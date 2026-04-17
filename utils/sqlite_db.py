import sqlite3
from typing import Dict, List, Optional
from datetime import datetime
import os


class SQLiteTermDB:
    """SQLite database for storing and retrieving technical terms"""
    
    def __init__(self, db_path: str):
        """
        Initialize SQLite connection.
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        
        # Ensure directory exists
        db_dir = os.path.dirname(db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
        
        self._create_tables()
    
    def _get_connection(self):
        """Get SQLite connection"""
        try:
            connection = sqlite3.connect(self.db_path)
            connection.row_factory = sqlite3.Row
            return connection
        except sqlite3.Error as e:
            print(f"Error connecting to SQLite: {e}")
            raise
    
    def _create_tables(self):
        """Create necessary tables if they don't exist"""
        connection = None
        try:
            connection = self._get_connection()
            cursor = connection.cursor()
            
            # Terms table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS terms (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    term TEXT NOT NULL,
                    explanation TEXT NOT NULL,
                    article_id TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create indexes
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_term ON terms(term)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_article ON terms(article_id)
            """)
            
            # Articles metadata table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS articles (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    source TEXT,
                    url TEXT,
                    published_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            connection.commit()
            print(f"Database tables created successfully at {self.db_path}")
            
        except sqlite3.Error as e:
            print(f"Error creating tables: {e}")
            raise
        finally:
            if connection:
                connection.close() # <--- Ensure connection is closed here
    
    def add_terms(self, terms: Dict[str, str], article_id: str, article_metadata: Optional[Dict] = None):
        """
        Add terms to the database.
        
        Args:
            terms: Dictionary of term -> explanation
            article_id: Unique identifier for the article
            article_metadata: Optional metadata about the article
        """
        connection = None
        try:
            connection = self._get_connection()
            cursor = connection.cursor()
            
            # Insert article metadata if provided
            if article_metadata:
                cursor.execute("""
                    INSERT OR REPLACE INTO articles (id, title, source, url, published_at)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    article_id,
                    article_metadata.get('title', ''),
                    article_metadata.get('source', ''),
                    article_metadata.get('url', ''),
                    article_metadata.get('published_at')
                ))
            
            # Insert terms
            for term, explanation in terms.items():
                cursor.execute("""
                    INSERT INTO terms (term, explanation, article_id)
                    VALUES (?, ?, ?)
                """, (term, explanation, article_id))
            
            connection.commit()
            print(f"Added {len(terms)} terms for article {article_id}")
            
        except sqlite3.Error as e:
            print(f"Error adding terms: {e}")
            if connection:
                connection.rollback()
            raise
        finally:
            if connection:
                connection.close()
    
    def search_terms(self, query: str, limit: int = 10) -> List[Dict]:
        """
        Search for terms matching the query.
        
        Args:
            query: Search term
            limit: Maximum number of results
            
        Returns:
            List of matching terms with explanations
        """
        connection = None
        try:
            connection = self._get_connection()
            cursor = connection.cursor()
            
            cursor.execute("""
                SELECT term, explanation, article_id, created_at
                FROM terms
                WHERE term LIKE ?
                ORDER BY created_at DESC
                LIMIT ?
            """, (f"%{query}%", limit))
            
            results = [dict(row) for row in cursor.fetchall()]
            return results
            
        except sqlite3.Error as e:
            print(f"Error searching terms: {e}")
            return []
        finally:
            if connection:
                connection.close()
    
    def get_article_terms(self, article_id: str) -> Dict[str, str]:
        """
        Get all terms for a specific article.
        
        Args:
            article_id: Article identifier
            
        Returns:
            Dictionary of term -> explanation
        """
        connection = None
        try:
            connection = self._get_connection()
            cursor = connection.cursor()
            
            cursor.execute("""
                SELECT term, explanation
                FROM terms
                WHERE article_id = ?
            """, (article_id,))
            
            results = cursor.fetchall()
            return {row['term']: row['explanation'] for row in results}
            
        except sqlite3.Error as e:
            print(f"Error getting article terms: {e}")
            return {}
        finally:
            if connection:
                connection.close()
    
    def get_all_terms(self, limit: int = 100) -> List[Dict]:
        """
        Get all terms from the database.
        
        Args:
            limit: Maximum number of terms to retrieve
            
        Returns:
            List of term dictionaries
        """
        connection = None
        try:
            connection = self._get_connection()
            cursor = connection.cursor()
            
            cursor.execute("""
                SELECT term, explanation, article_id, created_at
                FROM terms
                ORDER BY created_at DESC
                LIMIT ?
            """, (limit,))
            
            results = [dict(row) for row in cursor.fetchall()]
            return results
            
        except sqlite3.Error as e:
            print(f"Error getting all terms: {e}")
            return []
        finally:
            if connection:
                connection.close()
    
    def clear_old_terms(self, days: int = 30):
        """
        Clear terms older than specified days.
        
        Args:
            days: Number of days to keep
        """
        connection = None
        try:
            connection = self._get_connection()
            cursor = connection.cursor()
            
            cursor.execute("""
                DELETE FROM terms
                WHERE created_at < datetime('now', '-' || ? || ' days')
            """, (days,))
            
            deleted = cursor.rowcount
            connection.commit()
            print(f"Deleted {deleted} old terms")
            
        except sqlite3.Error as e:
            print(f"Error clearing old terms: {e}")
            if connection:
                connection.rollback()
        finally:
            if connection:
                connection.close()