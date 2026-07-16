from typing import List, Dict, Optional, Tuple
from embedding import embedding_manager
from metrics import evaluate_metrics, MetricsCalculator
from summary import SummaryGenerator, SummaryValidator
from questions import QuestionGenerator, QuestionStorage
from pdf_processor import PDFProcessor, DocumentProcessor
from config import config
import google.generativeai as genai


class ResearchAssistant:
    
    def __init__(self):
        self.embedding_manager = embedding_manager
        self.doc_processor = DocumentProcessor()
        self.conversation_history = []
        self.last_query = ""
        self.last_results = []
        self.last_auto_summaries = {}
    
    def add_document(self, pdf_path: str) -> Tuple[bool, str]:
        success, message = self.doc_processor.add_pdf(pdf_path)
        
        if success:
            doc = self.doc_processor.documents[-1]

            chunks = PDFProcessor.chunk_text(doc["text"], chunk_size=500, overlap=100)
            
            self.embedding_manager.add_documents(chunks, [{"source": doc["filename"]} for _ in chunks])
            
            self.embedding_manager.save_index()
        
        return success, message
    
    def generate_auto_summaries(self, doc_id: Optional[int] = None) -> Dict:
        
        try:
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

            if len(text) > 3000:
                text = text[:3000] + "..."
            
            # Generate summaries for all levels
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
        
        if include_summary:
            summary = SummaryGenerator.generate_summary(combined_text, expertise_level)
            result["summary"] = summary
            result["expertise_level"] = expertise_level
        
        return result
    
    def _generate_response(self, query: str, context: str) -> str:
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
        return self.doc_processor.list_documents()
    
    def clear_index(self):
        self.embedding_manager.clear_index()
        self.doc_processor.clear_all()
        self.conversation_history = []
        self.last_results = []


class QueryCache:

    def __init__(self, max_size: int = 100):
        self.cache = {}
        self.max_size = max_size
    
    def get(self, query: str) -> Optional[Dict]:
        return self.cache.get(query.lower())
    
    def put(self, query: str, result: Dict):
        if len(self.cache) >= self.max_size:
            # Remove oldest entry
            self.cache.pop(next(iter(self.cache)))
        
        self.cache[query.lower()] = result
    
    def clear(self):
        self.cache = {}


# Global instance
research_assistant = ResearchAssistant()
query_cache = QueryCache()
