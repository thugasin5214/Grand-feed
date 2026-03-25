"""Database operations for IntelFeed."""

import sqlite3
import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from rich.console import Console

from intel_feed.models import Item

console = Console()


class Database:
    """SQLite database for storing items and pipeline state."""
    
    def __init__(self, db_path: str = "data/intel_feed.db"):
        """Initialize database connection.
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row  # Enable column access by name
        
        self._create_tables()
    
    def _create_tables(self):
        """Create database tables if they don't exist."""
        cursor = self.conn.cursor()
        
        # Items table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS items (
                id TEXT PRIMARY KEY,
                source TEXT NOT NULL,
                title TEXT NOT NULL,
                body TEXT,
                url TEXT,
                author TEXT,
                score INTEGER DEFAULT 0,
                num_comments INTEGER DEFAULT 0,
                created_at TIMESTAMP,
                collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                
                -- Processing fields
                pipeline TEXT,
                category TEXT DEFAULT 'uncategorized',
                sentiment TEXT DEFAULT 'neutral',
                relevance_score REAL DEFAULT 0.0,
                ai_summary TEXT,
                ai_opportunity TEXT,
                entities TEXT,  -- JSON array
                tags TEXT,  -- JSON array
                
                -- Source-specific
                subreddit TEXT,
                feed TEXT,
                
                -- Status
                sent BOOLEAN DEFAULT 0
            )
        """)
        
        # Pipeline runs table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pipeline_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pipeline_name TEXT NOT NULL,
                started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP,
                items_collected INTEGER DEFAULT 0,
                items_after_filter INTEGER DEFAULT 0,
                items_after_dedup INTEGER DEFAULT 0,
                items_classified INTEGER DEFAULT 0,
                items_sent INTEGER DEFAULT 0,
                errors TEXT
            )
        """)
        
        # Create indexes separately (SQLite syntax)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_created_at ON items (created_at)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_pipeline ON items (pipeline)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sent ON items (sent)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_pipeline_name ON pipeline_runs (pipeline_name)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_started_at ON pipeline_runs (started_at)")
        
        self.conn.commit()
    
    def save_item(self, item: Item) -> bool:
        """Save an item to the database.
        
        Args:
            item: Item to save
            
        Returns:
            True if saved successfully
        """
        cursor = self.conn.cursor()
        
        try:
            cursor.execute("""
                INSERT OR REPLACE INTO items (
                    id, source, title, body, url, author, score, num_comments,
                    created_at, collected_at, pipeline, category, sentiment,
                    relevance_score, ai_summary, ai_opportunity, entities, tags,
                    subreddit, feed, sent
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                item.id,
                item.source,
                item.title,
                item.body,
                item.url,
                item.author,
                item.score,
                item.num_comments,
                item.created_at,
                item.collected_at,
                item.pipeline,
                item.category,
                item.sentiment,
                item.relevance_score,
                item.ai_summary,
                item.ai_opportunity,
                json.dumps(item.entities),
                json.dumps(item.tags),
                item.subreddit,
                item.feed,
                item.sent
            ))
            
            self.conn.commit()
            return True
            
        except sqlite3.Error as e:
            console.print(f"[red]Database error saving item {item.id}: {e}[/red]")
            return False
    
    def save_items(self, items: List[Item]) -> int:
        """Save multiple items to the database.
        
        Args:
            items: List of items to save
            
        Returns:
            Number of items saved successfully
        """
        saved = 0
        for item in items:
            if self.save_item(item):
                saved += 1
        
        console.print(f"[dim]Saved {saved}/{len(items)} items to database[/dim]")
        return saved
    
    def get_item(self, item_id: str) -> Optional[Dict[str, Any]]:
        """Get an item by ID.
        
        Args:
            item_id: Item ID
            
        Returns:
            Item data as dictionary or None
        """
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM items WHERE id = ?", (item_id,))
        row = cursor.fetchone()
        
        if row:
            return dict(row)
        return None
    
    def get_recent_items(self, days: int = 7, pipeline: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get recent items from the database.
        
        Args:
            days: Number of days to look back
            pipeline: Optional pipeline name filter
            
        Returns:
            List of item dictionaries
        """
        cursor = self.conn.cursor()
        cutoff = datetime.utcnow() - timedelta(days=days)
        
        if pipeline:
            cursor.execute("""
                SELECT * FROM items 
                WHERE collected_at >= ? AND pipeline = ?
                ORDER BY collected_at DESC
            """, (cutoff, pipeline))
        else:
            cursor.execute("""
                SELECT * FROM items 
                WHERE collected_at >= ?
                ORDER BY collected_at DESC
            """, (cutoff,))
        
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    
    def get_unsent_items(self, pipeline: Optional[str] = None, 
                        min_relevance: float = 0.0) -> List[Dict[str, Any]]:
        """Get unsent items from the database.
        
        Args:
            pipeline: Optional pipeline name filter
            min_relevance: Minimum relevance score
            
        Returns:
            List of item dictionaries
        """
        cursor = self.conn.cursor()
        
        if pipeline:
            cursor.execute("""
                SELECT * FROM items 
                WHERE sent = 0 AND relevance_score >= ? AND pipeline = ?
                ORDER BY relevance_score DESC, created_at DESC
            """, (min_relevance, pipeline))
        else:
            cursor.execute("""
                SELECT * FROM items 
                WHERE sent = 0 AND relevance_score >= ?
                ORDER BY relevance_score DESC, created_at DESC
            """, (min_relevance,))
        
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    
    def mark_items_sent(self, item_ids: List[str]) -> int:
        """Mark items as sent.
        
        Args:
            item_ids: List of item IDs to mark as sent
            
        Returns:
            Number of items marked
        """
        cursor = self.conn.cursor()
        
        for item_id in item_ids:
            cursor.execute("""
                UPDATE items SET sent = 1 WHERE id = ?
            """, (item_id,))
        
        self.conn.commit()
        return cursor.rowcount
    
    def update_item_classification(self, item_id: str, category: str, 
                                  relevance_score: float, 
                                  ai_summary: str = "",
                                  ai_opportunity: str = "") -> bool:
        """Update item classification results.
        
        Args:
            item_id: Item ID
            category: Classification category
            relevance_score: Relevance score (0-1)
            ai_summary: AI-generated summary
            ai_opportunity: AI-identified opportunity
            
        Returns:
            True if updated successfully
        """
        cursor = self.conn.cursor()
        
        try:
            cursor.execute("""
                UPDATE items 
                SET category = ?, relevance_score = ?, 
                    ai_summary = ?, ai_opportunity = ?
                WHERE id = ?
            """, (category, relevance_score, ai_summary, ai_opportunity, item_id))
            
            self.conn.commit()
            return cursor.rowcount > 0
            
        except sqlite3.Error as e:
            console.print(f"[red]Database error updating item {item_id}: {e}[/red]")
            return False
    
    def save_pipeline_run(self, stats: Dict[str, Any]) -> bool:
        """Save pipeline run statistics.
        
        Args:
            stats: Pipeline statistics dictionary
            
        Returns:
            True if saved successfully
        """
        cursor = self.conn.cursor()
        
        try:
            cursor.execute("""
                INSERT INTO pipeline_runs (
                    pipeline_name, started_at, completed_at,
                    items_collected, items_after_filter, items_after_dedup,
                    items_classified, items_sent, errors
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                stats.get('pipeline_name'),
                stats.get('start_time'),
                stats.get('end_time'),
                stats.get('items_collected', 0),
                stats.get('items_after_filter', 0),
                stats.get('items_after_dedup', 0),
                stats.get('items_classified', 0),
                stats.get('items_sent', 0),
                json.dumps(stats.get('errors', []))
            ))
            
            self.conn.commit()
            return True
            
        except sqlite3.Error as e:
            console.print(f"[red]Database error saving pipeline run: {e}[/red]")
            return False
    
    def close(self):
        """Close database connection."""
        self.conn.close()