"""Configuration loader for IntelFeed."""

import os
import yaml
from pathlib import Path
from typing import Dict, Any, Optional
from rich.console import Console

console = Console()


class Config:
    """Configuration manager for IntelFeed."""
    
    def __init__(self, secrets_path: str = "config/secrets.yaml"):
        """Initialize configuration.
        
        Args:
            secrets_path: Path to secrets YAML file
        """
        self.secrets_path = Path(secrets_path)
        self.global_config = self._load_secrets()
    
    def _load_secrets(self) -> Dict[str, Any]:
        """Load secrets from YAML file.
        
        Returns:
            Dictionary of secrets
        """
        if not self.secrets_path.exists():
            console.print(f"[yellow]Warning: Secrets file not found at {self.secrets_path}[/yellow]")
            console.print("[dim]Using environment variables as fallback[/dim]")
            return self._load_from_env()
        
        try:
            with open(self.secrets_path, 'r') as f:
                secrets = yaml.safe_load(f) or {}
            
            # Merge with environment variables (env vars take precedence)
            env_config = self._load_from_env()
            return self._deep_merge(secrets, env_config)
            
        except Exception as e:
            console.print(f"[red]Error loading secrets: {e}[/red]")
            return self._load_from_env()
    
    def _load_from_env(self) -> Dict[str, Any]:
        """Load configuration from environment variables.
        
        Returns:
            Dictionary of configuration from env vars
        """
        config = {}
        
        # OpenRouter API key
        if os.getenv('OPENROUTER_API_KEY'):
            config.setdefault('openrouter', {})['api_key'] = os.getenv('OPENROUTER_API_KEY')
        
        # Email configuration
        if os.getenv('GMAIL_SENDER'):
            config.setdefault('email', {})['sender'] = os.getenv('GMAIL_SENDER')
        if os.getenv('GMAIL_PASSWORD'):
            config.setdefault('email', {})['password'] = os.getenv('GMAIL_PASSWORD')
        if os.getenv('SMTP_HOST'):
            config.setdefault('email', {})['smtp_host'] = os.getenv('SMTP_HOST')
        if os.getenv('SMTP_PORT'):
            config.setdefault('email', {})['smtp_port'] = int(os.getenv('SMTP_PORT'))
        
        # NewsAPI key
        if os.getenv('NEWSAPI_KEY'):
            config.setdefault('newsapi', {})['api_key'] = os.getenv('NEWSAPI_KEY')
        
        # Blind credentials (future)
        if os.getenv('BLIND_USERNAME'):
            config.setdefault('blind', {})['username'] = os.getenv('BLIND_USERNAME')
        if os.getenv('BLIND_PASSWORD'):
            config.setdefault('blind', {})['password'] = os.getenv('BLIND_PASSWORD')
        
        return config
    
    def _deep_merge(self, dict1: Dict[str, Any], dict2: Dict[str, Any]) -> Dict[str, Any]:
        """Deep merge two dictionaries.
        
        Args:
            dict1: Base dictionary
            dict2: Dictionary to merge (takes precedence)
            
        Returns:
            Merged dictionary
        """
        result = dict1.copy()
        
        for key, value in dict2.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        
        return result
    
    def get_global_config(self) -> Dict[str, Any]:
        """Get global configuration including secrets.
        
        Returns:
            Global configuration dictionary
        """
        return self.global_config
    
    def load_pipeline_config(self, config_path: str) -> Dict[str, Any]:
        """Load pipeline configuration from YAML file.
        
        Args:
            config_path: Path to pipeline YAML file
            
        Returns:
            Pipeline configuration dictionary
        """
        config_path = Path(config_path)
        
        if not config_path.exists():
            raise FileNotFoundError(f"Pipeline config not found: {config_path}")
        
        try:
            with open(config_path, 'r') as f:
                pipeline_config = yaml.safe_load(f)
            
            return pipeline_config
            
        except Exception as e:
            raise ValueError(f"Error loading pipeline config: {e}")
    
    @staticmethod
    def list_pipelines(pipelines_dir: str = "pipelines") -> list:
        """List available pipeline configurations.
        
        Args:
            pipelines_dir: Directory containing pipeline YAML files
            
        Returns:
            List of pipeline configuration paths
        """
        pipelines_dir = Path(pipelines_dir)
        
        if not pipelines_dir.exists():
            return []
        
        return sorted([
            str(p) for p in pipelines_dir.glob("*.yaml")
            if p.is_file() and not p.name.startswith('.')
        ])
    
    @staticmethod
    def get_enabled_pipelines(pipelines_dir: str = "pipelines") -> list:
        """Get list of enabled pipelines.
        
        Args:
            pipelines_dir: Directory containing pipeline YAML files
            
        Returns:
            List of enabled pipeline configuration paths
        """
        enabled = []
        
        for pipeline_path in Config.list_pipelines(pipelines_dir):
            try:
                with open(pipeline_path, 'r') as f:
                    config = yaml.safe_load(f)
                
                if config.get('enabled', True):
                    enabled.append(pipeline_path)
            except:
                pass  # Skip invalid configs
        
        return enabled