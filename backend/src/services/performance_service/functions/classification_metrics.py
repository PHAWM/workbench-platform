"""
Classification metrics using sklearn.
"""

import numpy as np
import pandas as pd
from typing import Union
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    fbeta_score,
    roc_auc_score,
    average_precision_score,
    balanced_accuracy_score,
    matthews_corrcoef,
    cohen_kappa_score,
    log_loss,
    brier_score_loss,
    hamming_loss,
    jaccard_score,
    classification_report,
    confusion_matrix
)


def precision_metric(y_true, y_pred, average='binary', **kwargs):
    """
    Calculate precision score.

    Args:
        y_true: True labels
        y_pred: Predicted labels
        average: 'binary', 'micro', 'macro', 'weighted', or None
        **kwargs: Additional sklearn arguments

    Returns:
        float or array: Precision score
    """
    return precision_score(y_true, y_pred, average=average, zero_division=0, **kwargs)


def recall_metric(y_true, y_pred, average='binary', **kwargs):
    """
    Calculate recall score (sensitivity, true positive rate).

    Args:
        y_true: True labels
        y_pred: Predicted labels
        average: 'binary', 'micro', 'macro', 'weighted', or None
        **kwargs: Additional sklearn arguments

    Returns:
        float or array: Recall score
    """
    return recall_score(y_true, y_pred, average=average, zero_division=0, **kwargs)


def f1_metric(y_true, y_pred, average='binary', **kwargs):
    """
    Calculate F1 score (harmonic mean of precision and recall).

    Args:
        y_true: True labels
        y_pred: Predicted labels
        average: 'binary', 'micro', 'macro', 'weighted', or None
        **kwargs: Additional sklearn arguments

    Returns:
        float or array: F1 score
    """
    return f1_score(y_true, y_pred, average=average, zero_division=0, **kwargs)


def fbeta_metric(y_true, y_pred, beta=1.0, average='binary', **kwargs):
    """
    Calculate F-beta score with custom beta parameter.

    Args:
        y_true: True labels
        y_pred: Predicted labels
        beta: Weight of recall vs precision (beta > 1 favors recall)
        average: 'binary', 'micro', 'macro', 'weighted', or None
        **kwargs: Additional sklearn arguments

    Returns:
        float or array: F-beta score
    """
    return fbeta_score(y_true, y_pred, beta=beta, average=average, zero_division=0, **kwargs)


def roc_auc_metric(y_true, y_pred_proba, average='macro', multi_class='ovr', **kwargs):
    """
    Calculate ROC AUC score.

    Args:
        y_true: True labels
        y_pred_proba: Predicted probabilities
        average: 'macro', 'weighted', or None
        multi_class: 'ovr' (one-vs-rest) or 'ovo' (one-vs-one)
        **kwargs: Additional sklearn arguments

    Returns:
        float: ROC AUC score
    """
    try:
        return roc_auc_score(y_true, y_pred_proba, average=average, multi_class=multi_class, **kwargs)
    except ValueError as e:
        return {'error': str(e), 'metric': 'roc_auc'}


def pr_auc_metric(y_true, y_pred_proba, average='macro', **kwargs):
    """
    Calculate Precision-Recall AUC score (Average Precision).

    Args:
        y_true: True labels
        y_pred_proba: Predicted probabilities
        average: 'macro', 'weighted', 'micro', or None
        **kwargs: Additional sklearn arguments

    Returns:
        float: Average precision score
    """
    return average_precision_score(y_true, y_pred_proba, average=average, **kwargs)


def balanced_accuracy_metric(y_true, y_pred, **kwargs):
    """
    Calculate balanced accuracy (average of recall for each class).
    Useful for imbalanced datasets.

    Args:
        y_true: True labels
        y_pred: Predicted labels
        **kwargs: Additional sklearn arguments

    Returns:
        float: Balanced accuracy score
    """
    return balanced_accuracy_score(y_true, y_pred, **kwargs)


def mcc_metric(y_true, y_pred, **kwargs):
    """
    Calculate Matthews Correlation Coefficient.
    Good metric for imbalanced datasets, ranges from -1 to 1.

    Args:
        y_true: True labels
        y_pred: Predicted labels
        **kwargs: Additional sklearn arguments

    Returns:
        float: MCC score
    """
    return matthews_corrcoef(y_true, y_pred, **kwargs)


