"""Reddit collector using public JSON API."""

import time
import requests
from datetime import datetime
from typing import List, Dict, Any, Optional
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from intel_feed.core.base_collector import BaseCollector
from intel_feed.core.registry import register_collector
from intel_feed.models import Item

console = Console()


@register_collector("reddit")
class RedditCollector(BaseCollector):
    """Collect posts from Reddit using the public JSON API."""
    
    def __init__(self, source_config: Dict[str, Any], global_config: Dict[str, Any]):
        """Initialize Reddit collector.
        
        Args:
            source_config: Configuration with subreddits, min_score, etc.
            global_config: Global configuration
        """
        super().__init__(source_config, global_config)
        
        self.subreddits = source_config.get('subreddits', [])
        self.min_score = source_config.get('min_score', 5)
        self.max_posts_per_sub = source_config.get('max_posts_per_sub', 100)
        self.time_window_hours = source_config.get('time_window_hours', 24)
        self.keywords_override = source_config.get('keywords_override', [])
        
        # Headers to avoid rate limiting
        self.headers = {
            'User-Agent': 'IntelFeed/1.0 (https://github.com/fengli/intel-feed)'
        }
    
    def collect(self) -> List[Item]:
        """Collect posts from configured subreddits.
        
        Returns:
            List of Item objects
        """
        all_items = []
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            
            for subreddit in self.subreddits:
                task = progress.add_task(f"Fetching r/{subreddit}...", total=None)
                
                try:
                    # Fetch from both hot and new
                    for sort in ['hot', 'new']:
                        items = self._fetch_subreddit(subreddit, sort)
                        all_items.extend(items)
                        time.sleep(1)  # Rate limiting
                    
                    progress.update(task, completed=True)
                    console.print(f"[green]✓[/green] r/{subreddit}: {len([i for i in all_items if i.subreddit == subreddit])} posts")
                    
                except Exception as e:
                    console.print(f"[red]✗ Failed to fetch r/{subreddit}: {e}[/red]")
                
                progress.remove_task(task)
        
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
    
    def _fetch_subreddit(self, subreddit: str, sort: str = 'hot') -> List[Item]:
        """Fetch posts from a subreddit.
        
        Args:
            subreddit: Name of subreddit
            sort: Sort order (hot, new, top)
            
        Returns:
            List of Item objects
        """
        url = f"https://www.reddit.com/r/{subreddit}/{sort}.json"
        params = {'limit': self.max_posts_per_sub}
        
        try:
            response = requests.get(url, headers=self.headers, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            items = []
            for child in data.get('data', {}).get('children', []):
                post = child.get('data', {})
                
                # Skip removed/deleted posts
                if post.get('removed_by_category') or post.get('selftext') == '[removed]':
                    continue
                
                item = self._parse_post(post, subreddit, sort)
                if item:
                    items.append(item)
            
            return items
            
        except Exception as e:
            console.print(f"[yellow]Warning: Error fetching r/{subreddit}/{sort}: {e}[/yellow]")
            return []
    
    def _parse_post(self, post: Dict[str, Any], subreddit: str, sort: str = 'hot') -> Optional[Item]:
        """Parse Reddit post data into Item.
        
        Args:
            post: Reddit post data
            subreddit: Name of subreddit
            
        Returns:
            Item object or None if parsing fails
        """
        try:
            # Build post URL
            post_id = post.get('id', '')
            permalink = post.get('permalink', f"/r/{subreddit}/comments/{post_id}/")
            url = f"https://reddit.com{permalink}"
            
            # Get body text
            body = post.get('selftext', '') or post.get('title', '')
            if len(body) > 3000:
                body = body[:3000] + "..."
            
            # Parse timestamp
            created_utc = post.get('created_utc', 0)
            created_at = datetime.utcfromtimestamp(created_utc) if created_utc else datetime.utcnow()
            
            return Item(
                id=f"reddit:{post_id}",
                source="reddit",
                title=post.get('title', 'Untitled'),
                body=body,
                url=url,
                author=post.get('author', 'unknown'),
                score=post.get('score', 0),
                num_comments=post.get('num_comments', 0),
                created_at=created_at,
                subreddit=subreddit,
                feed=sort
            )
            
        except Exception as e:
            console.print(f"[yellow]Warning: Failed to parse Reddit post: {e}[/yellow]")
            return None