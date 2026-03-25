"""Hacker News collector using Firebase API."""

import time
import requests
import re
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any, Optional
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

from intel_feed.core.base_collector import BaseCollector
from intel_feed.core.registry import register_collector
from intel_feed.models import Item

console = Console()


@register_collector("hackernews")
class HackerNewsCollector(BaseCollector):
    """Collect stories from Hacker News using Firebase API."""
    
    API_BASE = "https://hacker-news.firebaseio.com/v0"
    
    def __init__(self, source_config: Dict[str, Any], global_config: Dict[str, Any]):
        """Initialize HackerNews collector.
        
        Args:
            source_config: Configuration with feeds, max_items_per_feed, etc.
            global_config: Global configuration
        """
        super().__init__(source_config, global_config)
        
        self.feeds = source_config.get('feeds', ['topstories', 'askstories', 'showstories'])
        self.max_items_per_feed = source_config.get('max_items_per_feed', 100)
        self.time_window_hours = source_config.get('time_window_hours', 24)
        self.min_score = source_config.get('min_score', 5)
        self.keywords_override = source_config.get('keywords_override', [])
        
        # Parallel fetching settings
        self.max_workers = 10
        self.request_delay = 0.05  # Small delay between requests
    
    def collect(self) -> List[Item]:
        """Collect stories from configured HN feeds.
        
        Returns:
            List of Item objects
        """
        all_items = []
        
        for feed in self.feeds:
            console.print(f"\n[cyan]Fetching HN {feed}...[/cyan]")
            
            try:
                # Get story IDs
                story_ids = self._fetch_feed_ids(feed)
                
                if not story_ids:
                    console.print(f"[yellow]No stories found in {feed}[/yellow]")
                    continue
                
                # Limit to max_items_per_feed
                story_ids = story_ids[:self.max_items_per_feed]
                
                # Fetch stories in parallel
                stories = self._fetch_stories_parallel(story_ids, feed)
                
                # Convert to Items
                for story in stories:
                    item = self._parse_story(story, feed)
                    if item:
                        all_items.append(item)
                
                console.print(f"[green]✓[/green] HN {feed}: {len([i for i in all_items if i.feed == feed])} stories")
                
            except Exception as e:
                console.print(f"[red]✗ Failed to fetch HN {feed}: {e}[/red]")
        
        # Apply filters
        all_items = self.filter_by_time(all_items, self.time_window_hours)
        all_items = self.filter_by_score(all_items, self.min_score)
        
        # Apply keyword override if specified
        if self.keywords_override:
            all_items = self.filter_by_keywords(all_items, include=self.keywords_override)
        
        # Dedupe and truncate
        all_items = self.dedupe_by_url(all_items)
        all_items = self.truncate_bodies(all_items)
        
        return all_items
    
    def _fetch_feed_ids(self, feed: str) -> List[int]:
        """Fetch story IDs from a HN feed.
        
        Args:
            feed: Feed name (topstories, askstories, showstories, etc.)
            
        Returns:
            List of story IDs
        """
        url = f"{self.API_BASE}/{feed}.json"
        
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            return response.json() or []
        except Exception as e:
            console.print(f"[yellow]Warning: Failed to fetch {feed} IDs: {e}[/yellow]")
            return []
    
    def _fetch_stories_parallel(self, story_ids: List[int], feed: str) -> List[Dict[str, Any]]:
        """Fetch multiple stories in parallel.
        
        Args:
            story_ids: List of story IDs to fetch
            feed: Feed name for progress display
            
        Returns:
            List of story data dictionaries
        """
        stories = []
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console
        ) as progress:
            
            task = progress.add_task(f"Fetching {feed} stories...", total=len(story_ids))
            
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                future_to_id = {
                    executor.submit(self._fetch_story, story_id): story_id 
                    for story_id in story_ids
                }
                
                for future in as_completed(future_to_id):
                    try:
                        story = future.result()
                        if story:
                            stories.append(story)
                    except Exception as e:
                        pass  # Skip failed stories
                    
                    progress.update(task, advance=1)
                    time.sleep(self.request_delay)  # Rate limiting
        
        return stories
    
    def _fetch_story(self, story_id: int) -> Optional[Dict[str, Any]]:
        """Fetch a single story by ID.
        
        Args:
            story_id: HN story ID
            
        Returns:
            Story data or None if failed
        """
        url = f"{self.API_BASE}/item/{story_id}.json"
        
        try:
            response = requests.get(url, timeout=5)
            response.raise_for_status()
            return response.json()
        except Exception:
            return None
    
    def _parse_story(self, story: Dict[str, Any], feed: str) -> Optional[Item]:
        """Parse HN story data into Item.
        
        Args:
            story: HN story data
            feed: Feed name
            
        Returns:
            Item object or None if parsing fails
        """
        try:
            # Skip non-stories
            if story.get('type') != 'story':
                return None
            
            # Build URL
            story_id = story.get('id', '')
            url = story.get('url', f"https://news.ycombinator.com/item?id={story_id}")
            
            # Get text content
            title = story.get('title', 'Untitled')
            text = story.get('text', '')
            
            # Clean HTML from text
            if text:
                text = re.sub('<[^<]+?>', '', text)  # Strip HTML tags
                text = text.strip()
            
            body = text if text else title
            
            # Parse timestamp
            created_time = story.get('time', 0)
            created_at = datetime.utcfromtimestamp(created_time) if created_time else datetime.utcnow()
            
            # Get comments count
            num_comments = story.get('descendants', 0)
            
            return Item(
                id=f"hn:{story_id}",
                source="hackernews",
                title=title,
                body=body,
                url=url,
                author=story.get('by', 'unknown'),
                score=story.get('score', 0),
                num_comments=num_comments,
                created_at=created_at,
                feed=feed
            )
            
        except Exception as e:
            console.print(f"[yellow]Warning: Failed to parse HN story: {e}[/yellow]")
            return None