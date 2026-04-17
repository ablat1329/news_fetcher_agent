# generate_graph.py
"""
Generate workflow visualization for README
"""
from dotenv import load_dotenv
# Load environment variables
load_dotenv()
from agents.workflow import ConversationalNewsAgent

def main():
    print("🎨 Generating workflow graph...")
    
    # Initialize agent
    agent = ConversationalNewsAgent()
    
    # Generate graph
    output_path = "docs/workflow_graph.png"
    agent.visualize_graph(output_path)
    
    print("✅ Done! Graph saved to", output_path)

if __name__ == "__main__":
    main()