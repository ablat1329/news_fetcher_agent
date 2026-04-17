# config.py
"""
Configuration management for AI News Agent
Handles paths consistently across local and Docker environments
"""

import os
from pathlib import Path
from typing import Optional

# ✅ Determine base directory
BASE_DIR = Path(__file__).resolve().parent

# ✅ Data directories
DATA_DIR = BASE_DIR / "data"
LOGS_DIR = BASE_DIR / "logs"
CACHE_DIR = BASE_DIR / "cache"

# ✅ Database
DB_PATH = DATA_DIR / "news_agent.db"

# ✅ Visualization
DOCS_DIR = BASE_DIR / "docs"
GRAPH_OUTPUT = DOCS_DIR / "workflow_graph.png"

# ✅ Create all directories
for directory in [DATA_DIR, LOGS_DIR, CACHE_DIR, DOCS_DIR]:
    directory.mkdir(parents=True, exist_ok=True)


class Config:
    """Application configuration"""
    
    # Paths
    BASE_DIR = BASE_DIR
    DATA_DIR = DATA_DIR
    LOGS_DIR = LOGS_DIR
    CACHE_DIR = CACHE_DIR
    DOCS_DIR = DOCS_DIR
    DB_PATH = DB_PATH
    GRAPH_OUTPUT = GRAPH_OUTPUT
    
    # API Configuration
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    NEWS_API_KEY = os.getenv("NEWS_API_KEY")
    NEWS_API_URL = os.getenv("NEWS_API_URL", "https://newsapi.org/v2")
    
    # Email Configuration
    SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
    SMTP_EMAIL = os.getenv("SMTP_EMAIL")
    SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
    
    # Application Settings
    ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    MAX_ARTICLES = int(os.getenv("MAX_ARTICLES", "10"))
    
    # LLM Settings
    DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    DEFAULT_TEMPERATURE = float(os.getenv("OPENAI_TEMPERATURE", "0.3"))
    
    @classmethod
    def validate(cls) -> bool:
        """Validate required configuration"""
        required = [
            ("OPENAI_API_KEY", cls.OPENAI_API_KEY),
            ("NEWS_API_KEY", cls.NEWS_API_KEY),
        ]
        
        missing = [name for name, value in required if not value]
        
        if missing:
            raise ValueError(f"Missing required config: {', '.join(missing)}")
        
        return True
    
    @classmethod
    def get_db_path(cls, custom_path: Optional[str] = None) -> Path:
        """Get database path, ensuring it exists"""
        if custom_path:
            path = Path(custom_path)
        else:
            path = cls.DB_PATH
        
        path.parent.mkdir(parents=True, exist_ok=True)
        return path
    
    @classmethod
    def info(cls):
        """Print configuration info"""
        print("🔧 Configuration:")
        print(f"  Base Dir: {cls.BASE_DIR}")
        print(f"  Data Dir: {cls.DATA_DIR}")
        print(f"  DB Path: {cls.DB_PATH}")
        print(f"  Environment: {cls.ENVIRONMENT}")
        print(f"  Model: {cls.DEFAULT_MODEL}")
        print(f"  API Keys: {'✅' if cls.OPENAI_API_KEY else '❌'} OpenAI, {'✅' if cls.NEWS_API_KEY else '❌'} News")


# Validate on import (optional)
if __name__ != "__main__":
    try:
        Config.validate()
    except ValueError as e:
        print(f"⚠️  Config warning: {e}")