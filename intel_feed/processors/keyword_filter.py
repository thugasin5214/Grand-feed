"""Keyword filter processor for including/excluding items by keywords."""

from typing import List, Dict, Any
from rich.console import Console

from intel_feed.core.base_processor import BaseProcessor
from intel_feed.core.registry import register_processor
from intel_feed.models import Item

console = Console()


@register_processor("keyword_filter")
class KeywordFilterProcessor(BaseProcessor):
    """Filter items by keyword inclusion/exclusion."""
    
    def __init__(self, processor_config: Dict[str, Any], global_config: Dict[str, Any]):
        """Initialize keyword filter processor.
        
        Args:
            processor_config: Configuration with include/exclude keywords
            global_config: Global configuration
        """
        super().__init__(processor_config, global_config)
        
        self.include = processor_config.get('include', [])
        self.exclude = processor_config.get('exclude', [])
        
        # Convert to lowercase for case-insensitive matching
        self.include = [k.lower() for k in self.include]
        self.exclude = [k.lower() for k in self.exclude]
    
    def process(self, items: List[Item]) -> List[Item]:
        """Filter items by keywords.
        
        Args:
            items: List of items to filter
            
        Returns:
            Filtered list of items
        """
        if not self.is_enabled():
            return items
        
        if not self.include and not self.exclude:
            console.print("[dim]Keyword filter: No keywords configured, skipping[/dim]")
            return items
        
        initial_count = len(items)
        filtered = []
        
        for item in items:
            # Combine title and body for searching
            text = f"{item.title} {item.body}".lower()
            
            # Check exclusions first (if any exclude keyword is found, skip)
            if self.exclude:
                if any(keyword in text for keyword in self.exclude):
                    continue
            
            # Check inclusions (if configured, at least one must be found)
            if self.include:
                if not any(keyword in text for keyword in self.include):
                    continue
            
            filtered.append(item)
        
        # Log filtering results
        removed_count = initial_count - len(filtered)
        if removed_count > 0:
            console.print(f"[yellow]Keyword filter: Removed {removed_count} items[/yellow]")
            console.print(f"[dim]  Include: {', '.join(self.include[:5])}{'...' if len(self.include) > 5 else ''}[/dim]")
            console.print(f"[dim]  Exclude: {', '.join(self.exclude[:5])}{'...' if len(self.exclude) > 5 else ''}[/dim]")
        else:
            console.print(f"[green]Keyword filter: All {initial_count} items passed[/green]")
        
        return filtered