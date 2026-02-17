"""
Keyword matching metrics for ANNIF and similar text classification models
"""
from typing import Dict, Any, List
import pandas as pd


def keyword_accuracy_metric(y_true, y_pred, **kwargs) -> Dict[str, Any]:
    """
    Calculate keyword matching accuracy for ANNIF models.

    Args:
        y_true: Expected keywords (semicolon-separated string or list)
        y_pred: Predicted keywords (semicolon-separated string or list)
        **kwargs: Additional parameters

    Returns:
        Dictionary with accuracy metrics
    """
    from src.services.performance_service.keyword_matching import (
        parse_keywords,
        calculate_keyword_accuracy
    )

    # Convert inputs to lists if they're strings
    if isinstance(y_true, str):
        expected_keywords = parse_keywords(y_true)
    elif isinstance(y_true, list):
        expected_keywords = y_true
    else:
        expected_keywords = []

    if isinstance(y_pred, str):
        predicted_keywords = parse_keywords(y_pred)
    elif isinstance(y_pred, list):
        predicted_keywords = y_pred
    else:
        predicted_keywords = []

    # Calculate accuracy
    metrics = calculate_keyword_accuracy(expected_keywords, predicted_keywords)

    return {
        'value': metrics['accuracy'],
        'accuracy': metrics['accuracy'],
        'precision': metrics['precision'],
        'f1_score': metrics['f1_score'],
        'matched_count': metrics['matched_count'],
        'expected_count': metrics['expected_count'],
        'predicted_count': metrics['predicted_count'],
        'matched_keywords': metrics['matched_keywords']
    }


def batch_keyword_accuracy_metric(df: pd.DataFrame,
                                   expected_col: str = 'expected_subjects',
                                   predicted_col: str = 'predicted_subjects',
                                   **kwargs) -> Dict[str, Any]:
    """
    Calculate keyword accuracy across multiple documents.

    Args:
        df: DataFrame with expected and predicted keywords
        expected_col: Column name for expected keywords
        predicted_col: Column name for predicted keywords
        **kwargs: Additional parameters

    Returns:
        Dictionary with overall accuracy metrics
    """
    from src.services.performance_service.keyword_matching import (
        calculate_overall_accuracy
    )

    # Prepare metadata and predictions lists
    metadata_list = []
    predictions_list = []

    for idx, row in df.iterrows():
        if pd.notna(row.get(expected_col)):
            metadata_list.append({
                'id': row.get('id', idx),
                'file_name': row.get('file_name', ''),
                'expected_subjects': row[expected_col]
            })

        predictions_list.append({
            'id': row.get('id', idx),
            'file_name': row.get('file_name', ''),
            'predicted_subjects': row.get(predicted_col, ''),
            'extracted_id': row.get('id', idx)
        })

    # Calculate overall accuracy
    if metadata_list:
        metrics = calculate_overall_accuracy(metadata_list, predictions_list)
        return {
            'value': metrics['overall_accuracy'],
            **metrics
        }
    else:
        return {
            'value': 0.0,
            'overall_accuracy': 0.0,
            'overall_precision': 0.0,
            'overall_f1_score': 0.0,
            'average_document_accuracy': 0.0,
            'total_matched_keywords': 0,
            'total_expected_keywords': 0,
            'total_predicted_keywords': 0,
            'documents_evaluated': 0
        }
