import os
from langchain_core.tools import tool
try:
    from tavily import TavilyClient
except ImportError:
    TavilyClient = None

@tool
def robust_search(query: str):
    """Current events and general knowledge search engine. Use this for questions about news, facts, or recent info."""
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        return "Error: TAVILY_API_KEY not found."
    
    if not TavilyClient:
        return "Error: `tavily-python` package not installed."

    try:
        client = TavilyClient(api_key=api_key)
        # Search for advanced context
        response = client.search(
            query=query, 
            search_depth="advanced",
            include_answer=True,
            max_results=5
        )
        
        # Format output
        context = []
        if response.get("answer"):
            context.append(f"AI Answer: {response['answer']}")
        
        for res in response.get("results", []):
            context.append(f"Source: {res['title']}\nURL: {res['url']}\nSnippet: {res['content']}")
            
        return "\n\n".join(context)
        
    except Exception as e:
        return f"Search failed: {str(e)}"
