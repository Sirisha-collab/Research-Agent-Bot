"""
Metrics module for retrieval quality evaluation
Implements Precision@K, Recall@K, MRR, and Hit Rate
"""

from typing import List, Set, Dict, Optional
from collections import defaultdict


class RetrievalMetrics:
    """Calculate retrieval quality metrics"""
    
    @staticmethod
    def calculate_precision_at_k(
        retrieved_docs: List[int], 
        relevant_docs: Set[int], 
        k: int
    ) -> float:
        """
        Calculate Precision@K
        Precision = Number of relevant docs in top-k / k
        
        Args:
            retrieved_docs: List of retrieved document IDs (ordered by rank)
            relevant_docs: Set of relevant document IDs
            k: Number of top results to consider
            
        Returns:
            Precision@k score (0.0 to 1.0)
        """
        if k == 0:
            return 0.0
        
        top_k = retrieved_docs[:k]
        relevant_in_top_k = len(set(top_k) & relevant_docs)
        
        return relevant_in_top_k / k
    
    @staticmethod
    def calculate_recall_at_k(
        retrieved_docs: List[int], 
        relevant_docs: Set[int], 
        k: int
    ) -> float:
        """
        Calculate Recall@K
        Recall = Number of relevant docs in top-k / Total relevant docs
        
        Args:
            retrieved_docs: List of retrieved document IDs (ordered by rank)
            relevant_docs: Set of relevant document IDs
            k: Number of top results to consider
            
        Returns:
            Recall@k score (0.0 to 1.0)
        """
        if not relevant_docs:
            return 0.0
        
        top_k = retrieved_docs[:k]
        relevant_in_top_k = len(set(top_k) & relevant_docs)
        
        return relevant_in_top_k / len(relevant_docs)
    
    @staticmethod
    def calculate_mrr(
        retrieved_docs: List[int], 
        relevant_docs: Set[int]
    ) -> float:
        """
        Calculate Mean Reciprocal Rank
        MRR = 1 / rank of first relevant document
        
        Args:
            retrieved_docs: List of retrieved document IDs (ordered by rank)
            relevant_docs: Set of relevant document IDs
            
        Returns:
            MRR score (0.0 to 1.0)
        """
        for rank, doc_id in enumerate(retrieved_docs, 1):
            if doc_id in relevant_docs:
                return 1.0 / rank
        
        return 0.0
    
    @staticmethod
    def calculate_hit_rate(
        retrieved_docs: List[int], 
        relevant_docs: Set[int], 
        k: int
    ) -> float:
        """
        Calculate Hit Rate
        Hit Rate = 1 if any relevant doc in top-k, else 0
        
        Args:
            retrieved_docs: List of retrieved document IDs (ordered by rank)
            relevant_docs: Set of relevant document IDs
            k: Number of top results to consider
            
        Returns:
            Hit rate (0.0 or 1.0)
        """
        if not relevant_docs:
            return 0.0
        
        top_k = set(retrieved_docs[:k])
        return 1.0 if top_k & relevant_docs else 0.0
    
    @staticmethod
    def calculate_ndcg(
        retrieved_docs: List[int], 
        relevant_docs: Set[int], 
        k: int
    ) -> float:
        """
        Calculate Normalized Discounted Cumulative Gain
        
        Args:
            retrieved_docs: List of retrieved document IDs (ordered by rank)
            relevant_docs: Set of relevant document IDs
            k: Number of top results to consider
            
        Returns:
            NDCG score (0.0 to 1.0)
        """
        # Calculate DCG
        dcg = 0.0
        for rank, doc_id in enumerate(retrieved_docs[:k], 1):
            if doc_id in relevant_docs:
                dcg += 1.0 / (1.0 + (rank - 1) * 0.1)  # Logarithmic discount
        
        # Calculate IDCG
        ideal_docs = min(len(relevant_docs), k)
        idcg = 0.0
        for rank in range(1, ideal_docs + 1):
            idcg += 1.0 / (1.0 + (rank - 1) * 0.1)
        
        if idcg == 0:
            return 0.0
        
        return dcg / idcg
    
    @staticmethod
    def calculate_f1_score(precision: float, recall: float) -> float:
        """
        Calculate F1 Score
        F1 = 2 * (Precision * Recall) / (Precision + Recall)
        
        Args:
            precision: Precision score
            recall: Recall score
            
        Returns:
            F1 score (0.0 to 1.0)
        """
        if precision + recall == 0:
            return 0.0
        
        return 2 * (precision * recall) / (precision + recall)


