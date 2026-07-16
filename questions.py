"""
Research questions generation module
Automatically generates research questions from document content
"""

import google.generativeai as genai
import json
import os
from typing import List, Dict, Optional
from datetime import datetime
from config import config


class QuestionGenerator:
    """Generate research questions from documents"""
    
    QUESTION_CATEGORIES = {
        "objectives": "Main research objectives and goals",
        "methodology": "Research methodology and approach",
        "results": "Key findings and results",
        "limitations": "Study limitations and constraints",
        "future_work": "Future research directions"
    }
    
    @staticmethod
    def generate_questions(
        document_text: str, 
        num_questions: int = config.NUM_QUESTIONS,
        categories: Optional[List[str]] = None
    ) -> Dict[str, List[str]]:
        """
        Generate research questions from document
        
        Args:
            document_text: Document text to analyze
            num_questions: Number of questions per category
            categories: Specific categories to generate (default: all)
            
        Returns:
            Dictionary of questions by category
        """
        if categories is None:
            categories = list(QuestionGenerator.QUESTION_CATEGORIES.keys())
        
        # Prepare the prompt
        prompt = QuestionGenerator._prepare_prompt(
            document_text, 
            num_questions, 
            categories
        )
        
        try:
            model = genai.GenerativeModel(
                config.GEMINI_MODEL,
                system_instruction=QuestionGenerator._get_system_instruction()
            )
            
            response = model.generate_content(
                prompt,
                generation_config={"temperature": config.QUESTION_TEMPERATURE}
            )
            
            questions = QuestionGenerator._parse_response(response.text, categories)
            return questions
            
        except Exception as e:
            print(f"Error generating questions: {e}")
            return {cat: [f"Error generating questions for {cat}"] for cat in categories}
    
    @staticmethod
    def _get_system_instruction() -> str:
        """Get system instruction for question generation"""
        return """You are an expert research analyst. Generate insightful research questions 
        that would help understand the key aspects of academic papers and research documents.
        Questions should be:
        - Specific and focused
        - Related to the given document category
        - Thought-provoking and analytical
        - Answerable from the document content
        
        Format your response as JSON with categories as keys and lists of questions as values."""
    
    @staticmethod
    def _prepare_prompt(
        document_text: str, 
        num_questions: int, 
        categories: List[str]
    ) -> str:
        """Prepare the question generation prompt"""
        # Limit document text to avoid token limits
        max_chars = 3000
        if len(document_text) > max_chars:
            document_text = document_text[:max_chars] + "..."
        
        categories_desc = "\n".join([
            f"- {cat}: {QuestionGenerator.QUESTION_CATEGORIES.get(cat, cat)}"
            for cat in categories
        ])
        
        return f"""Analyze the following document and generate {num_questions} research questions for each of these categories:

{categories_desc}

Document content:
{document_text}

Generate exactly {num_questions} questions for each category.
Return the response as valid JSON with this structure:
{{
    "objectives": ["question1", "question2", ...],
    "methodology": ["question1", "question2", ...],
    "results": ["question1", "question2", ...],
    "limitations": ["question1", "question2", ...],
    "future_work": ["question1", "question2", ...]
}}

Only include JSON in your response, no additional text."""
    
    @staticmethod
    def _parse_response(response_text: str, categories: List[str]) -> Dict[str, List[str]]:
        """Parse question generation response"""
        try:
            # Try to extract JSON from response
            json_start = response_text.find('{')
            json_end = response_text.rfind('}') + 1
            
            if json_start >= 0 and json_end > json_start:
                json_text = response_text[json_start:json_end]
                questions = json.loads(json_text)
            else:
                questions = {}
            
            # Ensure all requested categories are present
            result = {}
            for cat in categories:
                result[cat] = questions.get(cat, [f"No questions generated for {cat}"])
            
            return result
            
        except json.JSONDecodeError:
            return {cat: ["Error parsing response"] for cat in categories}


class QuestionStorage:
    """Store and retrieve generated questions"""
    
    @staticmethod
    def save_questions(
        questions: Dict[str, List[str]], 
        document_name: str, 
        storage_dir: str = "questions_storage"
    ) -> str:
        """
        Save generated questions to file
        
        Args:
            questions: Questions dictionary
            document_name: Name of the document
            storage_dir: Directory to store questions
            
        Returns:
            Path to saved file
        """
        os.makedirs(storage_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{storage_dir}/{document_name}_{timestamp}.json"
        
        data = {
            "document": document_name,
            "timestamp": datetime.now().isoformat(),
            "questions": questions
        }
        
        try:
            with open(filename, 'w') as f:
                json.dump(data, f, indent=2)
            print(f"Questions saved to {filename}")
            return filename
        except Exception as e:
            print(f"Error saving questions: {e}")
            return ""
    
    @staticmethod
    def load_questions(filepath: str) -> Dict:
        """
        Load questions from file
        
        Args:
            filepath: Path to questions file
            
        Returns:
            Questions dictionary
        """
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
            return data.get("questions", {})
        except Exception as e:
            print(f"Error loading questions: {e}")
            return {}
    
    @staticmethod
    def list_saved_questions(storage_dir: str = "questions_storage") -> List[str]:
        """List all saved question files"""
        if not os.path.exists(storage_dir):
            return []
        
        return [
            os.path.join(storage_dir, f) 
            for f in os.listdir(storage_dir) 
            if f.endswith('.json')
        ]


class QuestionSelector:
    """Interactive question selection and retrieval"""
    
    @staticmethod
    def format_for_display(questions: Dict[str, List[str]]) -> str:
        """Format questions for display"""
        lines = []
        lines.append("=" * 80)
        lines.append("GENERATED RESEARCH QUESTIONS")
        lines.append("=" * 80)
        
        for category, qs in questions.items():
            lines.append(f"\n{category.upper()}:")
            lines.append("-" * 40)
            for i, q in enumerate(qs, 1):
                lines.append(f"{i}. {q}")
        
        lines.append("\n" + "=" * 80)
        return "\n".join(lines)
    
    @staticmethod
    def select_question(questions: Dict[str, List[str]], index: int) -> Optional[str]:
        """
        Select a specific question
        
        Args:
            questions: Questions dictionary
            index: Index of question (0-based, across all categories)
            
        Returns:
            Selected question or None
        """
        all_questions = []
        for category_qs in questions.values():
            all_questions.extend(category_qs)
        
        if 0 <= index < len(all_questions):
            return all_questions[index]
        
        return None
    
    @staticmethod
    def get_all_questions(questions: Dict[str, List[str]]) -> List[str]:
        """Get all questions as a flat list"""
        all_questions = []
        for category_qs in questions.values():
            all_questions.extend(category_qs)
        return all_questions


# Utility functions for backward compatibility
def generate_research_questions(
    document_text: str, 
    num_questions: int = config.NUM_QUESTIONS
) -> Dict[str, List[str]]:
    """
    Generate research questions from document
    
    Args:
        document_text: Document text
        num_questions: Number of questions per category
        
    Returns:
        Dictionary of questions by category
    """
    return QuestionGenerator.generate_questions(document_text, num_questions)


def store_generated_questions(
    questions: Dict[str, List[str]], 
    document_name: str = "research_paper"
) -> str:
    """Store generated questions"""
    return QuestionStorage.save_questions(questions, document_name)


def load_research_questions(filepath: str) -> Dict:
    """Load questions from file"""
    return QuestionStorage.load_questions(filepath)


def display_questions_for_selection(questions: Dict[str, List[str]]) -> str:
    """Display questions for user selection"""
    return QuestionSelector.format_for_display(questions)
