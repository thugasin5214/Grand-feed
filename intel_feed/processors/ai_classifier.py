"""AI classifier processor using OpenRouter API."""

import json
import time
from typing import List, Dict, Any, Optional
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

from intel_feed.core.base_processor import BaseProcessor
from intel_feed.core.registry import register_processor
from intel_feed.models import Item

console = Console()


@register_processor("ai_classifier")
class AIClassifierProcessor(BaseProcessor):
    """Classify items using AI models via OpenRouter."""
    
    def __init__(self, processor_config: Dict[str, Any], global_config: Dict[str, Any]):
        """Initialize AI classifier processor.
        
        Args:
            processor_config: Configuration with model, categories, etc.
            global_config: Global configuration including API key
        """
        super().__init__(processor_config, global_config)
        
        # Get API key
        self.api_key = global_config.get('openrouter', {}).get('api_key', '')
        if not self.api_key:
            console.print("[yellow]Warning: OpenRouter API key not configured[/yellow]")
        
        # Model configuration
        self.model = processor_config.get('model', 'openai/gpt-3.5-turbo')
        self.fallback_model = processor_config.get('fallback_model', 'openai/gpt-3.5-turbo')
        self.temperature = processor_config.get('temperature', 0.3)
        self.batch_size = processor_config.get('batch_size', 10)
        
        # Classification configuration
        self.focus = processor_config.get('focus', 'general intelligence and insights')
        self.categories = processor_config.get('categories', {
            'important': 'Important information requiring attention',
            'interesting': 'Interesting but not critical',
            'noise': 'Not relevant or useful'
        })
        self.extra_instructions = processor_config.get('extra_instructions', '')
        
        # Rate limiting
        self.rate_limit_delay = 1.0  # Seconds between API calls
        
        # Import OpenAI client if available
        try:
            from openai import OpenAI
            self.client = OpenAI(
                api_key=self.api_key,
                base_url="https://openrouter.ai/api/v1"
            ) if self.api_key else None
        except ImportError:
            console.print("[yellow]Warning: openai package not installed[/yellow]")
            self.client = None
    
    def process(self, items: List[Item]) -> List[Item]:
        """Classify items using AI.
        
        Args:
            items: List of items to classify
            
        Returns:
            Items with classification results
        """
        if not self.is_enabled():
            return items
        
        if not self.client:
            console.print("[yellow]AI Classifier: Skipping (no API client)[/yellow]")
            return items
        
        if not items:
            return items
        
        console.print(f"\n[cyan]Classifying {len(items)} items with AI...[/cyan]")
        
        # Process in batches
        classified_items = []
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console
        ) as progress:
            
            task = progress.add_task("Classifying items...", total=len(items))
            
            for i in range(0, len(items), self.batch_size):
                batch = items[i:i + self.batch_size]
                
                try:
                    # Classify batch
                    batch_results = self._classify_batch(batch)
                    
                    # Apply results to items
                    for item, result in zip(batch, batch_results):
                        if result:
                            item.category = result.get('category', 'uncategorized')
                            item.relevance_score = result.get('relevance_score', 0.0)
                            item.ai_summary = result.get('summary', '')
                            item.ai_opportunity = result.get('opportunity', '')
                            
                            # Extract entities if provided
                            entities = result.get('entities', [])
                            if entities:
                                item.entities = entities
                        
                        classified_items.append(item)
                    
                    progress.update(task, advance=len(batch))
                    time.sleep(self.rate_limit_delay)  # Rate limiting
                    
                except Exception as e:
                    console.print(f"[red]Batch classification failed: {e}[/red]")
                    # Add unclassified items
                    classified_items.extend(batch)
                    progress.update(task, advance=len(batch))
        
        # Log results
        classified_count = sum(1 for i in classified_items if i.category != 'uncategorized')
        console.print(f"[green]✓ Classified {classified_count}/{len(items)} items[/green]")
        
        # Show category distribution
        category_counts = {}
        for item in classified_items:
            category_counts[item.category] = category_counts.get(item.category, 0) + 1
        
        if category_counts:
            console.print("[dim]Category distribution:[/dim]")
            for category, count in sorted(category_counts.items(), key=lambda x: x[1], reverse=True):
                console.print(f"  • {category}: {count}")
        
        return classified_items
    
    def _classify_batch(self, items: List[Item]) -> List[Dict[str, Any]]:
        """Classify a batch of items.
        
        Args:
            items: List of items to classify
            
        Returns:
            List of classification results
        """
        # Build prompt
        prompt = self._build_batch_prompt(items)
        
        try:
            # Call AI model
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self._get_system_prompt()},
                    {"role": "user", "content": prompt}
                ],
                temperature=self.temperature,
                max_tokens=2000
            )
            
            # Parse response
            content = response.choices[0].message.content
            return self._parse_batch_response(content, len(items))
            
        except Exception as e:
            console.print(f"[yellow]Primary model failed, trying fallback: {e}[/yellow]")
            
            # Try fallback model
            try:
                response = self.client.chat.completions.create(
                    model=self.fallback_model,
                    messages=[
                        {"role": "system", "content": self._get_system_prompt()},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=self.temperature,
                    max_tokens=2000
                )
                
                content = response.choices[0].message.content
                return self._parse_batch_response(content, len(items))
                
            except Exception as e2:
                console.print(f"[red]Fallback model also failed: {e2}[/red]")
                return [{}] * len(items)
    
    def _get_system_prompt(self) -> str:
        """Get system prompt for AI classification."""
        categories_desc = "\n".join([
            f"- {name}: {desc}" 
            for name, desc in self.categories.items()
        ])
        
        prompt = f"""You are an intelligence analyst focused on: {self.focus}

Your task is to classify items into these categories:
{categories_desc}

For each item, provide:
1. category: One of the category names above
2. relevance_score: 0.0 to 1.0 (how relevant/important)
3. summary: One-sentence summary of the key point
4. opportunity: Any opportunity or action item identified (or empty string)
5. entities: List of key entities mentioned (people, companies, products)

{self.extra_instructions}

Respond with valid JSON array matching the number of input items."""
        
        return prompt
    
    def _build_batch_prompt(self, items: List[Item]) -> str:
        """Build prompt for a batch of items."""
        items_text = []
        
        for i, item in enumerate(items, 1):
            # Truncate body for prompt
            body = item.body[:500] if len(item.body) > 500 else item.body
            
            items_text.append(f"""Item {i}:
Title: {item.title}
Source: {item.source} ({item.subreddit or item.feed or 'main'})
Score: {item.score} | Comments: {item.num_comments}
Body: {body}""")
        
        prompt = f"""Classify these {len(items)} items:

{chr(10).join(items_text)}

Return a JSON array with {len(items)} objects, one for each item."""
        
        return prompt
    
    def _parse_batch_response(self, content: str, expected_count: int) -> List[Dict[str, Any]]:
        """Parse AI response for batch classification.
        
        Args:
            content: AI response content
            expected_count: Expected number of results
            
        Returns:
            List of classification results
        """
        try:
            # Try to parse as JSON
            # Handle response that might have markdown code blocks
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]
            
            results = json.loads(content)
            
            # Ensure it's a list
            if not isinstance(results, list):
                results = [results]
            
            # Pad with empty results if needed
            while len(results) < expected_count:
                results.append({})
            
            return results[:expected_count]
            
        except json.JSONDecodeError as e:
            console.print(f"[yellow]Failed to parse AI response as JSON: {e}[/yellow]")
            return [{}] * expected_count