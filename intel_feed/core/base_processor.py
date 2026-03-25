"""Base processor class for item processing."""

from abc import ABC, abstractmethod
from typing import List, Dict, Any
from rich.console import Console

from intel_feed.models import Item

console = Console()


class BaseProcessor(ABC):
    """Abstract base class for all processors."""
    
    def __init__(self, processor_config: Dict[str, Any], global_config: Dict[str, Any]):
        """Initialize processor with configuration.
        
        Args:
            processor_config: Processor-specific configuration
            global_config: Global configuration including secrets
        """
        self.processor_config = processor_config
        self.global_config = global_config
        self.enabled = processor_config.get('enabled', True)
    
    @abstractmethod
    def process(self, items: List[Item]) -> List[Item]:
        """Process items.
        
        Args:
            items: List of items to process
            
        Returns:
            Processed list of items
        """
        pass
    
    def is_enabled(self) -> bool:
        """Check if processor is enabled."""
        return self.enabled