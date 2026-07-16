"""
Summary generation module
Generates multi-level summaries tailored to different expertise levels
"""

import google.generativeai as genai
from typing import Dict, List, Optional
from config import config


class SummaryGenerator:
    """Generate summaries at different expertise levels"""
    
    EXPERTISE_LEVELS = {
        "beginner": "Explain for someone new to this field with minimal technical background",
        "intermediate": "Explain for someone with some knowledge in this field",
        "expert": "Provide a detailed technical summary for domain experts"
    }
    
    @staticmethod
    def generate_summary(
        document_text: str, 
        expertise_level: str = "intermediate",
        length_range: tuple = (config.MIN_SUMMARY_LENGTH, config.MAX_SUMMARY_LENGTH)
    ) -> str:
        """
        Generate a summary for a specific expertise level
        
        Args:
            document_text: Text to summarize
            expertise_level: Target expertise level (beginner, intermediate, expert)
            length_range: (min_words, max_words) for summary
            
        Returns:
            Summarized text
        """
        if expertise_level not in SummaryGenerator.EXPERTISE_LEVELS:
            expertise_level = "intermediate"
        
        # Limit input text to avoid token limits
        max_chars = 5000
        if len(document_text) > max_chars:
            document_text = document_text[:max_chars] + "..."
        
        system_instruction = SummaryGenerator._get_system_instruction(expertise_level)
        
        prompt = f"""Summarize the following document in {length_range[0]}-{length_range[1]} words.
Focus on key points and main ideas.

Document:
{document_text}

Provide a clear, well-structured summary appropriate for {expertise_level} audience."""
        
        try:
            model = genai.GenerativeModel(
                config.GEMINI_MODEL,
                system_instruction=system_instruction
            )
            
            response = model.generate_content(
                prompt,
                generation_config={"temperature": config.SUMMARY_TEMPERATURE}
            )
            
            return response.text.strip()
            
        except Exception as e:
            return f"[Error generating summary: {str(e)[:100]}]"
    
    @staticmethod
    def _get_system_instruction(expertise_level: str) -> str:
        """Get system instruction for the expertise level"""
        base = "You are an expert summarizer. "
        
        if expertise_level == "beginner":
            return base + "Use simple language and avoid jargon. Explain concepts clearly for newcomers."
        elif expertise_level == "expert":
            return base + "Use precise technical terminology. Include nuances and methodological details."
        else:  # intermediate
            return base + "Balance technical accuracy with accessibility. Target informed readers."
    
    @staticmethod
    def generate_multiple_summaries(
        document_text: str,
        expertise_levels: Optional[List[str]] = None
    ) -> Dict[str, str]:
        """
        Generate summaries at multiple expertise levels
        
        Args:
            document_text: Text to summarize
            expertise_levels: List of expertise levels (default: all)
            
        Returns:
            Dictionary of summaries by expertise level
        """
        if expertise_levels is None:
            expertise_levels = list(SummaryGenerator.EXPERTISE_LEVELS.keys())
        
        summaries = {}
        for level in expertise_levels:
            summaries[level] = SummaryGenerator.generate_summary(document_text, level)
        
        return summaries


class SummaryValidator:
    """Validate summary quality"""
    
    @staticmethod
    def validate_quality(summary: str) -> Dict:
        """
        Validate summary quality
        
        Args:
            summary: Summary text
            
        Returns:
            Dictionary with quality metrics
        """
        if not summary or summary.startswith("[Error"):
            return {
                "quality_score": 0.0,
                "status": "failed",
                "issues": ["Summary generation failed"]
            }
        
        word_count = len(summary.split())
        
        # Check length
        issues = []
        quality_score = 1.0
        
        if word_count < config.MIN_SUMMARY_LENGTH:
            issues.append(f"Too short ({word_count} words, min {config.MIN_SUMMARY_LENGTH})")
            quality_score -= 0.3
        
        if word_count > config.MAX_SUMMARY_LENGTH:
            issues.append(f"Too long ({word_count} words, max {config.MAX_SUMMARY_LENGTH})")
            quality_score -= 0.2
        
        # Check for basic structure
        sentences = len([s for s in summary.split('.') if s.strip()])
        if sentences < 2:
            issues.append("Too few sentences (minimum 2)")
            quality_score -= 0.2
        
        # Check for content
        if len(summary) < 50:
            issues.append("Summary too brief")
            quality_score -= 0.3
        
        return {
            "quality_score": max(0.0, quality_score),
            "word_count": word_count,
            "sentence_count": sentences,
            "status": "pass" if quality_score > 0.7 else "review",
            "issues": issues
        }
    
    @staticmethod
    def format_validation_report(validation: Dict) -> str:
        """Format validation report for display"""
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
    """Compare summaries across expertise levels"""
    
    @staticmethod
    def compare_summaries(summaries: Dict[str, str]) -> Dict:
        """
        Compare summaries from different expertise levels
        
        Args:
            summaries: Dictionary of summaries by expertise level
            
        Returns:
            Comparison analysis
        """
        comparison = {}
        
        for level, summary in summaries.items():
            word_count = len(summary.split())
            sentence_count = len([s for s in summary.split('.') if s.strip()])
            
            # Calculate readability (simple metric)
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
        """Assess text complexity based on word length"""
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
        """Format comparison for display"""
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
    """Generate a summary for a specific expertise level"""
    return SummaryGenerator.generate_summary(document_text, expertise_level)


def generate_multi_level_summaries(document_text: str) -> Dict[str, str]:
    """Generate summaries at all expertise levels"""
    return SummaryGenerator.generate_multiple_summaries(document_text)


def validate_summary_quality(summary: str) -> Dict:
    """Validate summary quality"""
    return SummaryValidator.validate_quality(summary)


def compare_summaries(summaries: Dict[str, str]) -> Dict:
    """Compare summaries across expertise levels"""
    return SummaryComparator.compare_summaries(summaries)


def format_summary_comparison(comparison: Dict) -> str:
    """Format summary comparison for display"""
    return SummaryComparator.format_comparison(comparison)


def format_validation_report(validation: Dict) -> str:
    """Format validation report for display"""
    return SummaryValidator.format_validation_report(validation)
