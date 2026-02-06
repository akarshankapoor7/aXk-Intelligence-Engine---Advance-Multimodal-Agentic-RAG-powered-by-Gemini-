import os
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.prebuilt import ToolNode
from langgraph.graph import StateGraph, END
from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage, SystemMessage

from agents.state import AgentState
from tools.web_search import robust_search
from tools.ingestion import scrape_webpage

def create_graph():
    # 1. Initialize Model
    api_key = os.getenv("GEMINI_API_KEY")
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.0-flash", 
        google_api_key=api_key, 
        temperature=0
    )
    
    # 2. Bind Tools
    tools = [robust_search, scrape_webpage]
    llm_with_tools = llm.bind_tools(tools)

    # 3. Define Nodes
    def agent_node(state: AgentState):
        messages = state['messages']
        
        # Inject System Prompt if not present (or prepend dynamically)
        system_prompt = SystemMessage(content="""You are a helpful AI assistant called 'aXk - Intelligence Engine'.
        
        CAPABILITIES:
        1. You have access to a web search tool and a webpage scraper.
        2. You can read PDFs, TXTs, and CSVs provided by the user.
        3. If you see an image/scanned PDF, you can understand it visually.
        
        IMPORTANT:
        - If the user provides a URL in the chat (e.g. "read https://..."), YOU MUST use the `scrape_webpage` tool to read it. Do not just hallucinate the content.
        - If the user defined URLs in the "Knowledge Base", they are already in your context.
        
        VISUALIZATION RULES:
        If the user asks for a "workflow", "diagram", "process flow", or "image for understanding":
        1. You MUST generate a Graphviz DOT code block.
        2. Enclose the code in ```graphviz ... ```.
        3. Use 'digraph G { ... }' syntax.
        4. Make it professional, using 'rankdir=LR' or 'TB', and nice node shapes (box, oval).
        
        Example:
        ```graphviz
        digraph G {
          rankdir=LR;
          node [shape=box, style=filled, fillcolor=lightblue];
          Start -> Process -> End;
        }
        ```
        """)
        
        # Prepend system prompt to the list of messages passed to LLM
        # We assume messages list contains Human/AI messages.
        # Note: Gemini supports SystemMessage.
        
        # Check if system prompt is already there (optimization)
        # For simplicity, we create a new list
        all_messages = [system_prompt] + messages
        
        response = llm_with_tools.invoke(all_messages)
        return {"messages": [response]}

    tool_node = ToolNode(tools)

    # 4. Define Graph
    workflow = StateGraph(AgentState)
    
    workflow.add_node("agent", agent_node)
    workflow.add_node("tools", tool_node)
    
    workflow.set_entry_point("agent")
    
    # 5. Define Edges
    def should_continue(state: AgentState):
        last_message = state['messages'][-1]
        if last_message.tool_calls:
            return "tools"
        return END

    workflow.add_conditional_edges(
        "agent",
        should_continue,
        {
            "tools": "tools",
             END: END
        }
    )
    
    workflow.add_edge("tools", "agent")
    
    return workflow

# Global instance with Checkpointer
import sqlite3
from langgraph.checkpoint.sqlite import SqliteSaver

# Create DB connection
# check_same_thread=False is crucial for FastAPI multi-threading
conn = sqlite3.connect("checkpoints.db", check_same_thread=False)
memory = SqliteSaver(conn)

workflow = create_graph()
agent_app = workflow.compile(checkpointer=memory)
