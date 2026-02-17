import numpy as np
from sklearn.metrics import accuracy_score, confusion_matrix
from typing import Any, Dict, Union, Tuple
import pandas as pd

def accuracy_metric(y_true, y_pred, **kwargs):
    """
    Calculate accuracy metric.
    
    Args:
        y_true: True labels
        y_pred: Predicted labels
        **kwargs: Additional arguments (ignored for accuracy)
    
    Returns:
        float: Accuracy score
    """
    return accuracy_score(y_true, y_pred)

def confusion_matrix_metric(y_true, y_pred, sensitive_attr=None, **kwargs):
    """
    Calculate confusion matrix, optionally stratified by sensitive attribute.
    
    Args:
        y_true: True labels
        y_pred: Predicted labels
        sensitive_attr: Optional sensitive attribute for group-wise analysis
        **kwargs: Additional arguments (labels, normalize, etc.)
    
    Returns:
        If sensitive_attr is None: numpy array (confusion matrix)
        If sensitive_attr is provided: dict mapping group -> confusion matrix
    """
    if sensitive_attr is None:
        return confusion_matrix(y_true, y_pred, **kwargs)
    
    # Group-wise confusion matrices
    df = pd.DataFrame({
        'y_true': y_true,
        'y_pred': y_pred,
        'sensitive': sensitive_attr
    })
    
    group_cms = {}
    for group in df['sensitive'].unique():
        group_data = df[df['sensitive'] == group]
        group_cms[group] = confusion_matrix(
            group_data['y_true'], 
            group_data['y_pred'], 
            **kwargs
        )
    
    return group_cms

def confusion_matrix_analysis(y_true, y_pred, sensitive_attr=None, **kwargs):
    """
    Detailed confusion matrix analysis with derived metrics.
    
    Returns:
        If sensitive_attr is None: dict with overall metrics
        If sensitive_attr is provided: dict mapping group -> metrics dict
    """
    def _analyze_cm(cm):
        """Extract metrics from confusion matrix."""
        if cm.shape == (2, 2):
            tn, fp, fn, tp = cm.ravel()
            return {
                'confusion_matrix': cm,
                'true_positives': int(tp),
                'true_negatives': int(tn),
                'false_positives': int(fp),
                'false_negatives': int(fn),
                'accuracy': (tp + tn) / (tp + tn + fp + fn) if (tp + tn + fp + fn) > 0 else 0,
                'precision': tp / (tp + fp) if (tp + fp) > 0 else 0,
                'recall': tp / (tp + fn) if (tp + fn) > 0 else 0,
                'specificity': tn / (tn + fp) if (tn + fp) > 0 else 0,
                'false_positive_rate': fp / (tn + fp) if (tn + fp) > 0 else 0,
                'false_negative_rate': fn / (tp + fn) if (tp + fn) > 0 else 0
            }
        else:
            # Multi-class case - return basic metrics
            total = cm.sum()
            correct = np.trace(cm)
            return {
                'confusion_matrix': cm,
                'accuracy': correct / total if total > 0 else 0,
                'total_predictions': int(total),
                'correct_predictions': int(correct)
            }
    
    if sensitive_attr is None:
        cm = confusion_matrix(y_true, y_pred, **kwargs)
        return _analyze_cm(cm)
    
    # Group-wise analysis
    df = pd.DataFrame({
        'y_true': y_true,
        'y_pred': y_pred,
        'sensitive': sensitive_attr
    })
    
    group_analysis = {}
    for group in df['sensitive'].unique():
        group_data = df[df['sensitive'] == group]
        group_cm = confusion_matrix(
            group_data['y_true'], 
            group_data['y_pred'], 
            **kwargs
        )
        group_analysis[group] = _analyze_cm(group_cm)
    
    return group_analysis

def equalized_odds_metric(y_true, y_pred, sensitive_attr, **kwargs):
    """
    Calculate equalized odds difference.
    Requires both y_true and y_pred to calculate TPR and FPR.
    
    Args:
        y_true: True labels
        y_pred: Predicted labels
        sensitive_attr: Sensitive attribute values
        **kwargs: Additional arguments
    
    Returns:
        float: Equalized odds difference
    """
    if sensitive_attr is None:
        raise ValueError("sensitive_attr is required for equalized odds")
    
    df = pd.DataFrame({
        'y_true': y_true,
        'y_pred': y_pred,
        'sensitive': sensitive_attr
    })
    
    # Calculate TPR and FPR for each group
    tpr_diff = []
    fpr_diff = []
    
    for group in df['sensitive'].unique():
        group_data = df[df['sensitive'] == group]
        
        # True Positive Rate
        tpr = group_data[(group_data['y_true'] == 1) & (group_data['y_pred'] == 1)].shape[0] / \
              max(group_data[group_data['y_true'] == 1].shape[0], 1)
        
        # False Positive Rate  
        fpr = group_data[(group_data['y_true'] == 0) & (group_data['y_pred'] == 1)].shape[0] / \
              max(group_data[group_data['y_true'] == 0].shape[0], 1)
        
        tpr_diff.append(tpr)
        fpr_diff.append(fpr)
    
    # Return max difference in TPR and FPR
    tpr_diff = max(tpr_diff) - min(tpr_diff)
    fpr_diff = max(fpr_diff) - min(fpr_diff)
    
    return max(tpr_diff, fpr_diff)

def equal_opportunity_metric(y_true, y_pred, sensitive_attr, **kwargs):
    """
    Calculate equal opportunity difference (TPR difference).
    Requires both y_true and y_pred.
    
    Args:
        y_true: True labels
        y_pred: Predicted labels
        sensitive_attr: Sensitive attribute values
        **kwargs: Additional arguments
    
    Returns:
        float: Equal opportunity difference (TPR difference)
    """
    if sensitive_attr is None:
        raise ValueError("sensitive_attr is required for equal opportunity")
    
    df = pd.DataFrame({
        'y_true': y_true,
        'y_pred': y_pred,
        'sensitive': sensitive_attr
    })
    
    tpr_values = []
    
    for group in df['sensitive'].unique():
        group_data = df[df['sensitive'] == group]
        
        # True Positive Rate
        tpr = group_data[(group_data['y_true'] == 1) & (group_data['y_pred'] == 1)].shape[0] / \
              max(group_data[group_data['y_true'] == 1].shape[0], 1)
        
        tpr_values.append(tpr)
    
    return max(tpr_values) - min(tpr_values)