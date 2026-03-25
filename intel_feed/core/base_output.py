"""Base output class for sending results."""

from abc import ABC, abstractmethod
from typing import List, Dict, Any
from rich.console import Console

from intel_feed.models import Item

console = Console()


class BaseOutput(ABC):
    """Abstract base class for all outputs."""
    
    def __init__(self, output_config: Dict[str, Any], global_config: Dict[str, Any]):
        """Initialize output with configuration.
        
        Args:
            output_config: Output-specific configuration
            global_config: Global configuration including secrets
        """
        self.output_config = output_config
        self.global_config = global_config
        self.output_type = output_config.get('type', 'unknown')
    
    @abstractmethod
    def send(self, items: List[Item], pipeline_name: str, stats: Dict[str, Any]) -> bool:
        """Send items to output destination.
        
        Args:
            items: List of items to send
            pipeline_name: Name of the pipeline
            stats: Pipeline execution statistics
            
        Returns:
            True if successful, False otherwise
        """
        pass
    
    def should_send(self, items: List[Item]) -> bool:
        """Check if output should be sent based on conditions.
        
        Args:
            items: List of items to potentially send
            
        Returns:
            True if should send, False otherwise
        """
        min_items = self.output_config.get('min_items', 0)
        if len(items) < min_items:
            console.print(f"[yellow]Skipping {self.output_type} output: only {len(items)} items (min: {min_items})[/yellow]")
            return False
        return True