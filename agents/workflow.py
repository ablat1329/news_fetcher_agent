# agents/workflow.py

import os
import re
import json
from typing import Dict, Optional, List, TypedDict, Annotated
from operator import add
from pathlib import Path

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langchain_openai import ChatOpenAI

from utils.moderation import ContentModerator
from utils.news_fetcher import NewsFetcher
from utils.summarizer import NewsSummarizer
from utils.sqlite_db import SQLiteTermDB
from utils.emailer import NewsEmailer

# ✅ Docker-compatible path handling
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)


# -------------------------------------------------------------------
# State (MUST be msgpack-serializable)
# -------------------------------------------------------------------
class ConversationState(TypedDict):
    user_message: str
    agent_response: str

    topic: Optional[str]
    num_articles: int
    extract_terms: bool

    send_email: bool
    recipient_email: Optional[str]
    email_sent: bool

    intent: Optional[str]

    moderation_passed: bool
    moderation_details: Dict

    search_query: Optional[str]

    articles: List[Dict]
    processed_articles: List[Dict]

    # ✅ These persist across runs
    last_topic: Optional[str]
    last_articles: List[Dict]
    last_processed_articles: List[Dict]

    # ✅ Use Annotated to accumulate messages
    processing_messages: Annotated[List[str], add]
    errors: Annotated[List[str], add]


# -------------------------------------------------------------------
def sanitize(obj):
    """Ensure msgpack-safe serialization"""
    return json.loads(json.dumps(obj, default=str))


