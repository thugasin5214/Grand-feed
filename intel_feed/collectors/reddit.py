"""Reddit collector using PRAW (OAuth) with fallback to old.reddit JSON API."""

import time
import requests
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from intel_feed.core.base_collector import BaseCollector
from intel_feed.core.registry import register_collector
from intel_feed.models import Item

console = Console()


@register_collector("reddit")
class RedditCollector(BaseCollector):
    """Collect posts from Reddit. Uses PRAW if client_id/secret are configured,
    otherwise falls back to old.reddit.com JSON API."""

    def __init__(self, source_config: Dict[str, Any], global_config: Dict[str, Any]):
        super().__init__(source_config, global_config)

        self.subreddits = source_config.get('subreddits', [])
        self.min_score = source_config.get('min_score', 5)
        self.max_posts_per_sub = source_config.get('max_posts_per_sub', 100)
        self.time_window_hours = source_config.get('time_window_hours', 24)
        self.keywords_override = source_config.get('keywords_override', [])

        # Try PRAW first
        client_id = source_config.get('client_id') or global_config.get('reddit', {}).get('client_id')
        client_secret = source_config.get('client_secret') or global_config.get('reddit', {}).get('client_secret')

        self._praw = None
        if client_id and client_secret:
            try:
                import praw
                self._praw = praw.Reddit(
                    client_id=client_id,
                    client_secret=client_secret,
                    user_agent="IntelFeed/1.0 (personal research tool)",
                    ratelimit_seconds=300,
                )
                self._praw.read_only = True
                console.print("[dim]Reddit: using PRAW (OAuth)[/dim]")
            except Exception as e:
                console.print(f"[yellow]Reddit: PRAW init failed ({e}), falling back to JSON API[/yellow]")
                self._praw = None
        else:
            console.print("[dim]Reddit: no credentials, using old.reddit JSON API[/dim]")

        self.headers = {
            'User-Agent': 'IntelFeed/1.0 (personal research tool; +https://github.com/fengli/intel-feed)'
        }

    def collect(self) -> List[Item]:
        all_items = []

        with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console) as progress:
            for subreddit in self.subreddits:
                task = progress.add_task(f"Fetching r/{subreddit}...", total=None)
                try:
                    for sort in ['hot', 'new']:
                        if self._praw:
                            items = self._fetch_praw(subreddit, sort)
                        else:
                            items = self._fetch_json(subreddit, sort)
                        all_items.extend(items)
                        time.sleep(1)
                    count = len([i for i in all_items if i.subreddit == subreddit])
                    console.print(f"[green]✓[/green] r/{subreddit}: {count} posts")
                except Exception as e:
                    console.print(f"[red]✗ Failed to fetch r/{subreddit}: {e}[/red]")
                progress.remove_task(task)

        all_items = self.filter_by_time(all_items, self.time_window_hours)
        all_items = self.filter_by_score(all_items, self.min_score)
        if self.keywords_override:
            all_items = self.filter_by_keywords(all_items, include=self.keywords_override)
        all_items = self.dedupe_by_url(all_items)
        all_items = self.truncate_bodies(all_items)
        return all_items

    def _fetch_praw(self, subreddit: str, sort: str = 'hot') -> List[Item]:
        """Fetch via PRAW."""
        try:
            sub = self._praw.subreddit(subreddit)
            submissions = list(getattr(sub, sort)(limit=self.max_posts_per_sub))
            items = []
            for s in submissions:
                if s.removed_by_category or s.selftext in ('[removed]', '[deleted]'):
                    continue
                body = s.selftext or ''
                if len(body) > 3000:
                    body = body[:3000] + '...'
                created_at = datetime.fromtimestamp(s.created_utc, tz=timezone.utc).replace(tzinfo=None)
                items.append(Item(
                    id=f"reddit:{s.id}",
                    source="reddit",
                    title=s.title,
                    body=body,
                    url=f"https://reddit.com{s.permalink}",
                    author=str(s.author) if s.author else 'unknown',
                    score=s.score,
                    num_comments=s.num_comments,
                    created_at=created_at,
                    subreddit=subreddit,
                    feed=sort,
                ))
            return items
        except Exception as e:
            console.print(f"[yellow]PRAW fetch failed for r/{subreddit}/{sort}: {e}[/yellow]")
            return []

    def _fetch_json(self, subreddit: str, sort: str = 'hot') -> List[Item]:
        """Fallback: fetch via old.reddit.com JSON API."""
        url = f"https://old.reddit.com/r/{subreddit}/{sort}.json"
        try:
            response = requests.get(url, headers=self.headers, params={'limit': self.max_posts_per_sub}, timeout=15)
            response.raise_for_status()
            data = response.json()
            items = []
            for child in data.get('data', {}).get('children', []):
                post = child.get('data', {})
                if post.get('removed_by_category') or post.get('selftext') == '[removed]':
                    continue
                item = self._parse_post(post, subreddit, sort)
                if item:
                    items.append(item)
            return items
        except Exception as e:
            console.print(f"[yellow]JSON API failed for r/{subreddit}/{sort}: {e}[/yellow]")
            return []

    def _parse_post(self, post: Dict[str, Any], subreddit: str, sort: str = 'hot') -> Optional[Item]:
        try:
            post_id = post.get('id', '')
            permalink = post.get('permalink', f"/r/{subreddit}/comments/{post_id}/")
            url = f"https://reddit.com{permalink}"
            body = post.get('selftext', '') or post.get('title', '')
            if len(body) > 3000:
                body = body[:3000] + '...'
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
                feed=sort,
            )
        except Exception as e:
            console.print(f"[yellow]Warning: Failed to parse Reddit post: {e}[/yellow]")
            return None
