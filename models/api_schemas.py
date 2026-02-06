from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

class QueryRequest(BaseModel):
    query: str = Field(..., description="The user's question or instruction")
    urls: Optional[List[str]] = Field(default=[], description="List of URLs to process")
    # Files will be handled via UploadFile in FastAPI, but metadata can be passed here if needed
    
class Source(BaseModel):
    title: str
    url: Optional[str] = None
    content_snippet: str
    score: float

class Metrics(BaseModel):
    latency: float
    tokens_used: int
    grounding_score: Optional[float] = None

class QueryResponse(BaseModel):
    answer: str
    sources: List[Source] = []
    metrics: Optional[Metrics] = None
    trace_id: Optional[str] = Field(None, description="LangSmith Trace ID")
