import os
from typing import List, Dict, Optional, Tuple
from pathlib import Path

try:
    from pypdf import PdfReader
except ImportError:
    from PyPDF2 import PdfReader


class PDFProcessor:
    """Process and extract text from PDF files"""
    
    @staticmethod
    def extract_text(pdf_path: str) -> Tuple[str, int]:
        """
        Extract text from PDF file
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            Tuple of (extracted_text, num_pages)
        """
        try:
            reader = PdfReader(pdf_path)
            text_parts = []
            
            for page_num, page in enumerate(reader.pages):
                try:
                    text = page.extract_text()
                    if text:
                        text_parts.append(f"--- Page {page_num + 1} ---\n{text}")
                except Exception as e:
                    print(f"Error extracting page {page_num + 1}: {e}")
                    text_parts.append(f"--- Page {page_num + 1} [Failed to extract] ---")
            
            full_text = "\n\n".join(text_parts)
            return full_text, len(reader.pages)
            
        except Exception as e:
            print(f"Error reading PDF {pdf_path}: {e}")
            return "", 0
    
    @staticmethod
    def extract_text_by_pages(pdf_path: str) -> List[Dict]:
        """
        Extract text page by page
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            List of dictionaries with page content and metadata
        """
        try:
            reader = PdfReader(pdf_path)
            pages = []
            
            for page_num, page in enumerate(reader.pages):
                try:
                    text = page.extract_text()
                    pages.append({
                        "page_number": page_num + 1,
                        "text": text if text else "",
                        "error": None
                    })
                except Exception as e:
                    pages.append({
                        "page_number": page_num + 1,
                        "text": "",
                        "error": str(e)
                    })
            
            return pages
            
        except Exception as e:
            print(f"Error reading PDF {pdf_path}: {e}")
            return []
    
    @staticmethod
    def chunk_text(text: str, chunk_size: int = 500, overlap: int = 100) -> List[str]:
        """
        Split text into overlapping chunks
        
        Args:
            text: Text to chunk
            chunk_size: Number of characters per chunk
            overlap: Number of overlapping characters between chunks
            
        Returns:
            List of text chunks
        """
        if len(text) <= chunk_size:
            return [text]
        
        chunks = []
        step = chunk_size - overlap
        
        for i in range(0, len(text), step):
            chunk = text[i:i + chunk_size]
            if chunk.strip():
                chunks.append(chunk)
        
        return chunks
    
    @staticmethod
    def validate_pdf(pdf_path: str) -> Tuple[bool, Optional[str]]:
        """
        Validate PDF file
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check if file exists
        if not os.path.exists(pdf_path):
            return False, "File not found"
        
        # Check file extension
        if not pdf_path.lower().endswith('.pdf'):
            return False, "Not a PDF file"
        
        # Check file size
        file_size = os.path.getsize(pdf_path)
        max_size = 50 * 1024 * 1024  # 50 MB
        if file_size > max_size:
            return False, f"File too large ({file_size / (1024*1024):.1f} MB, max {max_size / (1024*1024):.1f} MB)"
        
        # Try to open as PDF
        try:
            PdfReader(pdf_path)
            return True, None
        except Exception as e:
            return False, f"Invalid PDF: {str(e)}"
    
    @staticmethod
    def get_pdf_info(pdf_path: str) -> Dict:
        """
        Get PDF metadata and information
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            Dictionary with PDF information
        """
        try:
            reader = PdfReader(pdf_path)
            
            info = {
                "num_pages": len(reader.pages),
                "file_size_mb": os.path.getsize(pdf_path) / (1024 * 1024),
                "filename": os.path.basename(pdf_path),
            }
            
            # Try to get metadata
            if reader.metadata:
                info["title"] = reader.metadata.get('/Title', 'Unknown')
                info["author"] = reader.metadata.get('/Author', 'Unknown')
                info["subject"] = reader.metadata.get('/Subject', 'Unknown')
            
            return info
            
        except Exception as e:
            return {
                "error": str(e),
                "filename": os.path.basename(pdf_path)
            }


class DocumentProcessor:
    """Process multiple documents and manage document collection"""
    
    def __init__(self):
        """Initialize document processor"""
        self.documents = []
        self.document_index = {}
    
    def add_pdf(self, pdf_path: str) -> Tuple[bool, Optional[str]]:
        """
        Add PDF to collection
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            Tuple of (success, message)
        """
        # Validate PDF
        is_valid, error_msg = PDFProcessor.validate_pdf(pdf_path)
        if not is_valid:
            return False, error_msg
        
        # Extract text
        text, num_pages = PDFProcessor.extract_text(pdf_path)
        if not text:
            return False, "No text could be extracted from PDF"
        
        # Get metadata
        info = PDFProcessor.get_pdf_info(pdf_path)
        
        # Add to collection
        doc_id = len(self.documents)
        self.documents.append({
            "id": doc_id,
            "path": pdf_path,
            "filename": os.path.basename(pdf_path),
            "text": text,
            "num_pages": num_pages,
            "metadata": info
        })
        
        self.document_index[doc_id] = len(self.documents) - 1
        
        return True, f"Added {os.path.basename(pdf_path)} ({num_pages} pages)"
    
    def get_document_text(self, doc_id: int) -> Optional[str]:
        """Get document text by ID"""
        if 0 <= doc_id < len(self.documents):
            return self.documents[doc_id]["text"]
        return None
    
    def get_document_info(self, doc_id: int) -> Optional[Dict]:
        """Get document info by ID"""
        if 0 <= doc_id < len(self.documents):
            doc = self.documents[doc_id]
            return {
                "id": doc["id"],
                "filename": doc["filename"],
                "num_pages": doc["num_pages"],
                "metadata": doc["metadata"]
            }
        return None
    
    def list_documents(self) -> List[Dict]:
        """List all documents in collection"""
        return [
            {
                "id": doc["id"],
                "filename": doc["filename"],
                "num_pages": doc["num_pages"]
            }
            for doc in self.documents
        ]
    
    def remove_document(self, doc_id: int) -> bool:
        """Remove document from collection"""
        if 0 <= doc_id < len(self.documents):
            del self.documents[doc_id]
            return True
        return False
    
    def clear_all(self):
        """Clear all documents"""
        self.documents = []
        self.document_index = {}


# Utility functions
def extract_pdf_text(pdf_path: str) -> str:
    """Extract text from PDF"""
    text, _ = PDFProcessor.extract_text(pdf_path)
    return text


def chunk_pdf_text(text: str, chunk_size: int = 500) -> List[str]:
    """Chunk PDF text"""
    return PDFProcessor.chunk_text(text, chunk_size)


def validate_pdf_file(pdf_path: str) -> bool:
    """Validate PDF file"""
    is_valid, _ = PDFProcessor.validate_pdf(pdf_path)
    return is_valid
