# utils/news_fetcher.py
import os
import requests
from typing import List, Dict, Optional
from datetime import datetime, timedelta


class NewsFetcher:
    """
    Fetches news articles using NewsAPI.
    Supports both simple topic search and advanced LLM-generated queries.
    """

    def __init__(self):
        self.api_key = os.getenv("NEWS_API_KEY")
        self.endpoint = "https://newsapi.org/v2/everything"

        if not self.api_key:
            raise ValueError("NEWS_API_KEY is not set in environment variables.")

    def fetch_news(
        self,
        topic: Optional[str] = None,
        num_articles: int = 3,
        custom_query: Optional[str] = None
    ) -> List[Dict]:
        """
        Fetch news using either:
        - LLM-optimized custom query OR
        - simple topic query

        Returns articles in normalized format.
        """
        # Use custom query first, fall back to topic, then default
        query = custom_query if custom_query else topic
        
        if not query or query.strip() == "":
            query = "technology"  # Better default than "general news"
        
        # Clean up the query
        query = query.strip()
        
        # Add date range to get recent articles (last 7 days)
        from_date = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
        
        params = {
            "q": query,
            "from": from_date,
            "pageSize": min(num_articles, 100),  # NewsAPI max is 100
            "sortBy": "publishedAt",
            "language": "en",
            "apiKey": self.api_key
        }

        print(f"[NewsFetcher] Fetching with params: {params}")

        try:
            resp = requests.get(self.endpoint, params=params, timeout=12)
            resp.raise_for_status()
            data = resp.json()

            print(f"[NewsFetcher] API Response status: {data.get('status')}")
            print(f"[NewsFetcher] Total results: {data.get('totalResults', 0)}")

            if data.get("status") != "ok":
                error_msg = data.get("message", "Unknown error")
                print(f"[NewsFetcher] API Error: {error_msg}")
                return []

            raw_articles = data.get("articles", [])
            print(f"[NewsFetcher] Raw articles count: {len(raw_articles)}")
            
            if not raw_articles:
                print(f"[NewsFetcher] No articles found for query: {query}")
                return []
            
            normalized = [self._normalize_article(a) for a in raw_articles]
            filtered = [a for a in normalized if a is not None]
            
            print(f"[NewsFetcher] Normalized articles count: {len(filtered)}")
            return filtered

        except requests.exceptions.RequestException as e:
            print(f"[NewsFetcher] Request Error: {e}")
            return []
        except Exception as e:
            print(f"[NewsFetcher] Unexpected Error: {e}")
            return []

    def _normalize_article(self, article: dict) -> Optional[Dict]:
        """
        Converts a NewsAPI article format into standard structure.
        Returns None if article is invalid.
        """
        try:
            # Skip articles with [Removed] content
            title = article.get("title", "")
            if "[Removed]" in title or not title:
                return None
            
            content = article.get("content", "")
            description = article.get("description", "")
            
            # Skip if both content and description are empty
            if not content and not description:
                return None
            
            return {
                "title": title,
                "description": description,
                "content": content,
                "source": article.get("source", {}).get("name", "Unknown"),
                "url": article.get("url", ""),
                "published_at": article.get("publishedAt", ""),
            }
        except Exception as e:
            print(f"[NewsFetcher] Error normalizing article: {e}")
            return None