def cohen_kappa_metric(y_true, y_pred, **kwargs):
    """
    Calculate Cohen's Kappa score.
    Measures inter-rater agreement, accounting for chance.

    Args:
        y_true: True labels
        y_pred: Predicted labels
        **kwargs: Additional sklearn arguments

    Returns:
        float: Cohen's Kappa score
    """
    return cohen_kappa_score(y_true, y_pred, **kwargs)


def log_loss_metric(y_true, y_pred_proba, **kwargs):
    """
    Calculate log loss (cross-entropy loss).

    Args:
        y_true: True labels
        y_pred_proba: Predicted probabilities
        **kwargs: Additional sklearn arguments

    Returns:
        float: Log loss value
    """
    return log_loss(y_true, y_pred_proba, **kwargs)


def brier_score_metric(y_true, y_pred_proba, **kwargs):
    """
    Calculate Brier score (mean squared error of probability predictions).
    Lower is better, ranges from 0 to 1.

    Args:
        y_true: True binary labels
        y_pred_proba: Predicted probabilities for positive class
        **kwargs: Additional sklearn arguments

    Returns:
        float: Brier score
    """
    return brier_score_loss(y_true, y_pred_proba, **kwargs)


def hamming_loss_metric(y_true, y_pred, **kwargs):
    """
    Calculate Hamming loss (fraction of incorrect labels).
    Useful for multi-label classification.

    Args:
        y_true: True labels
        y_pred: Predicted labels
        **kwargs: Additional sklearn arguments

    Returns:
        float: Hamming loss
    """
    return hamming_loss(y_true, y_pred, **kwargs)


def jaccard_metric(y_true, y_pred, average='binary', **kwargs):
    """
    Calculate Jaccard similarity score (Intersection over Union).

    Args:
        y_true: True labels
        y_pred: Predicted labels
        average: 'binary', 'micro', 'macro', 'weighted', or None
        **kwargs: Additional sklearn arguments

    Returns:
        float: Jaccard score
    """
    return jaccard_score(y_true, y_pred, average=average, zero_division=0, **kwargs)


def specificity_metric(y_true, y_pred, **kwargs):
    """
    Calculate specificity (true negative rate).

    Args:
        y_true: True labels
        y_pred: Predicted labels
        **kwargs: Additional arguments

    Returns:
        float: Specificity score
    """
    cm = confusion_matrix(y_true, y_pred)

    # Handle binary and multi-class
    if cm.shape == (2, 2):
        tn, fp, _, _ = cm.ravel()
        return tn / (tn + fp) if (tn + fp) > 0 else 0.0
    else:
        # For multi-class, return macro-averaged specificity
        specificities = []
        for i in range(cm.shape[0]):
            tn = np.sum(cm) - np.sum(cm[i, :]) - np.sum(cm[:, i]) + cm[i, i]
            fp = np.sum(cm[:, i]) - cm[i, i]
            spec = tn / (tn + fp) if (tn + fp) > 0 else 0.0
            specificities.append(spec)
        return np.mean(specificities)


def classification_report_metric(y_true, y_pred, output_dict=True, **kwargs):
    """
    Generate comprehensive classification report.

    Args:
        y_true: True labels
        y_pred: Predicted labels
        output_dict: If True, return dict; if False, return string
        **kwargs: Additional sklearn arguments

    Returns:
        dict or str: Classification report
    """
    return classification_report(y_true, y_pred, output_dict=output_dict, zero_division=0, **kwargs)


def performance_summary_metric(y_true, y_pred, y_pred_proba=None, **kwargs):
    """
    Calculate comprehensive performance summary with multiple metrics.

    Args:
        y_true: True labels
        y_pred: Predicted labels
        y_pred_proba: Predicted probabilities (optional)
        **kwargs: Additional arguments

    Returns:
        dict: Dictionary of multiple metric scores
    """
    summary = {
        'accuracy': accuracy_score(y_true, y_pred),
        'precision': precision_metric(y_true, y_pred),
        'recall': recall_metric(y_true, y_pred),
        'f1': f1_metric(y_true, y_pred),
        'balanced_accuracy': balanced_accuracy_metric(y_true, y_pred),
        'mcc': mcc_metric(y_true, y_pred),
    }

    if y_pred_proba is not None:
        try:
            summary['roc_auc'] = roc_auc_metric(y_true, y_pred_proba)
            summary['pr_auc'] = pr_auc_metric(y_true, y_pred_proba)
            summary['log_loss'] = log_loss_metric(y_true, y_pred_proba)
        except Exception as e:
            summary['probability_metrics_error'] = str(e)

    return summary
