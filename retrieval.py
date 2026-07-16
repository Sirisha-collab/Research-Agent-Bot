"""
Retrieval module
Main search, retrieval, and integration with all features
"""

from typing import List, Dict, Optional, Tuple
from embedding import embedding_manager
from metrics import evaluate_metrics, MetricsCalculator
from summary import SummaryGenerator, SummaryValidator
from questions import QuestionGenerator, QuestionStorage
from pdf_processor import PDFProcessor, DocumentProcessor
from config import config
import google.generativeai as genai


class ResearchAssistant:
    """Main research assistant class"""
    
    def __init__(self):
        """Initialize research assistant"""
        self.embedding_manager = embedding_manager
        self.doc_processor = DocumentProcessor()
        self.conversation_history = []
        self.last_query = ""
        self.last_results = []
        self.last_auto_summaries = {}
    
    def add_document(self, pdf_path: str) -> Tuple[bool, str]:
        """
        Add a PDF document to the system
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            Tuple of (success, message)
        """
        success, message = self.doc_processor.add_pdf(pdf_path)
        
        if success:
            # Extract and index document text
            doc = self.doc_processor.documents[-1]
            
            # Chunk the text for better retrieval
            chunks = PDFProcessor.chunk_text(doc["text"], chunk_size=500, overlap=100)
            
            # Add chunks to embedding index
            self.embedding_manager.add_documents(chunks, [{"source": doc["filename"]} for _ in chunks])
            
            # Save index
            self.embedding_manager.save_index()
        
        return success, message
    
    def generate_auto_summaries(self, doc_id: Optional[int] = None) -> Dict:
        """
        Automatically generate summaries for a document
        
        Args:
            doc_id: Document ID (if None, use last added document)
            
        Returns:
            Dictionary with summaries for all expertise levels
        """
        try:
            # Get document text
            if doc_id is not None:
                text = self.doc_processor.get_document_text(doc_id)
            elif self.doc_processor.documents:
                text = self.doc_processor.documents[-1]["text"]
            else:
                return {
                    "status": "error",
                    "message": "No document available",
                    "summaries": {}
                }
            
            if not text:
                return {
                    "status": "error",
                    "message": "Could not retrieve document text",
                    "summaries": {}
                }
            
            # Limit text to first 3000 characters for efficiency
            if len(text) > 3000:
                text = text[:3000] + "..."
            
            # Generate summaries for all expertise levels
            summaries = {}
            expertise_levels = ["beginner", "intermediate", "expert"]
            
            for level in expertise_levels:
                try:
                    from summary import SummaryGenerator, SummaryValidator
                    
                    summary = SummaryGenerator.generate_summary(text, expertise_level=level)
                    validation = SummaryValidator.validate_quality(summary)
                    
                    summaries[level] = {
                        "text": summary,
                        "quality_score": validation.get("quality_score", 0),
                        "word_count": validation.get("word_count", 0),
                        "status": validation.get("status", "unknown")
                    }
                except Exception as e:
                    summaries[level] = {
                        "text": f"Error generating {level} summary",
                        "quality_score": 0,
                        "error": str(e)
                    }
            
            # Store last auto summaries
            self.last_auto_summaries = summaries
            
            return {
                "status": "success",
                "doc_id": doc_id,
                "summaries": summaries
            }
            
        except Exception as e:
            return {
                "status": "error",
                "message": str(e),
                "summaries": {}
            }
    
    def retrieve(
        self, 
        query: str, 
        k: int = config.RETRIEVAL_TOP_K
    ) -> List[Dict]:
        """
        Retrieve relevant documents
        
        Args:
            query: Search query
            k: Number of results
            
        Returns:
            List of retrieved documents
        """
        # Store query
        self.last_query = query
        
        # Search
        results = self.embedding_manager.search(query, k)
        
        # Format results
        retrieved = []
        for idx, distance, text in results:
            retrieved.append({
                "id": idx,
                "text": text,
                "similarity": 1.0 / (1.0 + distance),  # Convert distance to similarity
                "distance": distance
            })
        
        self.last_results = retrieved
        return retrieved
    
    def query(
        self, 
        query: str, 
        include_summary: bool = True,
        expertise_level: str = "intermediate"
    ) -> Dict:
        """
        Query the assistant with optional summary
        
        Args:
            query: Query text
            include_summary: Whether to generate summary
            expertise_level: Expertise level for summary
            
        Returns:
            Dictionary with query results
        """
        # Retrieve relevant documents
        retrieved = self.retrieve(query)
        
        if not retrieved:
            return {
                "query": query,
                "status": "no_results",
                "message": "No relevant documents found",
                "results": []
            }
        
        # Combine retrieved texts
        combined_text = "\n\n".join([r["text"] for r in retrieved])
        
        # Generate response using LLM
        response = self._generate_response(query, combined_text)
        
        result = {
            "query": query,
            "status": "success",
            "response": response,
            "retrieved_count": len(retrieved),
            "results": retrieved
        }
        
        # Generate summary if requested
        if include_summary:
            summary = SummaryGenerator.generate_summary(combined_text, expertise_level)
            result["summary"] = summary
            result["expertise_level"] = expertise_level
        
        return result
    
    def _generate_response(self, query: str, context: str) -> str:
        """Generate LLM response based on query and context"""
        prompt = f"""Based on the following context, answer the query concisely.

Query: {query}

Context:
{context}

Provide a helpful answer based on the context provided."""
        
        try:
            model = genai.GenerativeModel(config.GEMINI_MODEL)
            response = model.generate_content(
                prompt,
                generation_config={"temperature": 0.3}
            )
            return response.text.strip()
        except Exception as e:
            return f"Error generating response: {str(e)}"
    
    def generate_research_questions(
        self, 
        doc_id: Optional[int] = None,
        num_questions: int = config.NUM_QUESTIONS
    ) -> Dict:
        """
        Generate research questions for a document
        
        Args:
            doc_id: Document ID (if None, use last retrieved)
            num_questions: Number of questions per category
            
        Returns:
            Dictionary of questions by category
        """
        # Get document text
        if doc_id is not None:
            text = self.doc_processor.get_document_text(doc_id)
        elif self.last_results:
            text = "\n\n".join([r["text"] for r in self.last_results])
        else:
            return {"error": "No document available"}
        
        if not text:
            return {"error": "Could not retrieve document text"}
        
        # Generate questions
        questions = QuestionGenerator.generate_questions(text, num_questions)
        
        # Store questions
        if doc_id is not None:
            doc_info = self.doc_processor.get_document_info(doc_id)
            doc_name = doc_info["filename"] if doc_info else "document"
        else:
            doc_name = "research"
        
        QuestionStorage.save_questions(questions, doc_name)
        
        return questions
    
    def generate_summaries(
        self, 
        doc_id: Optional[int] = None,
        expertise_levels: Optional[List[str]] = None
    ) -> Dict[str, str]:
        """
        Generate summaries at different expertise levels
        
        Args:
            doc_id: Document ID (if None, use last retrieved)
            expertise_levels: List of expertise levels
            
        Returns:
            Dictionary of summaries by expertise level
        """
        # Get document text
        if doc_id is not None:
            text = self.doc_processor.get_document_text(doc_id)
        elif self.last_results:
            text = "\n\n".join([r["text"] for r in self.last_results])
        else:
            return {"error": "No document available"}
        
        if not text:
            return {"error": "Could not retrieve document text"}
        
        # Generate summaries
        return SummaryGenerator.generate_multiple_summaries(text, expertise_levels)
    
    def evaluate_retrieval(
        self,
        relevant_doc_ids: List[int]
    ) -> Dict:
        """
        Evaluate retrieval quality with ground truth
        
        Args:
            relevant_doc_ids: List of IDs of relevant documents
            
        Returns:
            Dictionary of evaluation metrics
        """
        if not self.last_results:
            return {"error": "No retrieval results to evaluate"}
        
        # Convert to sets for metrics calculation
        retrieved_ids = [r["id"] for r in self.last_results]
        relevant_ids = set(relevant_doc_ids)
        
        # Calculate metrics
        metrics = evaluate_metrics(retrieved_ids, relevant_ids)
        
        return {
            "query": self.last_query,
            "retrieved_count": len(retrieved_ids),
            "relevant_count": len(relevant_ids),
            "metrics": metrics
        }
    
    def get_document_list(self) -> List[Dict]:
        """Get list of all documents in system"""
        return self.doc_processor.list_documents()
    
    def clear_index(self):
        """Clear all data"""
        self.embedding_manager.clear_index()
        self.doc_processor.clear_all()
        self.conversation_history = []
        self.last_results = []


class QueryCache:
    """Cache for query results"""
    
    def __init__(self, max_size: int = 100):
        """Initialize cache"""
        self.cache = {}
        self.max_size = max_size
    
    def get(self, query: str) -> Optional[Dict]:
        """Get cached result"""
        return self.cache.get(query.lower())
    
    def put(self, query: str, result: Dict):
        """Cache result"""
        if len(self.cache) >= self.max_size:
            # Remove oldest entry
            self.cache.pop(next(iter(self.cache)))
        
        self.cache[query.lower()] = result
    
    def clear(self):
        """Clear cache"""
        self.cache = {}


# Global instance
research_assistant = ResearchAssistant()
query_cache = QueryCache()
