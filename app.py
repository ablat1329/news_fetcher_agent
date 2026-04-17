# app.py
import streamlit as st
import os
from dotenv import load_dotenv
from agents.workflow import ConversationalNewsAgent
import uuid

# Load environment variables
load_dotenv()

# Page configuration
st.set_page_config(
    page_title="Conversational News Agent",
    page_icon="📰",
    layout="wide"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
    }
    .chat-message {
        padding: 1.5rem;
        border-radius: 0.5rem;
        margin-bottom: 1rem;
        display: flex;
        flex-direction: column;
    }
    .user-message {
        background-color: #e3f2fd;
        border-left: 5px solid #2196f3;
    }
    .assistant-message {
        background-color: #f5f5f5;
        border-left: 5px solid #4caf50;
    }
    .message-label {
        font-weight: bold;
        margin-bottom: 0.5rem;
    }
    .user-label {
        color: #2196f3;
    }
    .assistant-label {
        color: #4caf50;
    }
    .stButton button {
        background-color: #1f77b4;
        color: white;
        border-radius: 5px;
        padding: 0.5rem 2rem;
        font-size: 1rem;
    }
    .stButton button:hover {
        background-color: #155a8a;
    }
    .info-box {
        background-color: #fff3cd;
        border-left: 5px solid #ffc107;
        padding: 1rem;
        border-radius: 0.5rem;
        margin-bottom: 1rem;
    }
    .success-box {
        background-color: #d4edda;
        border-left: 5px solid #28a745;
        padding: 1rem;
        border-radius: 0.5rem;
        margin-bottom: 1rem;
    }
    .error-box {
        background-color: #f8d7da;
        border-left: 5px solid #dc3545;
        padding: 1rem;
        border-radius: 0.5rem;
        margin-bottom: 1rem;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if "messages" not in st.session_state:
    st.session_state.messages = []

if "agent" not in st.session_state:
    with st.spinner("Initializing News Agent..."):
        try:
            st.session_state.agent = ConversationalNewsAgent()
            st.session_state.agent_ready = True
        except Exception as e:
            st.error(f"Failed to initialize agent: {str(e)}")
            st.session_state.agent_ready = False

if "thread_id" not in st.session_state:
    st.session_state.thread_id = str(uuid.uuid4())
    print(f"[App] Created new thread_id: {st.session_state.thread_id}")

# Header
st.markdown('<h1 class="main-header">📰 Conversational News Agent</h1>', unsafe_allow_html=True)

# Sidebar
with st.sidebar:
    st.header("ℹ️ About")
    st.write("""
    This intelligent news agent can:
    - 🔍 Fetch latest news articles
    - 📝 Provide summaries
    - 🔤 Extract and explain technical terms
    - 📧 Send articles via email
    - 💬 Have contextual conversations
    """)
    
    st.header("🎯 Example Queries")
    st.code("Give me top 3 AI news")
    st.code("Tell me more about the first article")
    st.code("Extract terms from article 2")
    st.code("Send these to my email")
    
    st.header("🔧 Session Info")
    st.write(f"**Thread ID:** `{st.session_state.thread_id[:8]}...`")
    st.write(f"**Messages:** {len(st.session_state.messages)}")
    
    if st.button("🔄 New Conversation"):
        st.session_state.messages = []
        st.session_state.thread_id = str(uuid.uuid4())
        print(f"[App] Started new conversation with thread_id: {st.session_state.thread_id}")
        st.rerun()

# Main chat interface
if not st.session_state.get("agent_ready", False):
    st.error("❌ Agent not ready. Please check your environment variables and restart.")
    st.stop()

# Display chat history
for message in st.session_state.messages:
    if message["role"] == "user":
        st.markdown(f"""
        <div class="chat-message user-message">
            <div class="message-label user-label">You:</div>
            <div>{message["content"]}</div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown(f"""
        <div class="chat-message assistant-message">
            <div class="message-label assistant-label">Assistant:</div>
            <div>{message["content"]}</div>
        </div>
        """, unsafe_allow_html=True)

# Input form
with st.form(key="chat_form", clear_on_submit=True):
    col1, col2 = st.columns([5, 1])
    
    with col1:
        user_input = st.text_input(
            "Your message:",
            placeholder="Ask me to fetch news, explain articles, or extract terms...",
            label_visibility="collapsed"
        )
    
    with col2:
        submit_button = st.form_submit_button("Send 📤")

if submit_button and user_input:
    # Add user message to history
    st.session_state.messages.append({"role": "user", "content": user_input})
    
    # Display user message immediately
    st.markdown(f"""
    <div class="chat-message user-message">
        <div class="message-label user-label">You:</div>
        <div>{user_input}</div>
    </div>
    """, unsafe_allow_html=True)
    
    # Show processing indicator
    with st.spinner("🤔 Processing..."):
        try:
            # Run agent with the same thread_id for conversation memory
            result = st.session_state.agent.run(
                user_input,
                thread_id=st.session_state.thread_id
            )
            
            response = result.get("agent_response", "No response generated.")
            
            # Add assistant message to history
            st.session_state.messages.append({"role": "assistant", "content": response})
            
            # Display assistant response
            st.markdown(f"""
            <div class="chat-message assistant-message">
                <div class="message-label assistant-label">Assistant:</div>
                <div>{response}</div>
            </div>
            """, unsafe_allow_html=True)
            
            # Show additional info if available
            if result.get("errors"):
                st.markdown(f"""
                <div class="error-box">
                    <strong>⚠️ Errors:</strong><br>
                    {'<br>'.join(result['errors'])}
                </div>
                """, unsafe_allow_html=True)
            
            if result.get("email_sent"):
                st.markdown("""
                <div class="success-box">
                    <strong>✅ Email sent successfully!</strong>
                </div>
                """, unsafe_allow_html=True)
            
        except Exception as e:
            error_msg = f"Error processing request: {str(e)}"
            st.error(error_msg)
            st.session_state.messages.append({"role": "assistant", "content": error_msg})
    
    # Force rerun to update UI
    st.rerun()

# Footer
st.markdown("---")
st.markdown("""
<div style="text-align: center; color: #666; padding: 1rem;">
    <p>💡 Tip: You can ask follow-up questions about the articles!</p>
    <p style="font-size: 0.8rem;">Powered by OpenAI GPT-4 and NewsAPI</p>
</div>
""", unsafe_allow_html=True)