"""Database output for storing items."""

from typing import List, Dict, Any
from rich.console import Console

from intel_feed.core.base_output import BaseOutput
from intel_feed.core.registry import register_output
from intel_feed.models import Item
from intel_feed.db import Database

console = Console()


@register_output("database")
class DatabaseOutput(BaseOutput):
    """Save items to SQLite database."""
    
    def __init__(self, output_config: Dict[str, Any], global_config: Dict[str, Any]):
        """Initialize database output.
        
        Args:
            output_config: Configuration with table name, etc.
            global_config: Global configuration
        """
        super().__init__(output_config, global_config)
        
        # Database configuration
        self.table = output_config.get('table', 'items')
        self.db_path = output_config.get('db_path', 'data/intel_feed.db')
        
        # Initialize database
        self.db = Database(self.db_path)
    
    def send(self, items: List[Item], pipeline_name: str, stats: Dict[str, Any]) -> bool:
        """Save items to database.
        
        Args:
            items: List of items to save
            pipeline_name: Name of the pipeline
            stats: Pipeline execution statistics
            
        Returns:
            True if successful, False otherwise
        """
        if not items:
            console.print("[yellow]Database output: No items to save[/yellow]")
            return True
        
        console.print(f"[cyan]Saving {len(items)} items to database...[/cyan]")
        
        try:
            # Save items
            saved_count = self.db.save_items(items)
            
            # Save pipeline run stats
            self.db.save_pipeline_run(stats)
            
            console.print(f"[green]✓ Saved {saved_count}/{len(items)} items to database[/green]")
            
            # Mark items as sent if configured
            if self.output_config.get('mark_as_sent', False):
                item_ids = [item.id for item in items]
                marked = self.db.mark_items_sent(item_ids)
                console.print(f"[dim]  Marked {marked} items as sent[/dim]")
            
            return saved_count > 0
            
        except Exception as e:
            console.print(f"[red]✗ Database save failed: {e}[/red]")
            return False