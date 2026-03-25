"""Deduplication processor using SQLite database."""

import hashlib
from typing import List, Dict, Any, Set
from rich.console import Console

from intel_feed.core.base_processor import BaseProcessor
from intel_feed.core.registry import register_processor
from intel_feed.models import Item
from intel_feed.db import Database

console = Console()


@register_processor("dedup")
class DedupProcessor(BaseProcessor):
    """Remove duplicate items using database history."""
    
    def __init__(self, processor_config: Dict[str, Any], global_config: Dict[str, Any]):
        """Initialize dedup processor.
        
        Args:
            processor_config: Processor configuration
            global_config: Global configuration
        """
        super().__init__(processor_config, global_config)
        
        # Initialize database
        self.db = Database()
        
        # Dedup strategies
        self.by_id = processor_config.get('by_id', True)
        self.by_url = processor_config.get('by_url', True)
        self.by_title = processor_config.get('by_title', False)
        self.lookback_days = processor_config.get('lookback_days', 7)
    
    def process(self, items: List[Item]) -> List[Item]:
        """Remove duplicate items.
        
        Args:
            items: List of items to deduplicate
            
        Returns:
            Deduplicated list of items
        """
        if not self.is_enabled():
            return items
        
        initial_count = len(items)
        
        # Get existing items from database
        existing_ids = self._get_existing_identifiers()
        
        # Filter out duplicates
        unique_items = []
        duplicates = 0
        
        for item in items:
            if self._is_duplicate(item, existing_ids):
                duplicates += 1
                continue
            
            unique_items.append(item)
            
            # Add to existing set to catch duplicates within this batch
            existing_ids['ids'].add(item.id)
            existing_ids['urls'].add(item.url)
            if item.title:
                title_hash = self._hash_title(item.title)
                existing_ids['titles'].add(title_hash)
        
        if duplicates > 0:
            console.print(f"[yellow]Dedup: Removed {duplicates} duplicate items[/yellow]")
        else:
            console.print(f"[green]Dedup: No duplicates found in {initial_count} items[/green]")
        
        return unique_items
    
    def _get_existing_identifiers(self) -> Dict[str, Set[str]]:
        """Get existing item identifiers from database.
        
        Returns:
            Dictionary with sets of existing IDs, URLs, and title hashes
        """
        existing = {
            'ids': set(),
            'urls': set(),
            'titles': set()
        }
        
        # Query database for recent items
        recent_items = self.db.get_recent_items(days=self.lookback_days)
        
        for item_dict in recent_items:
            if self.by_id and item_dict.get('id'):
                existing['ids'].add(item_dict['id'])
            if self.by_url and item_dict.get('url'):
                existing['urls'].add(item_dict['url'])
            if self.by_title and item_dict.get('title'):
                title_hash = self._hash_title(item_dict['title'])
                existing['titles'].add(title_hash)
        
        console.print(f"[dim]Dedup: Checking against {len(recent_items)} items from last {self.lookback_days} days[/dim]")
        
        return existing
    
    def _is_duplicate(self, item: Item, existing: Dict[str, Set[str]]) -> bool:
        """Check if an item is a duplicate.
        
        Args:
            item: Item to check
            existing: Dictionary of existing identifiers
            
        Returns:
            True if duplicate, False otherwise
        """
        # Check by ID
        if self.by_id and item.id in existing['ids']:
            return True
        
        # Check by URL
        if self.by_url and item.url in existing['urls']:
            return True
        
        # Check by title (fuzzy match via hash)
        if self.by_title and item.title:
            title_hash = self._hash_title(item.title)
            if title_hash in existing['titles']:
                return True
        
        return False
    
    def _hash_title(self, title: str) -> str:
        """Create a hash of the title for fuzzy matching.
        
        Args:
            title: Title to hash
            
        Returns:
            Hash string
        """
        # Normalize title: lowercase, remove extra spaces
        normalized = ' '.join(title.lower().split())
        # Create hash
        return hashlib.md5(normalized.encode()).hexdigest()