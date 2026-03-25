"""Base collector class for all data sources."""

from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import re
from rich.console import Console

from intel_feed.models import Item

console = Console()


class BaseCollector(ABC):
    """Abstract base class for all collectors."""
    
    def __init__(self, source_config: Dict[str, Any], global_config: Dict[str, Any]):
        """Initialize collector with configuration.
        
        Args:
            source_config: Source-specific configuration from pipeline YAML
            global_config: Global configuration including secrets
        """
        self.source_config = source_config
        self.global_config = global_config
        self.source_type = source_config.get('type', 'unknown')
        
    @abstractmethod
    def collect(self) -> List[Item]:
        """Collect items from the source.
        
        Returns:
            List of Item objects
        """
        pass
    
    def filter_by_time(self, items: List[Item], hours: int) -> List[Item]:
        """Filter items by time window.
        
        Args:
            items: List of items to filter
            hours: Number of hours in time window
            
        Returns:
            Filtered list of items
        """
        if hours <= 0:
            return items
            
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        filtered = [item for item in items if item.created_at >= cutoff]
        
        console.print(f"[dim]Filtered {len(items)} → {len(filtered)} items (last {hours}h)[/dim]")
        return filtered
    
    def filter_by_keywords(self, items: List[Item], 
                          include: Optional[List[str]] = None,
                          exclude: Optional[List[str]] = None) -> List[Item]:
        """Filter items by keyword inclusion/exclusion.
        
        Args:
            items: List of items to filter
            include: Keywords that must be present (OR logic)
            exclude: Keywords that must not be present
            
        Returns:
            Filtered list of items
        """
        if not include and not exclude:
            return items
        
        filtered = []
        for item in items:
            text = f"{item.title} {item.body}".lower()
            
            # Check exclusions first
            if exclude:
                if any(keyword.lower() in text for keyword in exclude):
                    continue
            
            # Check inclusions
            if include:
                if not any(keyword.lower() in text for keyword in include):
                    continue
            
            filtered.append(item)
        
        console.print(f"[dim]Keyword filtered {len(items)} → {len(filtered)} items[/dim]")
        return filtered
    
    def filter_by_score(self, items: List[Item], min_score: int = 0) -> List[Item]:
        """Filter items by minimum score.
        
        Args:
            items: List of items to filter
            min_score: Minimum score required
            
        Returns:
            Filtered list of items
        """
        if min_score <= 0:
            return items
        
        filtered = [item for item in items if item.score >= min_score]
        console.print(f"[dim]Score filtered {len(items)} → {len(filtered)} items (min: {min_score})[/dim]")
        return filtered
    
    def dedupe_by_url(self, items: List[Item]) -> List[Item]:
        """Remove duplicate items by URL.
        
        Args:
            items: List of items to deduplicate
            
        Returns:
            Deduplicated list of items
        """
        seen_urls = set()
        deduped = []
        
        for item in items:
            if item.url not in seen_urls:
                seen_urls.add(item.url)
                deduped.append(item)
        
        if len(deduped) < len(items):
            console.print(f"[dim]Deduped {len(items)} → {len(deduped)} items[/dim]")
        
        return deduped
    
    def truncate_bodies(self, items: List[Item], max_chars: int = 3000) -> List[Item]:
        """Truncate item bodies to max length.
        
        Args:
            items: List of items
            max_chars: Maximum characters for body
            
        Returns:
            Items with truncated bodies
        """
        for item in items:
            item.truncate_body(max_chars)
        return items