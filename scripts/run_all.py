#!/usr/bin/env python3
"""Run all enabled pipelines."""

import sys
import argparse
from pathlib import Path
from rich.console import Console
from rich.table import Table

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from intel_feed.config import Config
from intel_feed.core.pipeline import Pipeline

console = Console()


def main():
    """Run all enabled pipelines."""
    parser = argparse.ArgumentParser(description='Run all enabled IntelFeed pipelines')
    parser.add_argument('--secrets', default='config/secrets.yaml',
                       help='Path to secrets.yaml (default: config/secrets.yaml)')
    parser.add_argument('--pipelines-dir', default='pipelines',
                       help='Directory containing pipeline configs (default: pipelines)')
    parser.add_argument('--verbose', action='store_true',
                       help='Enable verbose output')
    parser.add_argument('--dry-run', action='store_true',
                       help='Show which pipelines would run without executing them')
    
    args = parser.parse_args()
    
    # Load configuration
    config = Config(secrets_path=args.secrets)
    global_config = config.get_global_config()
    
    # Get enabled pipelines
    enabled_pipelines = config.get_enabled_pipelines(args.pipelines_dir)
    
    if not enabled_pipelines:
        console.print("[yellow]No enabled pipelines found[/yellow]")
        console.print(f"[dim]Looked in: {args.pipelines_dir}/[/dim]")
        sys.exit(0)
    
    console.print(f"\n[bold blue]IntelFeed - Running All Enabled Pipelines[/bold blue]")
    console.print(f"[dim]Found {len(enabled_pipelines)} enabled pipeline(s)[/dim]\n")
    
    if args.dry_run:
        console.print("[yellow]DRY RUN MODE - Not executing pipelines[/yellow]\n")
        for pipeline_path in enabled_pipelines:
            console.print(f"  • Would run: {pipeline_path}")
        sys.exit(0)
    
    # Track results
    results = []
    total_items_collected = 0
    total_items_sent = 0
    failed_pipelines = []
    
    # Run each pipeline
    for i, pipeline_path in enumerate(enabled_pipelines, 1):
        console.print(f"\n{'='*60}")
        console.print(f"[cyan]Pipeline {i}/{len(enabled_pipelines)}[/cyan]")
        
        try:
            pipeline = Pipeline(pipeline_path, global_config)
            stats = pipeline.run()
            
            results.append({
                'name': stats.get('pipeline_name', 'Unknown'),
                'status': 'Failed' if stats.get('errors') else 'Success',
                'collected': stats.get('items_collected', 0),
                'sent': stats.get('items_sent', 0),
                'errors': len(stats.get('errors', []))
            })
            
            total_items_collected += stats.get('items_collected', 0)
            total_items_sent += stats.get('items_sent', 0)
            
            if stats.get('errors'):
                failed_pipelines.append(stats.get('pipeline_name'))
                
        except Exception as e:
            pipeline_name = Path(pipeline_path).stem
            console.print(f"[bold red]Pipeline {pipeline_name} failed: {e}[/bold red]")
            
            results.append({
                'name': pipeline_name,
                'status': 'Failed',
                'collected': 0,
                'sent': 0,
                'errors': 1
            })
            
            failed_pipelines.append(pipeline_name)
            
            if args.verbose:
                import traceback
                console.print(traceback.format_exc())
    
    # Print summary
    console.print(f"\n{'='*60}")
    console.print("\n[bold cyan]📊 Summary Report[/bold cyan]\n")
    
    # Create summary table
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Pipeline", style="cyan")
    table.add_column("Status", justify="center")
    table.add_column("Collected", justify="right")
    table.add_column("Sent", justify="right")
    table.add_column("Errors", justify="right")
    
    for result in results:
        status_style = "green" if result['status'] == 'Success' else "red"
        table.add_row(
            result['name'],
            f"[{status_style}]{result['status']}[/{status_style}]",
            str(result['collected']),
            str(result['sent']),
            str(result['errors']) if result['errors'] > 0 else "-"
        )
    
    console.print(table)
    
    # Print totals
    console.print(f"\n[bold]Totals:[/bold]")
    console.print(f"  • Pipelines run: {len(enabled_pipelines)}")
    console.print(f"  • Items collected: {total_items_collected}")
    console.print(f"  • Items sent: {total_items_sent}")
    
    if failed_pipelines:
        console.print(f"\n[red]Failed pipelines: {', '.join(failed_pipelines)}[/red]")
        sys.exit(1)
    else:
        console.print(f"\n[green]All pipelines completed successfully![/green]")


if __name__ == "__main__":
    main()