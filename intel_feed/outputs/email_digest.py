"""Email digest output using Gmail SMTP."""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any
import jinja2
from rich.console import Console

from intel_feed.core.base_output import BaseOutput
from intel_feed.core.registry import register_output
from intel_feed.models import Item

console = Console()


@register_output("email")
class EmailDigestOutput(BaseOutput):
    """Send email digest of items."""
    
    def __init__(self, output_config: Dict[str, Any], global_config: Dict[str, Any]):
        """Initialize email output.
        
        Args:
            output_config: Configuration with to, subject_template, etc.
            global_config: Global configuration including SMTP settings
        """
        super().__init__(output_config, global_config)
        
        # Email configuration
        self.to = output_config.get('to', '')
        self.subject_template = output_config.get('subject_template', '{name} - {date}')
        self.send_hour = output_config.get('send_hour', None)
        self.timezone = output_config.get('timezone', 'UTC')
        
        # SMTP configuration from global config
        email_config = global_config.get('email', {})
        self.smtp_host = email_config.get('smtp_host', 'smtp.gmail.com')
        self.smtp_port = email_config.get('smtp_port', 587)
        self.sender = email_config.get('sender', '')
        self.password = email_config.get('password', '')
        
        if not all([self.to, self.sender, self.password]):
            console.print("[yellow]Warning: Email configuration incomplete[/yellow]")
        
        # Setup Jinja2 template
        template_dir = Path(__file__).parent.parent / 'templates'
        self.jinja_env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(str(template_dir)),
            autoescape=True
        )
        self.template = self.jinja_env.get_template('email_digest.html')
    
    def send(self, items: List[Item], pipeline_name: str, stats: Dict[str, Any]) -> bool:
        """Send email digest of items.
        
        Args:
            items: List of items to send
            pipeline_name: Name of the pipeline
            stats: Pipeline execution statistics
            
        Returns:
            True if successful, False otherwise
        """
        if not self.should_send(items):
            return False
        
        if not all([self.to, self.sender, self.password]):
            console.print("[red]✗ Email output: Missing configuration[/red]")
            return False
        
        console.print(f"[cyan]Sending email digest to {self.to}...[/cyan]")
        
        try:
            # Filter out low relevance items
            min_relevance = self.output_config.get('min_relevance', 0.3)
            relevant_items = [i for i in items if i.relevance_score >= min_relevance]
            
            if not relevant_items:
                console.print("[yellow]No relevant items to send (all below relevance threshold)[/yellow]")
                return False
            
            # Build email content
            html_content = self._build_html(relevant_items, pipeline_name, stats)
            
            # Create email
            subject = self._build_subject(pipeline_name)
            message = self._create_message(subject, html_content)
            
            # Send email
            self._send_email(message)
            
            console.print(f"[green]✓ Email sent successfully to {self.to}[/green]")
            console.print(f"[dim]  Subject: {subject}[/dim]")
            console.print(f"[dim]  Items: {len(relevant_items)} (filtered from {len(items)})[/dim]")
            
            return True
            
        except Exception as e:
            console.print(f"[red]✗ Failed to send email: {e}[/red]")
            return False
    
    def _build_html(self, items: List[Item], pipeline_name: str, stats: Dict[str, Any]) -> str:
        """Build HTML content for email.
        
        Args:
            items: List of items to include
            pipeline_name: Name of the pipeline
            stats: Pipeline statistics
            
        Returns:
            HTML content string
        """
        # Group items by category
        items_by_category = {}
        for item in items:
            category = item.category or 'uncategorized'
            if category not in items_by_category:
                items_by_category[category] = []
            items_by_category[category].append(item)
        
        # Sort categories by importance
        category_order = [
            'pain_point', 'earnings_signal', 'important',
            'idea', 'project_launch', 'employee_sentiment',
            'lesson_learned', 'interesting', 'product_launch',
            'competitive', 'uncategorized', 'noise'
        ]
        
        sorted_categories = {}
        for category in category_order:
            if category in items_by_category:
                sorted_categories[category] = sorted(
                    items_by_category[category],
                    key=lambda x: x.relevance_score,
                    reverse=True
                )
        
        # Add any remaining categories
        for category, category_items in items_by_category.items():
            if category not in sorted_categories:
                sorted_categories[category] = sorted(
                    category_items,
                    key=lambda x: x.relevance_score,
                    reverse=True
                )
        
        # Category emojis
        category_emojis = {
            'pain_point': '😫',
            'idea': '💡',
            'project_launch': '🚀',
            'lesson_learned': '📚',
            'earnings_signal': '📈',
            'employee_sentiment': '👥',
            'product_launch': '📦',
            'competitive': '⚔️',
            'important': '⚠️',
            'interesting': '🤔',
            'uncategorized': '📝',
            'noise': '🔇'
        }
        
        # Render template
        html = self.template.render(
            pipeline_name=pipeline_name,
            date=datetime.now().strftime('%B %d, %Y'),
            items=items,
            items_by_category=sorted_categories,
            category_emojis=category_emojis,
            stats=stats,
            total_items=len(items)
        )
        
        return html
    
    def _build_subject(self, pipeline_name: str) -> str:
        """Build email subject from template.
        
        Args:
            pipeline_name: Name of the pipeline
            
        Returns:
            Email subject string
        """
        subject = self.subject_template.format(
            name=pipeline_name,
            date=datetime.now().strftime('%B %d, %Y'),
            day=datetime.now().strftime('%A'),
            time=datetime.now().strftime('%H:%M')
        )
        return subject
    
    def _create_message(self, subject: str, html_content: str) -> MIMEMultipart:
        """Create email message.
        
        Args:
            subject: Email subject
            html_content: HTML body content
            
        Returns:
            Email message object
        """
        message = MIMEMultipart('alternative')
        message['From'] = self.sender
        message['To'] = self.to
        message['Subject'] = subject
        
        # Create plain text version (simple fallback)
        text_content = f"""
{subject}

This email is best viewed in HTML format.
Please enable HTML viewing in your email client.

---
IntelFeed
        """
        
        # Attach parts
        text_part = MIMEText(text_content, 'plain')
        html_part = MIMEText(html_content, 'html')
        
        message.attach(text_part)
        message.attach(html_part)
        
        return message
    
    def _send_email(self, message: MIMEMultipart) -> None:
        """Send email via SMTP.
        
        Args:
            message: Email message to send
        """
        with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
            server.starttls()
            server.login(self.sender, self.password)
            server.send_message(message)