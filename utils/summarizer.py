import os
import re
import tiktoken
from openai import OpenAI
from typing import List, Dict, Tuple, Optional

class SummarizerError(Exception):
    """Custom exception for summarizer errors"""
    pass

class NewsSummarizer:
    """Summarizes news and extracts technical terms with explanations"""
    
    import os
import re
import tiktoken
from openai import OpenAI
from typing import List, Dict, Tuple, Optional

class SummarizerError(Exception):
    """Custom exception for summarizer errors"""
    pass

class NewsSummarizer:
    """Summarizes news and extracts technical terms with explanations"""
    
    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4o-mini"):
        self.client = OpenAI(api_key=api_key or os.getenv("OPENAI_API_KEY"))
        self.model = model
        # Remove self.encoding initialization here
    
    def count_tokens(self, text: str) -> int:
        """Count exact tokens using tiktoken"""
        # Initialize encoding inside the method
        # NOTE: This is less efficient but ensures the class is serializable.
        try:
            encoding = tiktoken.encoding_for_model(self.model)
            return len(encoding.encode(text))
        except Exception:
            # Fallback if model name is not recognized by tiktoken
            return 0
    
    def summarize_article(
        self, 
        article: Dict, 
        max_tokens: int = 150
    ) -> Dict:
        """
        Summarize a single news article
        
        Args:
            article: Article dictionary with title, description, content
            max_tokens: Maximum tokens for summary
        
        Returns:
            Dictionary with summary and token count
        """
        try:
            # Combine available text
            text_parts = [
                article.get("title", ""),
                article.get("description", ""),
                article.get("content", "")
            ]
            full_text = " ".join(filter(None, text_parts))
            
            if not full_text.strip():
                return {
                    "summary": "No content available to summarize.",
                    "tokens_used": 0
                }
            
            prompt = f"""Summarize the following news article concisely in 2-3 sentences:

{full_text[:2000]}  

Focus on the key facts and main points."""
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a concise news summarizer."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=max_tokens,
                temperature=0.3
            )
            
            summary = response.choices[0].message.content.strip()
            tokens_used = response.usage.total_tokens
            
            return {
                "summary": summary,
                "tokens_used": tokens_used
            }
            
        except Exception as e:
            raise SummarizerError(f"Summarization failed: {str(e)}")
    
    def extract_and_explain_terms(
        self, 
        article: Dict, 
        max_terms: int = 5
    ) -> Dict:
        """
        Extract technical terms and provide teacher-style explanations
        
        Args:
            article: Article dictionary
            max_terms: Maximum number of terms to extract
        
        Returns:
            Dictionary with terms and explanations
        """
        try:
            text_parts = [
                article.get("title", ""),
                article.get("description", ""),
                article.get("content", "")
            ]
            full_text = " ".join(filter(None, text_parts))
            
            prompt = f"""Analyze this news article and identify up to {max_terms} technical or specialized terms that might need explanation.

Article:
{full_text[:2000]}

For each term, provide:
1. The term itself
2. A clear, teacher-style explanation (2-3 sentences) suitable for someone learning about the topic

Format your response as:
TERM: [term name]
EXPLANATION: [explanation]

(Repeat for each term)"""
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a patient teacher explaining technical concepts clearly."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=500,
                temperature=0.5
            )
            
            content = response.choices[0].message.content
            
            # Parse terms and explanations
            terms = {}
            term_pattern = r"TERM:\s*(.+?)\s*EXPLANATION:\s*(.+?)(?=TERM:|$)"
            matches = re.findall(term_pattern, content, re.DOTALL | re.IGNORECASE)
            
            for term, explanation in matches:
                terms[term.strip()] = explanation.strip()
            
            return {
                "terms": terms,
                "tokens_used": response.usage.total_tokens
            }
            
        except Exception as e:
            raise SummarizerError(f"Term extraction failed: {str(e)}")
    
    def process_article(
        self, 
        article: Dict, 
        extract_terms: bool = False
    ) -> Dict:
        """
        Process article with summary and optional term extraction
        
        Returns:
            Complete processed article data
        """
        result = {
            "original": article,
            "summary": None,
            "terms": None,
            "total_tokens": 0
        }
        
        # Summarize
        summary_result = self.summarize_article(article)
        result["summary"] = summary_result["summary"]
        result["total_tokens"] += summary_result["tokens_used"]
        
        # Extract terms if requested
        if extract_terms:
            terms_result = self.extract_and_explain_terms(article)
            result["terms"] = terms_result["terms"]
            result["total_tokens"] += terms_result["tokens_used"]
        
        return result