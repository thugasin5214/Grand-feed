"""Core data models for IntelFeed."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Dict, Any


@dataclass
class Item:
    """Universal item — works for any source."""
    id: str                    # "reddit:abc123", "hn:12345", "news:uuid"
    source: str                # "reddit", "hackernews", "newsapi", "blind"
    title: str
    body: str                  # truncated to 3000 chars
    url: str
    author: str
    score: int                 # upvotes, likes, etc. 0 if not available
    num_comments: int
    created_at: datetime
    
    # Processing results
    category: str = "uncategorized"
    sentiment: str = "neutral"          # positive/negative/neutral
    relevance_score: float = 0.0
    ai_summary: str = ""
    ai_opportunity: str = ""
    entities: List[str] = field(default_factory=list)  # ["Amazon", "AWS", "Andy Jassy"]
    
    # Metadata
    pipeline: str = ""                  # which pipeline processed this
    tags: List[str] = field(default_factory=list)  # e.g. ["earnings", "layoffs"]
    collected_at: datetime = field(default_factory=datetime.utcnow)
    sent: bool = False
    
    # Source-specific
    subreddit: str = ""
    feed: str = ""                      # HN feed name, news category, etc.
    
    def truncate_body(self, max_chars: int = 3000) -> None:
        """Truncate body to max_chars."""
        if len(self.body) > max_chars:
            self.body = self.body[:max_chars] + "..."
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        result = {}
        for key, value in self.__dict__.items():
            if isinstance(value, datetime):
                result[key] = value.isoformat()
            else:
                result[key] = value
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Item':
        """Create Item from dictionary."""
        # Convert ISO strings back to datetime
        for key in ['created_at', 'collected_at']:
            if key in data and isinstance(data[key], str):
                data[key] = datetime.fromisoformat(data[key])
        return cls(**data)


@dataclass
class Category:
    """Category definition for AI classification."""
    name: str
    description: str
    examples: List[str] = field(default_factory=list)


@dataclass
class Pipeline:
    """Pipeline configuration."""
    name: str
    enabled: bool
    schedule: str  # cron expression
    sources: List[Dict[str, Any]]
    processors: Dict[str, Dict[str, Any]]
    outputs: List[Dict[str, Any]]
    
    @classmethod
    def from_config(cls, config: Dict[str, Any]) -> 'Pipeline':
        """Create Pipeline from YAML config."""
        return cls(
            name=config.get('name', 'Unnamed Pipeline'),
            enabled=config.get('enabled', True),
            schedule=config.get('schedule', '0 12 * * *'),
            sources=config.get('sources', []),
            processors=config.get('processors', {}),
            outputs=config.get('outputs', [])
        )


@dataclass
class PipelineStats:
    """Statistics for a pipeline run."""
    pipeline_name: str
    start_time: datetime
    end_time: Optional[datetime] = None
    items_collected: int = 0
    items_after_filter: int = 0
    items_after_dedup: int = 0
    items_classified: int = 0
    items_sent: int = 0
    errors: List[str] = field(default_factory=list)
    
    def duration_seconds(self) -> float:
        """Get duration in seconds."""
        if self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'pipeline_name': self.pipeline_name,
            'start_time': self.start_time.isoformat(),
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'duration_seconds': self.duration_seconds(),
            'items_collected': self.items_collected,
            'items_after_filter': self.items_after_filter,
            'items_after_dedup': self.items_after_dedup,
            'items_classified': self.items_classified,
            'items_sent': self.items_sent,
            'errors': self.errors
        }