import os
import time
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from models.api_schemas import QueryRequest, QueryResponse, Source, Metrics

# Initialize FastAPI app
app = FastAPI(
    title="aXk – Intelligence Engine",
    description="Multimodal Agentic RAG System",
    version="2.0"
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# LangSmith Setup (Basic check)
LANGCHAIN_TRACING_V2 = os.getenv("LANGCHAIN_TRACING_V2")
LANGCHAIN_API_KEY = os.getenv("LANGCHAIN_API_KEY")

if LANGCHAIN_TRACING_V2 == "true" and not LANGCHAIN_API_KEY:
    print("WARNING: LangSmith tracing is enabled but API Key is missing.")

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "aXk-Intelligence-Engine"}

@app.post("/query", response_model=QueryResponse)
async def query_engine(
    query: str = Form(...),
    session_id: str = Form("default_session"),
    urls: Optional[List[str]] = Form(None),
    files: List[UploadFile] = File(None)
):
    """
    Main entry point for the Intelligence Engine.
    Accepts query, session_id, URLs, and files.
    """
    start_time = time.time()
    
    # Connect to LangGraph Orchestrator
    try:
        from agents.orchestrator import agent_app
        from db.vector_store import semantic_cache
        from langchain_core.messages import HumanMessage
        
        # 1. Check Semantic Cache
        # Note: We might skip cache if conversation history is important, 
        # or we need to check if the query is context-dependent.
        # For now, we keep it simple.
        cached_answer = semantic_cache.check_cache(query)
        if cached_answer:
             # Just return it, but maybe Log it to history? 
             # Ideally we should pass it to the agent as a "tool output" or something so it knows.
             # But for strict caching speed, we return directly.
             pass 

        # Prepare content with URLs if provided
        # SMART INGESTION: Actively crawl/scrape the URLs instead of just passing them as text.
        
        import asyncio
        from tools.ingestion import robust_scrape

        content_text = query
        if urls:
            content_text += "\n\n--- Processed Web Sources ---\n"
            
            # Helper to fetch single URL using our robust scraper
            # Note: robust_scrape is synchronous (uses requests/sync_playwright).
            # We run it in a thread to keep FastAPI async.
            def fetch_single(u):
                 return (u, robust_scrape(u))

            # Parallel Execution
            tasks = [asyncio.to_thread(fetch_single, u) for u in urls]
            results = await asyncio.gather(*tasks)
            
            for url, text in results:
                if text and "Failed to extract" not in text:
                    # "Smart" Limit: Truncate to reasonable size
                    truncated_text = text[:15000]
                    content_text += f"\nSOURCE: {url}\nCONTENT:\n{truncated_text}\n"
                    if len(text) > 15000:
                        content_text += "\n[...Content Truncated...]\n"
                else:
                    content_text += f"\nSOURCE: {url}\nSTATUS: Failed to extract meaningful text. (Error: {text[:100]})\n"

            content_text += "\n-----------------------------------\n"
            
        message_parts = [{"type": "text", "text": content_text}]
        
        # ... (File processing code remains same) ...
        # Process Files (Images & Documents)
        import base64
        import io
        import pypdf
        
        for file in files or []:
            if file.content_type.startswith("image/"):
                file_content = await file.read()
                encoded_image = base64.b64encode(file_content).decode("utf-8")
                message_parts.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:{file.content_type};base64,{encoded_image}"}
                })
            
            elif file.content_type == "application/pdf":
                file_content = await file.read()
                pdf_reader = pypdf.PdfReader(io.BytesIO(file_content))
                text = ""
                try:
                    for page in pdf_reader.pages:
                        extracted = page.extract_text()
                        if extracted:
                            text += extracted + "\n"
                except:
                    text = "" # Failed to extract text (e.g. encrypted or corrupt)

                # HEURISTIC: If text is very short/empty, assume it's a SCANNED PDF (Image-based).
                # In that case, we send the raw PDF bytes for Gemini's native OCR.
                if len(text.strip()) < 50:
                    encoded_pdf = base64.b64encode(file_content).decode("utf-8")
                    message_parts.append({
                        "type": "text",
                        "text": f"\n\n--- Document ({file.filename}) is likely SCANNED. Processing as Image-PDF... ---\n"
                    })
                    # Pass as inline_data (compatible with langchain-google-genai conversion)
                    message_parts.append({
                        "type": "image_url", # 'image_url' key triggers Blob creation in LangChain Google
                        "image_url": {"url": f"data:application/pdf;base64,{encoded_pdf}"}
                    })
                else:
                    message_parts.append({
                        "type": "text", 
                        "text": f"\n\n--- Document Content ({file.filename}) ---\n{text}\n-----------------------------------\n"
                    })
                
            elif file.content_type in ["text/plain", "text/csv", "application/json"]:
                file_content = await file.read()
                text = file_content.decode("utf-8")
                message_parts.append({
                    "type": "text", 
                    "text": f"\n\n--- Document Content ({file.filename}) ---\n{text}\n-----------------------------------\n"
                })
            else:
                 pass
        
        inputs = {"messages": [HumanMessage(content=message_parts)]}
        config = {"configurable": {"thread_id": session_id}}
        
        # 2. Run Agent
        result = agent_app.invoke(inputs, config=config)
        
        # Extract Answer
        last_message = result["messages"][-1]
        final_answer = last_message.content
        
        # 3. Save to Cache
        semantic_cache.add_to_cache(query, final_answer)
        
        # Extract Sources (Naive extraction from tool artifacts or text)
        # Ideally, we'd parse tool_outputs from the state history
        # For now, we rely on the agent to cite sources in the text or Tavily's output
        # A more robust way is to inspect `result['messages']` for ToolMessages
        
        sources_list = []
        for msg in result["messages"]:
            if msg.type == "tool":
                # This is a simplification. Real extraction would parse the JSON/Strongly typed content
                sources_list.append(Source(
                    title="Agent Tool Result",
                    content_snippet=str(msg.content)[:200] + "...",
                    score=1.0
                ))
            
        # 4. FIX REFERENCES: Add "Context" sources (PDFs, URLs) explicitly
        if urls:
            for u in urls:
                sources_list.append(Source(title=f"Web: {u}", content_snippet="Provided by user", score=1.0))
        for f in (files or []):
             sources_list.append(Source(title=f"File: {f.filename}", content_snippet="Uploaded Document", score=1.0))

    except Exception as e:
        final_answer = f"Error processing request: {str(e)}"
        sources_list = []

    latency = time.time() - start_time
    
    # Extract Token Usage & Cost (Estimate)
    # Gemini Flash is free/cheap, but let's track it.
    total_tokens = 0
    try:
        # Loop through messages reversed to find the AI response with usage
        for msg in reversed(result["messages"]):
             if hasattr(msg, "response_metadata"):
                 usage = msg.response_metadata.get("usage_metadata")
                 if usage:
                     total_tokens = usage.get("total_tokens", 0)
                     break
        # Fallback if not found in metadata
        if total_tokens == 0:
             # Very rough estimate: 4 chars = 1 token
             total_tokens = len(final_answer) // 4
    except:
        pass

    # Calculate Relevancy (Grounding Score)
    # We use the existing encoder from semantic_cache to check similarity between Context and Answer.
    grounding_score = 0.0
    try:
        from sentence_transformers import util
        
        # 1. Encode Answer
        answer_emb = semantic_cache.encoder.encode(final_answer, convert_to_tensor=True)
        
        # 2. Encode Context (we use the 'content_text' which aggregates all inputs)
        # Context might be huge, so we take a representative chunk (first 5k chars) or valid sources.
        # Ideally, we split context into chunks and find max similarity (RAG style).
        # For efficiency, we just check against the provided text snippet.
        if len(content_text) > 50:
            context_snippet = content_text[:5000] # Limit to avoid processing too much
            context_emb = semantic_cache.encoder.encode(context_snippet, convert_to_tensor=True)
            
            # 3. Compute Cosine Similarity
            score = util.cos_sim(answer_emb, context_emb).item()
            grounding_score = max(0.0, min(1.0, score)) # Clip between 0 and 1
    except Exception as e:
        print(f"Relevancy calculation failed: {e}")
        grounding_score = 0.0

    return QueryResponse(
        answer=final_answer,
        sources=sources_list,
        metrics=Metrics(
            latency=latency,
            tokens_used=total_tokens,
            grounding_score=grounding_score
        ),
        trace_id=session_id
    )