class MetricsCalculator:
    """Calculate metrics for batch evaluations"""
    
    @staticmethod
    def evaluate_batch(
        retrieved_results: List[List[int]], 
        relevant_docs_list: List[Set[int]], 
        k_values: List[int] = None
    ) -> Dict:
        """
        Evaluate multiple queries
        
        Args:
            retrieved_results: List of retrieved doc lists for each query
            relevant_docs_list: List of relevant doc sets for each query
            k_values: K values to evaluate (default: [1, 3, 5, 10])
            
        Returns:
            Dictionary of metrics
        """
        if k_values is None:
            k_values = [1, 3, 5, 10]
        
        metrics = RetrievalMetrics()
        results = defaultdict(list)
        
        for retrieved, relevant in zip(retrieved_results, relevant_docs_list):
            for k in k_values:
                results[f"precision@{k}"].append(
                    metrics.calculate_precision_at_k(retrieved, relevant, k)
                )
                results[f"recall@{k}"].append(
                    metrics.calculate_recall_at_k(retrieved, relevant, k)
                )
                results[f"ndcg@{k}"].append(
                    metrics.calculate_ndcg(retrieved, relevant, k)
                )
            
            results["mrr"].append(metrics.calculate_mrr(retrieved, relevant))
        
        # Calculate averages
        summary = {}
        for metric_name, values in results.items():
            if values:
                avg = sum(values) / len(values)
                summary[f"{metric_name}_avg"] = avg
                summary[f"{metric_name}_min"] = min(values)
                summary[f"{metric_name}_max"] = max(values)
        
        summary["num_queries"] = len(retrieved_results)
        
        return summary
    
    @staticmethod
    def format_metrics(metrics: Dict) -> str:
        """Format metrics for display"""
        lines = []
        lines.append("=" * 60)
        lines.append("RETRIEVAL QUALITY METRICS")
        lines.append("=" * 60)
        
        for metric_name, value in sorted(metrics.items()):
            if isinstance(value, float):
                lines.append(f"{metric_name:.<40} {value:.4f}")
            else:
                lines.append(f"{metric_name:.<40} {value}")
        
        lines.append("=" * 60)
        return "\n".join(lines)


# Utility functions for backward compatibility
def calculate_precision_at_k(retrieved_docs: List[int], relevant_docs: Set[int], k: int) -> float:
    """Wrapper for precision@k calculation"""
    return RetrievalMetrics.calculate_precision_at_k(retrieved_docs, relevant_docs, k)


def calculate_recall_at_k(retrieved_docs: List[int], relevant_docs: Set[int], k: int) -> float:
    """Wrapper for recall@k calculation"""
    return RetrievalMetrics.calculate_recall_at_k(retrieved_docs, relevant_docs, k)


def calculate_mrr(retrieved_docs: List[int], relevant_docs: Set[int]) -> float:
    """Wrapper for MRR calculation"""
    return RetrievalMetrics.calculate_mrr(retrieved_docs, relevant_docs)


def calculate_hit_rate(retrieved_docs: List[int], relevant_docs: Set[int], k: int) -> float:
    """Wrapper for hit rate calculation"""
    return RetrievalMetrics.calculate_hit_rate(retrieved_docs, relevant_docs, k)


def evaluate_metrics(
    retrieved_docs: List[int], 
    relevant_docs: Set[int]
) -> Dict:
    """
    Calculate all metrics for a single query
    
    Args:
        retrieved_docs: List of retrieved document IDs
        relevant_docs: Set of relevant document IDs
        
    Returns:
        Dictionary of all metrics
    """
    metrics = RetrievalMetrics()
    
    return {
        "precision@1": metrics.calculate_precision_at_k(retrieved_docs, relevant_docs, 1),
        "precision@3": metrics.calculate_precision_at_k(retrieved_docs, relevant_docs, 3),
        "precision@5": metrics.calculate_precision_at_k(retrieved_docs, relevant_docs, 5),
        "recall@1": metrics.calculate_recall_at_k(retrieved_docs, relevant_docs, 1),
        "recall@3": metrics.calculate_recall_at_k(retrieved_docs, relevant_docs, 3),
        "recall@5": metrics.calculate_recall_at_k(retrieved_docs, relevant_docs, 5),
        "mrr": metrics.calculate_mrr(retrieved_docs, relevant_docs),
        "hit_rate@5": metrics.calculate_hit_rate(retrieved_docs, relevant_docs, 5),
        "ndcg@5": metrics.calculate_ndcg(retrieved_docs, relevant_docs, 5),
    }
