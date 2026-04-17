import os
from openai import OpenAI
from typing import Dict, Tuple, Optional, List

class ModerationError(Exception):
    """Custom exception for moderation errors"""
    pass

class ContentModerator:
    """Moderates user input using OpenAI Moderation API"""
    
    def __init__(self, api_key: Optional[str] = None):
        self.client = OpenAI(api_key=api_key or os.getenv("OPENAI_API_KEY"))
    
    def check_content(self, text: str) -> Tuple[bool, Dict]:
        """
        Check if content is appropriate
        
        Args:
            text: Text to moderate
        
        Returns:
            Tuple of (is_safe: bool, details: dict)
        """
        try:
            response = self.client.moderations.create(input=text)
            result = response.results[0]
            
            is_safe = not result.flagged
            
            details = {
                "flagged": result.flagged,
                "categories": {
                    category: getattr(result.categories, category)
                    for category in dir(result.categories)
                    if not category.startswith("_")
                },
                "category_scores": {
                    category: getattr(result.category_scores, category)
                    for category in dir(result.category_scores)
                    if not category.startswith("_")
                }
            }
            
            return is_safe, details
            
        except Exception as e:
            raise ModerationError(f"Moderation check failed: {str(e)}")
    
    def get_flagged_categories(self, details: Dict) -> List[str]:
        """Get list of flagged categories"""
        return [
            category for category, flagged in details.get("categories", {}).items()
            if flagged
        ]