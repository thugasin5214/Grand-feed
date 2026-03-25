"""Pipeline runner — loads config, runs collect→process→output."""

import os
import yaml
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn

from intel_feed.models import Item, Pipeline as PipelineConfig, PipelineStats
from intel_feed.core.registry import get_collector, get_processor, get_output, load_all_components

console = Console()


class Pipeline:
    """Pipeline runner that orchestrates collection, processing, and output."""
    
    def __init__(self, config_path: str, global_config: Optional[Dict[str, Any]] = None):
        """Initialize pipeline with configuration.
        
        Args:
            config_path: Path to pipeline YAML configuration
            global_config: Global configuration including secrets
        """
        self.config_path = Path(config_path)
        self.global_config = global_config or {}
        
        # Load pipeline configuration
        with open(self.config_path, 'r') as f:
            config_data = yaml.safe_load(f)
        
        self.config = PipelineConfig.from_config(config_data)
        self.stats = PipelineStats(
            pipeline_name=self.config.name,
            start_time=datetime.utcnow()
        )
        
        # Load all component modules to register them
        load_all_components()
    
    def run(self) -> Dict[str, Any]:
        """Run the pipeline.
        
        Returns:
            Statistics dictionary
        """
        console.print(f"\n[bold blue]═══ Running Pipeline: {self.config.name} ═══[/bold blue]")
        
        if not self.config.enabled:
            console.print("[yellow]Pipeline is disabled. Skipping.[/yellow]")
            return self.stats.to_dict()
        
        try:
            # 1. Collect from all sources
            all_items = self._collect()
            
            # 2. Process items
            processed_items = self._process(all_items)
            
            # 3. Send to outputs
            self._output(processed_items)
            
        except Exception as e:
            console.print(f"[bold red]Pipeline error: {e}[/bold red]")
            self.stats.errors.append(str(e))
        finally:
            self.stats.end_time = datetime.utcnow()
            self._print_summary()
        
        return self.stats.to_dict()
    
    def _collect(self) -> List[Item]:
        """Collect items from all configured sources."""
        console.print("\n[bold cyan]📥 Collection Phase[/bold cyan]")
        all_items = []
        
        for source_config in self.config.sources:
            source_type = source_config.get('type')
            console.print(f"\nCollecting from [bold]{source_type}[/bold]...")
            
            try:
                collector = get_collector(source_type, source_config, self.global_config)
                items = collector.collect()
                
                # Set pipeline name on items
                for item in items:
                    item.pipeline = self.config.name
                
                all_items.extend(items)
                console.print(f"[green]✓[/green] Collected {len(items)} items from {source_type}")
                
            except Exception as e:
                console.print(f"[red]✗ Failed to collect from {source_type}: {e}[/red]")
                self.stats.errors.append(f"Collection error ({source_type}): {e}")
        
        self.stats.items_collected = len(all_items)
        console.print(f"\n[dim]Total collected: {len(all_items)} items[/dim]")
        return all_items
    
    def _process(self, items: List[Item]) -> List[Item]:
        """Process items through configured processors."""
        if not items:
            return items
        
        console.print("\n[bold cyan]⚙️  Processing Phase[/bold cyan]")
        processed_items = items
        
        # Process in order: keyword_filter → dedup → ai_classifier → others
        processor_order = ['keyword_filter', 'dedup', 'ai_classifier', 'sentiment']
        
        for processor_name in processor_order:
            if processor_name not in self.config.processors:
                continue
            
            processor_config = self.config.processors[processor_name]
            if not processor_config.get('enabled', True):
                continue
            
            console.print(f"\nRunning [bold]{processor_name}[/bold] processor...")
            
            try:
                processor = get_processor(processor_name, processor_config, self.global_config)
                processed_items = processor.process(processed_items)
                
                # Update stats
                if processor_name == 'keyword_filter':
                    self.stats.items_after_filter = len(processed_items)
                elif processor_name == 'dedup':
                    self.stats.items_after_dedup = len(processed_items)
                elif processor_name == 'ai_classifier':
                    self.stats.items_classified = len([i for i in processed_items if i.category != 'uncategorized'])
                
                console.print(f"[green]✓[/green] {processor_name} complete ({len(processed_items)} items)")
                
            except Exception as e:
                console.print(f"[red]✗ Processor {processor_name} failed: {e}[/red]")
                self.stats.errors.append(f"Processor error ({processor_name}): {e}")
        
        return processed_items
    
    def _output(self, items: List[Item]) -> None:
        """Send items to configured outputs."""
        if not items:
            console.print("\n[yellow]No items to output.[/yellow]")
            return
        
        console.print("\n[bold cyan]📤 Output Phase[/bold cyan]")
        
        for output_config in self.config.outputs:
            output_type = output_config.get('type')
            console.print(f"\nSending to [bold]{output_type}[/bold]...")
            
            try:
                output = get_output(output_type, output_config, self.global_config)
                
                if output.should_send(items):
                    success = output.send(items, self.config.name, self.stats.to_dict())
                    
                    if success:
                        self.stats.items_sent = len(items)
                        console.print(f"[green]✓[/green] Sent {len(items)} items to {output_type}")
                    else:
                        console.print(f"[yellow]⚠[/yellow] Failed to send to {output_type}")
                
            except Exception as e:
                console.print(f"[red]✗ Output {output_type} failed: {e}[/red]")
                self.stats.errors.append(f"Output error ({output_type}): {e}")
    
    def _print_summary(self) -> None:
        """Print pipeline execution summary."""
        console.print("\n[bold cyan]📊 Pipeline Summary[/bold cyan]")
        
        table = Table(show_header=False, box=None)
        table.add_column("Metric", style="dim")
        table.add_column("Value", justify="right")
        
        table.add_row("Pipeline", self.config.name)
        table.add_row("Duration", f"{self.stats.duration_seconds():.1f}s")
        table.add_row("Items Collected", str(self.stats.items_collected))
        table.add_row("After Filter", str(self.stats.items_after_filter))
        table.add_row("After Dedup", str(self.stats.items_after_dedup))
        table.add_row("Classified", str(self.stats.items_classified))
        table.add_row("Items Sent", str(self.stats.items_sent))
        
        if self.stats.errors:
            table.add_row("Errors", str(len(self.stats.errors)), style="red")
        
        console.print(table)
        
        if self.stats.errors:
            console.print("\n[bold red]Errors:[/bold red]")
            for error in self.stats.errors:
                console.print(f"  • {error}")