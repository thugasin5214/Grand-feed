"""Registry for collectors, processors, and outputs."""

from typing import Dict, Type, Any
from intel_feed.core.base_collector import BaseCollector
from intel_feed.core.base_processor import BaseProcessor
from intel_feed.core.base_output import BaseOutput


COLLECTORS: Dict[str, Type[BaseCollector]] = {}
PROCESSORS: Dict[str, Type[BaseProcessor]] = {}
OUTPUTS: Dict[str, Type[BaseOutput]] = {}


def register_collector(name: str):
    """Decorator to register a collector class."""
    def decorator(cls):
        COLLECTORS[name] = cls
        return cls
    return decorator


def register_processor(name: str):
    """Decorator to register a processor class."""
    def decorator(cls):
        PROCESSORS[name] = cls
        return cls
    return decorator


def register_output(name: str):
    """Decorator to register an output class."""
    def decorator(cls):
        OUTPUTS[name] = cls
        return cls
    return decorator


def get_collector(name: str, source_config: Dict[str, Any], global_config: Dict[str, Any]) -> BaseCollector:
    """Get a collector instance by name."""
    if name not in COLLECTORS:
        raise ValueError(f"Unknown collector: {name}")
    return COLLECTORS[name](source_config, global_config)


def get_processor(name: str, processor_config: Dict[str, Any], global_config: Dict[str, Any]) -> BaseProcessor:
    """Get a processor instance by name."""
    if name not in PROCESSORS:
        raise ValueError(f"Unknown processor: {name}")
    return PROCESSORS[name](processor_config, global_config)


def get_output(name: str, output_config: Dict[str, Any], global_config: Dict[str, Any]) -> BaseOutput:
    """Get an output instance by name."""
    if name not in OUTPUTS:
        raise ValueError(f"Unknown output: {name}")
    return OUTPUTS[name](output_config, global_config)


def load_all_components():
    """Import all component modules to register them."""
    # Import collectors
    try:
        from intel_feed.collectors import reddit, hackernews, newsapi, blind
    except ImportError as e:
        pass  # Some collectors might not be implemented yet
    
    # Import processors
    try:
        from intel_feed.processors import keyword_filter, dedup, ai_classifier, sentiment
    except ImportError as e:
        pass  # Some processors might not be implemented yet
    
    # Import outputs
    try:
        from intel_feed.outputs import email_digest, database
    except ImportError as e:
        pass  # Some outputs might not be implemented yet