@app.get("/sessions")
async def list_sessions():
    """List all available chat sessions from history."""
    try:
        # We need to access the sqlite connection from the orchestrator
        from agents.orchestrator import conn
        cursor = conn.cursor()
        # checkpoints table has 'thread_id'
        # Limit to last 5 recent sessions
        cursor.execute("SELECT DISTINCT thread_id FROM checkpoints ORDER BY thread_id DESC LIMIT 5")
        threads = [row[0] for row in cursor.fetchall()]
        return {"sessions": threads}
    except Exception as e:
         return {"sessions": [], "error": str(e)}

@app.get("/history/{session_id}")
async def get_history(session_id: str):
    """Retrieve message history for a specific session."""
    try:
        from agents.orchestrator import agent_app
        config = {"configurable": {"thread_id": session_id}}
        state = agent_app.get_state(config)
        
        history = []
        if state and state.values:
            raw_msgs = state.values.get("messages", [])
            for msg in raw_msgs:
                # Map LangChain message types to Frontend roles
                role = "user"
                if msg.type == "ai":
                    role = "assistant"
                elif msg.type == "human":
                    role = "user"
                else:
                    # Skip tool messages in the history view for cleanliness, 
                    # or map them if needed. For now, skip.
                    continue
                    
                history.append({
                    "role": role,
                    "content": msg.content
                })
        return {"history": history}
    except Exception as e:
        return {"history": [], "error": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.app:app", host="0.0.0.0", port=8050, reload=True)
