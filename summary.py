import logging
import google.generativeai as genai
from config import config
from typing import Dict, List, Optional

logging.basicConfig(level=logging.INFO)

class SummaryGenerator:
    MODEL_NAME = "gemini-pro"
    
    @classmethod
    def _initialize_genai(cls):
        try:
            api_key = config.GEMINI_API_KEY
            
            if not api_key:
                raise ValueError("GEMINI_API_KEY not set!")
            
            genai.configure(api_key=api_key)
            logging.info("Gemini API configured")
            return True
        
        except Exception as e:
            logging.error(f"Failed to init API: {str(e)}")
            return False
        
    #Generates summary
    @staticmethod
    def generate_summary(text: str, expertise_level: str = "intermediate") -> str:
        try:
            if not text or not isinstance(text, str):
                return "Error: Invalid text"
            
            if not SummaryGenerator._initialize_genai():
                return "Error: Could not initialize Gemini"

            prompt = f"""Provide a {expertise_level} summary (200-500 words) of:
{text}"""
            
            model = genai.GenerativeModel(SummaryGenerator.MODEL_NAME)
            response = model.generate_content(prompt)
            
            if not response or not response.text:
                return "Error: Empty response"
            
            summary = response.text.strip()
            logging.info(f"Generated {expertise_level} summary")
            return summary
        
        except Exception as e:
            error_str = str(e)
            logging.error(f"Error: {error_str}")
            
            if "401" in error_str:
                return "Error: Invalid API key - check GEMINI_API_KEY in .env"
            return f"Error: {error_str[:100]}"
    
    @staticmethod
    def generate_multiple_summaries(text: str) -> dict:
        return {
            "beginner": SummaryGenerator.generate_summary(text, "beginner"),
            "intermediate": SummaryGenerator.generate_summary(text, "intermediate"),
            "expert": SummaryGenerator.generate_summary(text, "expert")
        }


class SummaryValidator:
    @staticmethod
    def validate_quality(summary: str) -> dict:
        if not summary or summary.startswith("Error:"):
            return {
                "status": "failed",
                "quality_score": 0.0,
                "word_count": 0
            }
        
        word_count = len(summary.split())
        quality_score = 0.85 if 150 < word_count < 550 else 0.65
        
        return {
            "status": "pass" if quality_score >= 0.7 else "review",
            "quality_score": quality_score,
            "word_count": word_count
        }
    
    @staticmethod
    def format_validation_report(validation: Dict) -> str:
        lines = []
        lines.append("=" * 50)
        lines.append("SUMMARY VALIDATION REPORT")
        lines.append("=" * 50)
        lines.append(f"Status: {validation.get('status', 'unknown').upper()}")
        lines.append(f"Quality Score: {validation.get('quality_score', 0):.2f}/1.0")
        lines.append(f"Word Count: {validation.get('word_count', 0)}")
        lines.append(f"Sentence Count: {validation.get('sentence_count', 0)}")
        
        if validation.get('issues'):
            lines.append("\nIssues:")
            for issue in validation['issues']:
                lines.append(f"  - {issue}")
        else:
            lines.append("\nNo issues found!")
        
        lines.append("=" * 50)
        return "\n".join(lines)


class SummaryComparator:
      
    @staticmethod
    def compare_summaries(summaries: Dict[str, str]) -> Dict:
        comparison = {}
        
        for level, summary in summaries.items():
            word_count = len(summary.split())
            sentence_count = len([s for s in summary.split('.') if s.strip()])

            avg_word_length = sum(len(w) for w in summary.split()) / max(word_count, 1)
            
            comparison[level] = {
                "word_count": word_count,
                "sentence_count": sentence_count,
                "avg_word_length": round(avg_word_length, 2),
                "complexity": SummaryComparator._assess_complexity(avg_word_length)
            }
        
        return comparison
    
    @staticmethod
    def _assess_complexity(avg_word_length: float) -> str:
        if avg_word_length < 5:
            return "very_simple"
        elif avg_word_length < 6:
            return "simple"
        elif avg_word_length < 7:
            return "moderate"
        elif avg_word_length < 8:
            return "complex"
        else:
            return "very_complex"
    
    @staticmethod
    def format_comparison(comparison: Dict) -> str:
        lines = []
        lines.append("=" * 70)
        lines.append("SUMMARY COMPARISON ACROSS EXPERTISE LEVELS")
        lines.append("=" * 70)
        
        for level, metrics in comparison.items():
            lines.append(f"\n{level.upper()}:")
            lines.append("-" * 40)
            lines.append(f"  Word Count: {metrics['word_count']}")
            lines.append(f"  Sentences: {metrics['sentence_count']}")
            lines.append(f"  Avg Word Length: {metrics['avg_word_length']}")
            lines.append(f"  Complexity: {metrics['complexity']}")
        
        lines.append("\n" + "=" * 70)
        return "\n".join(lines)


# Utility functions for backward compatibility
def generate_summary(
    document_text: str, 
    expertise_level: str = "intermediate"
) -> str:
    return SummaryGenerator.generate_summary(document_text, expertise_level)


def generate_multi_level_summaries(document_text: str) -> Dict[str, str]:
    return SummaryGenerator.generate_multiple_summaries(document_text)


def validate_summary_quality(summary: str) -> Dict:
    return SummaryValidator.validate_quality(summary)


def compare_summaries(summaries: Dict[str, str]) -> Dict:
    return SummaryComparator.compare_summaries(summaries)


def format_summary_comparison(comparison: Dict) -> str:
    return SummaryComparator.format_comparison(comparison)


def format_validation_report(validation: Dict) -> str:
    return SummaryValidator.format_validation_report(validation)
