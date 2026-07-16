"""
Embedding module for text vectorization and similarity search
Uses Gemini embeddings with FAISS indexing
"""

import numpy as np
import faiss
import google.generativeai as genai
import pickle
import os
import time
from typing import List, Tuple, Optional, Dict
from config import config


class EmbeddingManager:
    """Manages text embeddings and vector indexing"""
    
    def __init__(self):
        """Initialize embedding manager"""
        self.dimension = config.FAISS_INDEX_DIMENSION
        self.index = None
        self.documents = []
        self.document_texts = []
        self.load_or_create_index()
    
    def embed_text(
        self, 
        text: str, 
        task_type: str = "retrieval_document"
    ) -> List[float]:
        """
        Embed text using Gemini embeddings API
        
        Args:
            text: Text to embed
            task_type: Type of embedding task
            
        Returns:
            Embedding vector
        """
        try:
            result = genai.embed_content(
                model=config.GEMINI_EMBED_MODEL,
                content=text,
                task_type=task_type,
            )
            return result.get("embedding", [])
        except Exception as e:
            print(f"Embedding error: {e}")
            raise
    
    def embed_batch(
        self, 
        texts: List[str], 
        task_type: str = "retrieval_document"
    ) -> List[List[float]]:
        """
        Embed multiple texts
        
        Args:
            texts: List of texts to embed
            task_type: Type of embedding task
            
        Returns:
            List of embedding vectors
        """
        embeddings = []
        for i, text in enumerate(texts):
            try:
                embedding = self.embed_text(text, task_type)
                embeddings.append(embedding)
                # Rate limiting: small delay between API calls
                if i < len(texts) - 1:
                    time.sleep(0.1)
            except Exception as e:
                print(f"Error embedding text {i}: {e}")
                embeddings.append([0.0] * self.dimension)
        
        return embeddings
    
    def create_index(self):
        """Create FAISS index"""
        self.index = faiss.IndexFlatL2(self.dimension)
    
    def add_documents(
        self, 
        texts: List[str], 
        metadata: Optional[List[Dict]] = None
    ) -> int:
        """
        Add documents to the index
        
        Args:
            texts: List of document texts
            metadata: Optional metadata for each document
            
        Returns:
            Number of documents added
        """
        if not self.index:
            self.create_index()
        
        # Embed texts
        embeddings = self.embed_batch(texts)
        
        # Convert to numpy array
        embeddings_array = np.array(embeddings, dtype=np.float32)
        
        # Add to index
        self.index.add(embeddings_array)
        
        # Store documents
        for i, text in enumerate(texts):
            self.documents.append({
                "id": len(self.document_texts),
                "text": text,
                "metadata": metadata[i] if metadata else {}
            })
            self.document_texts.append(text)
        
        return len(texts)
    
    def search(
        self, 
        query: str, 
        k: int = config.RETRIEVAL_TOP_K
    ) -> List[Tuple[int, float, str]]:
        """
        Search for similar documents
        
        Args:
            query: Query text
            k: Number of results to return
            
        Returns:
            List of (doc_id, distance, text) tuples
        """
        if not self.index or len(self.document_texts) == 0:
            return []
        
        try:
            # Embed query
            query_embedding = self.embed_text(
                query, 
                task_type="retrieval_query"
            )
            query_array = np.array([query_embedding], dtype=np.float32)
            
            # Search
            distances, indices = self.index.search(query_array, min(k, len(self.document_texts)))
            
            # Format results
            results = []
            for idx, distance in zip(indices[0], distances[0]):
                if 0 <= idx < len(self.document_texts):
                    results.append((
                        int(idx),
                        float(distance),
                        self.document_texts[int(idx)]
                    ))
            
            return results
        except Exception as e:
            print(f"Search error: {e}")
            return []
    
    def save_index(self, path: str = config.FAISS_INDEX_PATH):
        """Save index to disk"""
        try:
            if self.index:
                faiss.write_index(self.index, f"{path}.idx")
            
            # Save document texts and metadata
            with open(f"{path}_docs.pkl", "wb") as f:
                pickle.dump({
                    "documents": self.documents,
                    "texts": self.document_texts
                }, f)
            
            print(f"Index saved to {path}")
        except Exception as e:
            print(f"Error saving index: {e}")
    
    def load_or_create_index(self, path: str = config.FAISS_INDEX_PATH):
        """Load index from disk or create new one"""
        try:
            if os.path.exists(f"{path}.idx") and os.path.exists(f"{path}_docs.pkl"):
                self.index = faiss.read_index(f"{path}.idx")
                
                with open(f"{path}_docs.pkl", "rb") as f:
                    data = pickle.load(f)
                    self.documents = data.get("documents", [])
                    self.document_texts = data.get("texts", [])
                
                print(f"Index loaded from {path}")
            else:
                self.create_index()
                print("New index created")
        except Exception as e:
            print(f"Error loading index: {e}")
            self.create_index()
    
    def clear_index(self):
        """Clear all data from index"""
        self.create_index()
        self.documents = []
        self.document_texts = []
    
    def get_index_stats(self) -> Dict:
        """Get index statistics"""
        return {
            "num_documents": len(self.document_texts),
            "dimension": self.dimension,
            "index_type": "FAISS L2",
            "total_size_mb": len(self.document_texts) * self.dimension * 4 / (1024 * 1024)
        }


# Global embedding manager instance
embedding_manager = EmbeddingManager()
