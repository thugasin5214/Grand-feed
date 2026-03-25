#!/usr/bin/env python3
"""Run a specific pipeline."""

import sys
import argparse
from pathlib import Path
from rich.console import Console

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from intel_feed.config import Config
from intel_feed.core.pipeline import Pipeline

console = Console()


def main():
    """Run a specific pipeline."""
    parser = argparse.ArgumentParser(description='Run an IntelFeed pipeline')
    parser.add_argument('pipeline', help='Pipeline name or path to YAML config')
    parser.add_argument('--secrets', default='config/secrets.yaml', 
                       help='Path to secrets.yaml (default: config/secrets.yaml)')
    parser.add_argument('--verbose', action='store_true', 
                       help='Enable verbose output')
    
    args = parser.parse_args()
    
    # Load configuration
    config = Config(secrets_path=args.secrets)
    global_config = config.get_global_config()
    
    # Determine pipeline path
    pipeline_path = args.pipeline
    if not pipeline_path.endswith('.yaml'):
        # Try to find in pipelines directory
        possible_path = Path('pipelines') / f"{pipeline_path}.yaml"
        if possible_path.exists():
            pipeline_path = str(possible_path)
        else:
            console.print(f"[red]Pipeline not found: {args.pipeline}[/red]")
            console.print(f"[dim]Looked for: {possible_path}[/dim]")
            sys.exit(1)
    
    # Check if pipeline exists
    if not Path(pipeline_path).exists():
        console.print(f"[red]Pipeline config not found: {pipeline_path}[/red]")
        sys.exit(1)
    
    # Run pipeline
    console.print(f"\n[bold blue]Starting IntelFeed Pipeline[/bold blue]")
    console.print(f"[dim]Config: {pipeline_path}[/dim]")
    console.print(f"[dim]Secrets: {args.secrets}[/dim]\n")
    
    try:
        pipeline = Pipeline(pipeline_path, global_config)
        stats = pipeline.run()
        
        # Check for errors
        if stats.get('errors'):
            console.print(f"\n[yellow]Pipeline completed with {len(stats['errors'])} errors[/yellow]")
            sys.exit(1)
        else:
            console.print(f"\n[green]Pipeline completed successfully![/green]")
            
    except Exception as e:
        console.print(f"\n[bold red]Pipeline failed: {e}[/bold red]")
        if args.verbose:
            import traceback
            console.print(traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    main()