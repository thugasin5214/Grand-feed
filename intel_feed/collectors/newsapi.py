"""NewsAPI.org collector for news articles."""

import requests
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from rich.console import Console

from intel_feed.core.base_collector import BaseCollector
from intel_feed.core.registry import register_collector
from intel_feed.models import Item

console = Console()


@register_collector("newsapi")
class NewsAPICollector(BaseCollector):
    """Collect news articles from NewsAPI.org."""
    
    API_BASE = "https://newsapi.org/v2"
    
    def __init__(self, source_config: Dict[str, Any], global_config: Dict[str, Any]):
        """Initialize NewsAPI collector.
        
        Args:
            source_config: Configuration with query, language, page_size, etc.
            global_config: Global configuration including API key
        """
        super().__init__(source_config, global_config)
        
        # Get API key from secrets
        self.api_key = global_config.get('newsapi', {}).get('api_key', '')
        if not self.api_key:
            console.print("[yellow]Warning: NewsAPI key not configured in secrets.yaml[/yellow]")
        
        # Configuration
        self.query = source_config.get('query', '')
        self.language = source_config.get('language', 'en')
        self.page_size = source_config.get('page_size', 100)
        self.sort_by = source_config.get('sort_by', 'relevancy')  # relevancy, popularity, publishedAt
        self.domains = source_config.get('domains', '')  # Comma-separated list of domains
        self.exclude_domains = source_config.get('exclude_domains', '')
        self.time_window_hours = source_config.get('time_window_hours', 24)
    
    def collect(self) -> List[Item]:
        """Collect news articles from NewsAPI.
        
        Returns:
            List of Item objects
        """
        if not self.api_key:
            console.print("[red]✗ Skipping NewsAPI: No API key configured[/red]")
            return []
        
        console.print(f"[cyan]Fetching news articles for query: {self.query}...[/cyan]")
        
        all_items = []
        
        try:
            # Calculate date range
            to_date = datetime.utcnow()
            from_date = to_date - timedelta(hours=self.time_window_hours)
            
            # Build request parameters
            params = {
                'apiKey': self.api_key,
                'q': self.query,
                'language': self.language,
                'pageSize': self.page_size,
                'sortBy': self.sort_by,
                'from': from_date.isoformat(),
                'to': to_date.isoformat()
            }
            
            if self.domains:
                params['domains'] = self.domains
            if self.exclude_domains:
                params['excludeDomains'] = self.exclude_domains
            
            # Fetch articles
            articles = self._fetch_articles(params)
            
            # Convert to Items
            for article in articles:
                item = self._parse_article(article)
                if item:
                    all_items.append(item)
            
            console.print(f"[green]✓[/green] NewsAPI: {len(all_items)} articles")
            
        except Exception as e:
            console.print(f"[red]✗ Failed to fetch from NewsAPI: {e}[/red]")
        
        # Dedupe and truncate
        all_items = self.dedupe_by_url(all_items)
        all_items = self.truncate_bodies(all_items)
        
        return all_items
    
    def _fetch_articles(self, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Fetch articles from NewsAPI.
        
        Args:
            params: API request parameters
            
        Returns:
            List of article data
        """
        url = f"{self.API_BASE}/everything"
        
        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            # Check for API errors
            if data.get('status') != 'ok':
                error_msg = data.get('message', 'Unknown error')
                console.print(f"[red]NewsAPI error: {error_msg}[/red]")
                return []
            
            articles = data.get('articles', [])
            total_results = data.get('totalResults', 0)
            
            console.print(f"[dim]Found {total_results} total results, fetching {len(articles)}[/dim]")
            
            return articles
            
        except requests.exceptions.RequestException as e:
            console.print(f"[yellow]Warning: NewsAPI request failed: {e}[/yellow]")
            return []
    
    def _parse_article(self, article: Dict[str, Any]) -> Optional[Item]:
        """Parse NewsAPI article into Item.
        
        Args:
            article: Article data from NewsAPI
            
        Returns:
            Item object or None if parsing fails
        """
        try:
            # Parse published date
            published_at = article.get('publishedAt', '')
            if published_at:
                # NewsAPI returns ISO format with Z suffix
                published_at = published_at.replace('Z', '+00:00')
                created_at = datetime.fromisoformat(published_at)
            else:
                created_at = datetime.utcnow()
            
            # Get content
            title = article.get('title', 'Untitled')
            description = article.get('description', '')
            content = article.get('content', '')
            
            # Combine description and content for body
            body = description
            if content and content != description:
                # NewsAPI truncates content, often ending with [+X chars]
                if content.endswith(']'):
                    # Remove the truncation indicator
                    content = content.rsplit('[', 1)[0].strip()
                if content and content not in body:
                    body = f"{description}\n\n{content}" if description else content
            
            # Get source info
            source = article.get('source', {})
            source_name = source.get('name', 'Unknown')
            
            # Generate unique ID
            url = article.get('url', '')
            article_id = str(hash(url))[-8:] if url else str(hash(title))[-8:]
            
            return Item(
                id=f"news:{article_id}",
                source="newsapi",
                title=title,
                body=body or title,
                url=url,
                author=article.get('author', source_name),
                score=0,  # NewsAPI doesn't provide scores
                num_comments=0,  # No comments in news articles
                created_at=created_at,
                feed=source_name
            )
            
        except Exception as e:
            console.print(f"[yellow]Warning: Failed to parse NewsAPI article: {e}[/yellow]")
            return None