# -------------------------------------------------------------------
class ConversationalNewsAgent:

    DEFAULT_CONFIG = {
        "num_articles": 3,
        "temperature": 0.3,
        "model": "gpt-4o-mini"
    }

    PROMPTS = {
        "parameter_extraction": """Extract info from this request:

User message: "{user_message}"

Respond EXACTLY:
TOPIC: <topic>
NUMBER: <number>
EXTRACT_TERMS: <yes/no>
EMAIL: <email or none>""",

        "query_generation": """Create a short news search query (2–5 words) for: {topic}

Important: Return ONLY the search keywords without any quotes, punctuation, or extra formatting.

Examples:
- Topic: "AI news" → artificial intelligence news
- Topic: "LLM developments" → language models AI
- Topic: "climate change" → climate change news

Your query:""",

        "email_extraction": """Extract the email address from this message:

User message: "{user_message}"

Respond EXACTLY in this format:
EMAIL: <email_address>

If no email found, respond:
EMAIL: none"""
    }

    # -------------------------------------------------------------------
    def __init__(self, db_path: Optional[str] = None):
        self.llm = ChatOpenAI(
            model=self.DEFAULT_CONFIG["model"],
            temperature=self.DEFAULT_CONFIG["temperature"],
            api_key=os.getenv("OPENAI_API_KEY")
        )

        self.moderator = ContentModerator()
        self.news_fetcher = NewsFetcher()
        self.summarizer = NewsSummarizer()

        # ✅ Use pathlib for database path (Docker-compatible)
        if db_path:
            self.db_path = Path(db_path)
        else:
            self.db_path = DATA_DIR / "news_agent.db"
        
        # Ensure parent directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        self.term_db = SQLiteTermDB(str(self.db_path))

        try:
            self.emailer = NewsEmailer()
        except ValueError:
            self.emailer = None

        self.memory = MemorySaver()
        self.workflow = self._build_workflow()
        
        print(f"📁 Database path: {self.db_path.absolute()}")
        print(f"📁 Data directory: {DATA_DIR.absolute()}")

    # -------------------------------------------------------------------
    def _build_workflow(self):
        g = StateGraph(ConversationState)

        g.add_node("moderate", self._moderate_input)
        g.add_node("intent", self._detect_intent)
        g.add_node("parse", self._parse_request)
        g.add_node("query", self._generate_search_query)
        g.add_node("fetch", self._fetch_news)
        g.add_node("process", self._process_articles)
        g.add_node("store_terms", self._store_terms)
        g.add_node("handle_article_detail", self.handle_article_detail)
        g.add_node("handle_email", self.handle_email)

        g.set_entry_point("moderate")

        g.add_conditional_edges(
            "moderate",
            lambda s: "ok" if s["moderation_passed"] else "bad",
            {"ok": "intent", "bad": END}
        )

        g.add_conditional_edges(
            "intent",
            lambda s: s["intent"],
            {
                "fetch_news": "parse",
                "extract_terms": "parse",
                "article_detail": "handle_article_detail",
                "send_email": "handle_email",
                "unknown": END,
            }
        )
        g.add_edge("handle_article_detail", END)
        g.add_edge("handle_email", END)
        g.add_edge("parse", "query")
        g.add_edge("query", "fetch")
        g.add_edge("fetch", "process")
        g.add_edge("process", "store_terms")
        g.add_edge("store_terms", END)

        return g.compile(checkpointer=self.memory)

    # -------------------------------------------------------------------
    def _moderate_input(self, state: ConversationState):
        ok, details = self.moderator.check_content(state["user_message"])
        state["moderation_passed"] = ok
        state["moderation_details"] = sanitize(details)
        return state

    def _detect_intent(self, state: ConversationState):
        prompt = f"""
Classify the user's intent.

User message:
"{state['user_message']}"

Choose ONE intent:
- fetch_news (new articles are requested)
- article_detail (user asks about a previously shown article)
- extract_terms (user asks to extract/explain terms from articles)
- send_email (user wants to send/email the articles or summary)
- unknown

Respond EXACTLY in this format:
INTENT: <intent>
"""

        resp = self.llm.invoke(prompt).content.strip()

        match = re.search(r"INTENT:\s*(\w+)", resp, re.I)
        intent = match.group(1).lower() if match else "unknown"

        state["intent"] = intent
        print(f"🎯 Detected intent: {intent}")
        return state

    def _parse_request(self, state: ConversationState):
        resp = self.llm.invoke(
            self.PROMPTS["parameter_extraction"].format(
                user_message=state["user_message"]
            )
        ).content

        topic_match = re.search(r"TOPIC:\s*(.+)", resp)
        number_match = re.search(r"NUMBER:\s*(\d+)", resp)
        extract_match = re.search(r"EXTRACT_TERMS:\s*(yes|no)", resp, re.I)

        if topic_match:
            state["topic"] = topic_match.group(1).strip()

        if number_match:
            state["num_articles"] = int(number_match.group(1))

        if extract_match:
            state["extract_terms"] = extract_match.group(1).lower() == "yes"

        return state

    def _generate_search_query(self, state: ConversationState):
        topic = state["topic"].lower()

        expansions = {
            "llm": "large language model",
            "ai": "artificial intelligence",
            "ml": "machine learning",
        }

        if topic in expansions:
            state["search_query"] = expansions[topic]
        else:
            query = self.llm.invoke(
                self.PROMPTS["query_generation"].format(topic=state["topic"])
            ).content.strip()
            
            # ✅ Clean up the query - remove quotes, extra spaces
            query = query.strip('"').strip("'").strip()
            query = re.sub(r'\s+', ' ', query)  # normalize spaces
            
            state["search_query"] = query
        
        print(f"🔍 Search query generated: '{state['search_query']}' for topic '{state['topic']}'")
        
        return state

    def _fetch_news(self, state: ConversationState):
        articles = self.news_fetcher.fetch_news(
            topic=state["topic"],
            num_articles=state["num_articles"],
            custom_query=state["search_query"]
        )
        
        # ✅ Add debugging/logging
        if not articles:
            print(f"⚠️  No articles found for topic='{state['topic']}', query='{state['search_query']}'")
            state["errors"].append(f"No articles found for '{state['topic']}'")
        
        state["articles"] = sanitize(articles or [])
        return state

    def _process_articles(self, state: ConversationState):
        # ✅ Handle empty articles case
        if not state["articles"]:
            state["agent_response"] = f"❌ Sorry, I couldn't find any articles about '{state['topic']}'. Please try a different topic."
            state["processed_articles"] = []
            return state
        
        processed = []

        for article in state["articles"]:
            processed.append(
                self.summarizer.process_article(
                    article,
                    extract_terms=state["extract_terms"]
                )
            )

        state["processed_articles"] = sanitize(processed)
        state["last_articles"] = list(state["articles"])
        state["last_topic"] = state["topic"]
        state["last_processed_articles"] = list(processed)

        # ✅ Build full response
        response = f"📰 **Top {len(processed)} articles about {state['topic']}**\n\n"

        for i, p in enumerate(processed, 1):
            title = p["original"].get("title", "Untitled")
            summary = p.get("summary", "")

            response += f"### {i}. {title}\n"
            response += f"{summary}\n\n"

            # ✅ Show extracted terms
            if state["extract_terms"] and p.get("terms"):
                response += "**Background / Technical Terms:**\n"
                for term, expl in p["terms"].items():
                    response += f"- **{term}**: {expl}\n"
                response += "\n"

        state["agent_response"] = response
        return state

    def _store_terms(self, state: ConversationState):
        for p in state["processed_articles"]:
            if p.get("terms"):
                self.term_db.add_terms(
                    p["terms"],
                    f"id_{os.urandom(4).hex()}",
                    {"title": p["original"]["title"]}
                )
        return state
    
    def handle_article_detail(self, state: ConversationState):
        msg = state["user_message"].lower()

        # ✅ Debug print
        print(f"🔍 Looking for article in last_articles: {len(state.get('last_articles', []))} articles")
        if state.get("last_articles"):
            for i, a in enumerate(state["last_articles"]):
                print(f"  [{i}] {a.get('title', 'No title')[:50]}")

        index_map = {
            "first": 0,
            "1st": 0,
            "second": 1,
            "2nd": 1,
            "third": 2,
            "3rd": 2,
        }

        idx = None
        for k, v in index_map.items():
            if k in msg:
                idx = v
                break

        if idx is None:
            state["agent_response"] = "Please specify which article (first, second, or third)."
            return state

        if not state.get("last_articles") or idx >= len(state["last_articles"]):
            state["agent_response"] = f"I couldn't find article #{idx+1}. I only have {len(state.get('last_articles', []))} articles in memory."
            return state

        article = state["last_articles"][idx]
        processed = self.summarizer.process_article(article, extract_terms=True)

        response = f"### {article.get('title','Untitled')}\n\n"
        response += processed.get("summary", "") + "\n\n"

        if processed.get("terms"):
            response += "**Background Terms:**\n"
            for t, e in processed["terms"].items():
                response += f"- **{t}**: {e}\n"

        state["agent_response"] = response
        return state

    def handle_email(self, state: ConversationState):
        """Handle email sending requests"""
        
        # Check if emailer is configured
        if not self.emailer:
            state["agent_response"] = "❌ Email functionality is not configured. Please set up SMTP settings."
            return state

        # Check if we have articles to send
        if not state.get("last_processed_articles") and not state.get("last_articles"):
            state["agent_response"] = "❌ No articles to send. Please fetch some news first."
            return state

        # Extract email address
        email_resp = self.llm.invoke(
            self.PROMPTS["email_extraction"].format(
                user_message=state["user_message"]
            )
        ).content.strip()

        email_match = re.search(r"EMAIL:\s*(.+)", email_resp)
        recipient_email = None
        
        if email_match:
            email_str = email_match.group(1).strip()
            if email_str.lower() != "none" and "@" in email_str:
                recipient_email = email_str

        if not recipient_email:
            state["agent_response"] = "❌ Please provide a valid email address. Example: 'Send to john@example.com'"
            return state

        # Use last processed articles or process them now
        articles_to_send = state.get("last_processed_articles", [])
        
        if not articles_to_send and state.get("last_articles"):
            # Process articles if not already processed
            articles_to_send = [
                self.summarizer.process_article(article, extract_terms=True)
                for article in state["last_articles"]
            ]

        if not articles_to_send:
            state["agent_response"] = "❌ No articles available to send."
            return state

        try:
            # ✅ Use the correct method name: send_news_summary
            success = self.emailer.send_news_summary(
                articles_data=articles_to_send,
                recipient=recipient_email,
                topic=state.get("last_topic", "Latest News")
            )

            if success:
                state["email_sent"] = True
                state["recipient_email"] = recipient_email
                state["agent_response"] = f"✅ Successfully sent {len(articles_to_send)} article summaries to {recipient_email}!"
            else:
                state["agent_response"] = "❌ Failed to send email. Please check the email address and try again."
                
        except Exception as e:
            state["agent_response"] = f"❌ Error sending email: {str(e)}"
            state["errors"].append(f"Email error: {str(e)}")
            print(f"❌ Email error details: {e}")

        return state

    # -------------------------------------------------------------------
    def run(self, user_message: str, thread_id="default"):
        config = {"configurable": {"thread_id": thread_id}}
        
        # ✅ Just pass the new message - LangGraph handles state persistence
        input_state = {
            "user_message": user_message,
        }

        return self.workflow.invoke(input_state, config)

    # -------------------------------------------------------------------
    def visualize_graph(self, output_path: Optional[str] = None):
        """
        Visualize the workflow graph and save as PNG
        
        Args:
            output_path: Path to save the graph image
        
        Returns:
            Path to the saved image
        """
        # ✅ Use pathlib for output path
        if output_path is None:
            docs_dir = BASE_DIR / "docs"
            docs_dir.mkdir(parents=True, exist_ok=True)
            output_path = docs_dir / "workflow_graph.png"
        else:
            output_path = Path(output_path)
        
        # Ensure parent directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            # Generate the graph visualization
            graph_png = self.workflow.get_graph().draw_mermaid_png()
            
            # Save to file
            with open(output_path, 'wb') as f:
                f.write(graph_png)
            
            print(f"✅ Graph saved to {output_path.absolute()}")
            return str(output_path)
            
        except Exception as e:
            print(f"❌ Error generating graph: {e}")
            print("💡 Make sure you have graphviz installed:")
            print("   - Mac: brew install graphviz")
            print("   - Ubuntu: sudo apt-get install graphviz")
            print("   - Windows: Download from https://graphviz.org/download/")
            return None

    