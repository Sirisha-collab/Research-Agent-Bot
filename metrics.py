from typing import List, Set, Dict, Optional
from collections import defaultdict


class RetrievalMetrics:
    
    @staticmethod
    def calculate_precision_at_k(
        retrieved_docs: List[int], 
        relevant_docs: Set[int], 
        k: int
    ) -> float:

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

        if precision + recall == 0:
            return 0.0
        
        return 2 * (precision * recall) / (precision + recall)


class MetricsCalculator:
    
    @staticmethod
    def evaluate_batch(
        retrieved_results: List[List[int]], 
        relevant_docs_list: List[Set[int]], 
        k_values: List[int] = None
    ) -> Dict:

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
    return RetrievalMetrics.calculate_precision_at_k(retrieved_docs, relevant_docs, k)


def calculate_recall_at_k(retrieved_docs: List[int], relevant_docs: Set[int], k: int) -> float:
    return RetrievalMetrics.calculate_recall_at_k(retrieved_docs, relevant_docs, k)


def calculate_mrr(retrieved_docs: List[int], relevant_docs: Set[int]) -> float:
    return RetrievalMetrics.calculate_mrr(retrieved_docs, relevant_docs)


def calculate_hit_rate(retrieved_docs: List[int], relevant_docs: Set[int], k: int) -> float:
    return RetrievalMetrics.calculate_hit_rate(retrieved_docs, relevant_docs, k)


def evaluate_metrics(
    retrieved_docs: List[int], 
    relevant_docs: Set[int]
) -> Dict:

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
