"""
FastAPI server for Research Assistant Bot
Provides REST API for all features
"""

from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List, Optional, Dict
import os
import json
from pathlib import Path
from dotenv import load_dotenv

from config import config
from retrieval import research_assistant, query_cache
from summary import SummaryGenerator, SummaryValidator
from questions import QuestionGenerator
from metrics import evaluate_metrics
import google.generativeai as genai

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

print("Working", api_key)

# Initialize Gemini API
try:
    if config.GEMINI_API_KEY:
        genai.configure(api_key=config.GEMINI_API_KEY)
except Exception as e:
    print(f"Warning: Could not configure Gemini API: {e}")

# Create FastAPI app
app = FastAPI(
    title="Research Assistant Bot API",
    description="AI-powered research assistant with retrieval, summarization, and question generation",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create upload folder
os.makedirs(config.UPLOAD_FOLDER, exist_ok=True)


# ==================== Pydantic Models ====================

class QueryRequest(BaseModel):
    """Query request model"""
    query: str
    include_summary: bool = True
    expertise_level: str = "intermediate"
    use_cache: bool = True


class SummaryRequest(BaseModel):
    """Summary generation request"""
    text: str
    expertise_level: str = "intermediate"


class QuestionsRequest(BaseModel):
    """Research questions request"""
    text: str
    num_questions: int = 5
    categories: Optional[List[str]] = None


class EvaluationRequest(BaseModel):
    """Evaluation request"""
    relevant_doc_ids: List[int]


class DocumentInfo(BaseModel):
    """Document information"""
    id: int
    filename: str
    num_pages: int


# ==================== Health & Status ====================

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "Research Assistant Bot",
        "version": "1.0.0"
    }


@app.get("/config")
async def get_config():
    """Get current configuration"""
    is_valid, error = config.validate()
    return {
        "valid": is_valid,
        "config": config.to_dict() if is_valid else None,
        "error": error
    }


# ==================== Document Management ====================

@app.post("/documents/upload")
async def upload_document(file: UploadFile = File(...)):
    """Upload and process PDF document with automatic summary generation"""
    try:
        # Validate file
        if not file.filename.lower().endswith('.pdf'):
            raise HTTPException(status_code=400, detail="Only PDF files are supported")
        
        # Save uploaded file
        file_path = os.path.join(config.UPLOAD_FOLDER, file.filename)
        
        with open(file_path, "wb") as buffer:
            content = await file.read()
            
            # Check file size
            if len(content) > config.MAX_FILE_SIZE:
                raise HTTPException(
                    status_code=413, 
                    detail=f"File too large (max {config.MAX_FILE_SIZE / (1024*1024):.1f} MB)"
                )
            
            buffer.write(content)
        
        # Add to research assistant
        success, message = research_assistant.add_document(file_path)
        
        if success:
            # Get the document ID (last added document)
            doc_id = len(research_assistant.doc_processor.documents) - 1
            
            # Automatically generate summaries
            auto_summaries = research_assistant.generate_auto_summaries(doc_id)
            
            return {
                "status": "success",
                "message": message,
                "filename": file.filename,
                "doc_id": doc_id,
                "auto_summaries": auto_summaries
            }
        else:
            os.remove(file_path)
            raise HTTPException(status_code=400, detail=message)
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload error: {str(e)}")


@app.get("/documents")
async def list_documents():
    """List all uploaded documents"""
    try:
        documents = research_assistant.get_document_list()
        return {
            "status": "success",
            "count": len(documents),
            "documents": documents
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/documents/clear")
async def clear_all_documents():
    """Clear all documents"""
    try:
        research_assistant.clear_index()
        return {
            "status": "success",
            "message": "All documents cleared"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== Retrieval & Query ====================

@app.post("/query")
async def query_assistant(request: QueryRequest):
    """Query the research assistant"""
    try:
        # Check cache
        if request.use_cache:
            cached = query_cache.get(request.query)
            if cached:
                return {
                    "status": "success",
                    "cached": True,
                    **cached
                }
        
        # Perform query
        result = research_assistant.query(
            request.query,
            include_summary=request.include_summary,
            expertise_level=request.expertise_level
        )
        
        # Cache result
        if request.use_cache:
            query_cache.put(request.query, result)
        
        return {
            "status": "success",
            "cached": False,
            **result
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/retrieve")
async def retrieve_documents(query: str, k: int = 5):
    """Retrieve documents for a query"""
    try:
        results = research_assistant.retrieve(query, k)
        return {
            "status": "success",
            "query": query,
            "count": len(results),
            "results": results
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== Summary Generation ====================

@app.post("/summaries/generate")
async def generate_summary(request: SummaryRequest):
    """Generate summary at specific expertise level"""
    try:
        summary = SummaryGenerator.generate_summary(
            request.text,
            request.expertise_level
        )
        
        validation = SummaryValidator.validate_quality(summary)
        
        return {
            "status": "success",
            "expertise_level": request.expertise_level,
            "summary": summary,
            "validation": validation
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/summaries/multi-level")
async def generate_multi_level_summaries(text: str):
    """Generate summaries at all expertise levels"""
    try:
        summaries = SummaryGenerator.generate_multiple_summaries(text)
        
        result = {}
        for level, summary in summaries.items():
            validation = SummaryValidator.validate_quality(summary)
            result[level] = {
                "summary": summary,
                "validation": validation
            }
        
        return {
            "status": "success",
            "summaries": result
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== Research Questions ====================

@app.post("/questions/generate")
async def generate_questions(request: QuestionsRequest):
    """Generate research questions"""
    try:
        questions = QuestionGenerator.generate_questions(
            request.text,
            request.num_questions,
            request.categories
        )
        
        return {
            "status": "success",
            "num_questions": request.num_questions,
            "questions": questions
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== Metrics & Evaluation ====================

@app.post("/evaluate/retrieval")
async def evaluate_retrieval(request: EvaluationRequest):
    """Evaluate retrieval quality"""
    try:
        metrics = research_assistant.evaluate_retrieval(request.relevant_doc_ids)
        
        return {
            "status": "success",
            "metrics": metrics
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/index/stats")
async def get_index_stats():
    """Get index statistics"""
    try:
        stats = research_assistant.embedding_manager.get_index_stats()
        
        return {
            "status": "success",
            "stats": stats
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== Cache Management ====================

@app.delete("/cache/clear")
async def clear_cache():
    """Clear query cache"""
    try:
        query_cache.clear()
        return {
            "status": "success",
            "message": "Cache cleared"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== Error Handlers ====================

@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """Handle general exceptions"""
    return JSONResponse(
        status_code=500,
        content={
            "status": "error",
            "message": str(exc)
        },
    )


# ==================== Root ====================

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "name": "Research Assistant Bot API",
        "version": "1.0.0",
        "endpoints": {
            "health": "/health",
            "config": "/config",
            "documents": {
                "upload": "POST /documents/upload",
                "list": "GET /documents",
                "clear": "DELETE /documents/clear"
            },
            "retrieval": {
                "query": "POST /query",
                "retrieve": "GET /retrieve"
            },
            "summaries": {
                "generate": "POST /summaries/generate",
                "multi_level": "POST /summaries/multi-level"
            },
            "questions": {
                "generate": "POST /questions/generate"
            },
            "evaluation": {
                "retrieve": "POST /evaluate/retrieval",
                "stats": "GET /index/stats"
            },
            "cache": {
                "clear": "DELETE /cache/clear"
            }
        }
    }


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        app,
        host=config.SERVER_HOST,
        port=config.SERVER_PORT,
        log_level="info"
    )
