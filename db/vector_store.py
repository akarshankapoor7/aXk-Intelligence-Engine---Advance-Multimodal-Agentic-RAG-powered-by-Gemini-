import os
import time
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from sentence_transformers import SentenceTransformer

class SemanticCache:
    def __init__(self):
        self.url = os.getenv("QDRANT_URL", "http://localhost:6333")
        self.api_key = os.getenv("QDRANT_API_KEY")
        
        # Initialize Client
        # If no URL is set, we might default to local memory for testing, 
        # but the plan said Qdrant.
        try:
             self.client = QdrantClient(url=self.url, api_key=self.api_key)
        except:
             print("Qdrant not reachable. Caching disabled.")
             self.client = None

        self.collection_name = "semantic_cache"
        self.encoder = SentenceTransformer('all-MiniLM-L6-v2') # Lightweight model
        
        if self.client:
            self._ensure_collection()

    def _ensure_collection(self):
        try:
            self.client.get_collection(self.collection_name)
        except Exception:
            try:
                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=VectorParams(size=384, distance=Distance.COSINE),
                )
            except Exception as e:
                print(f"Failed to create/get collection: {e}")
                self.client = None # Disable client if we can't ensure collection

    def check_cache(self, query: str, threshold: float = 0.85):
        if not self.client:
            return None
            
        try:
            vector = self.encoder.encode(query).tolist()
            
            results = self.client.search(
                collection_name=self.collection_name,
                query_vector=vector,
                limit=1,
                score_threshold=threshold
            )
            
            if results:
                return results[0].payload.get("answer")
        except Exception as e:
            print(f"Cache check failed: {e}")
            # Optional: Disable client if connection refused repeatedly
        
        return None

    def add_to_cache(self, query: str, answer: str):
        if not self.client:
            return

        try:
            vector = self.encoder.encode(query).tolist()
            point_id = int(time.time() * 1000) # Simple ID generation
            
            self.client.upsert(
                collection_name=self.collection_name,
                points=[
                    PointStruct(
                        id=point_id,
                        vector=vector,
                        payload={"query": query, "answer": answer}
                    )
                ]
            )
        except Exception as e:
            print(f"Cache update failed: {e}")

# Global Instance
semantic_cache = SemanticCache()
