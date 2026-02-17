"""
Ranking and retrieval metrics using sklearn.
"""

from sklearn.metrics import (
    ndcg_score,
    top_k_accuracy_score
)


def ndcg_metric(y_true, y_score, k=None, **kwargs):
    """
    Calculate Normalized Discounted Cumulative Gain.
    Useful for ranking and recommendation systems.

    Args:
        y_true: True relevance scores
        y_score: Predicted scores
        k: Consider only top k results (None for all)
        **kwargs: Additional sklearn arguments

    Returns:
        float: NDCG score
    """
    return ndcg_score([y_true], [y_score], k=k, **kwargs)


def top_k_accuracy_metric(y_true, y_score, k=5, **kwargs):
    """
    Calculate top-k accuracy.
    Prediction is correct if true label is in top k predictions.

    Args:
        y_true: True labels
        y_score: Predicted scores/probabilities (2D array)
        k: Number of top predictions to consider
        **kwargs: Additional sklearn arguments

    Returns:
        float: Top-k accuracy
    """
    return top_k_accuracy_score(y_true, y_score, k=k, **kwargs)
