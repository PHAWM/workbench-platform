"""
Keyword matching utilities for ANNIF evaluation
"""
import csv
import logging
from typing import List, Dict, Tuple, Any
from pathlib import Path

logger = logging.getLogger(__name__)


def normalize_keyword(keyword: str) -> str:
    """Normalize keyword for matching (lowercase, strip whitespace)"""
    return keyword.strip().lower()


def parse_keywords(keywords_str: str) -> List[str]:
    """Parse semicolon-separated keywords into a list of normalized keywords"""
    if not keywords_str or not isinstance(keywords_str, str):
        return []

    # Split by semicolon and normalize each keyword
    keywords = [normalize_keyword(k) for k in keywords_str.split(';')]
    return [k for k in keywords if k]  # Filter out empty strings


def calculate_keyword_accuracy(expected: List[str], predicted: List[str]) -> Dict[str, Any]:
    """
    Calculate accuracy metrics for keyword matching

    Args:
        expected: List of expected keywords
        predicted: List of predicted keywords

    Returns:
        Dictionary with accuracy metrics:
        - matched_count: Number of keywords that matched
        - expected_count: Total number of expected keywords
        - predicted_count: Total number of predicted keywords
        - accuracy: Percentage of expected keywords that were predicted
        - precision: Percentage of predicted keywords that were correct
        - f1_score: Harmonic mean of accuracy (recall) and precision
        - matched_keywords: List of keywords that matched
    """
    if not expected:
        return {
            'matched_count': 0,
            'expected_count': 0,
            'predicted_count': len(predicted),
            'accuracy': 0.0,
            'precision': 0.0,
            'f1_score': 0.0,
            'matched_keywords': []
        }

    # Normalize all keywords
    expected_set = set(expected)
    predicted_set = set(predicted)

    # Find matches
    matched = expected_set.intersection(predicted_set)
    matched_count = len(matched)
    expected_count = len(expected)
    predicted_count = len(predicted)

    # Calculate metrics
    accuracy = (matched_count / expected_count * 100) if expected_count > 0 else 0.0
    precision = (matched_count / predicted_count * 100) if predicted_count > 0 else 0.0

    # Calculate F1 score
    if accuracy + precision > 0:
        f1_score = 2 * (accuracy * precision) / (accuracy + precision)
    else:
        f1_score = 0.0

    return {
        'matched_count': matched_count,
        'expected_count': expected_count,
        'predicted_count': predicted_count,
        'accuracy': round(accuracy, 2),
        'precision': round(precision, 2),
        'f1_score': round(f1_score, 2),
        'matched_keywords': sorted(list(matched))
    }


def save_results_csv(
    output_dir: str,
    results: List[Dict[str, Any]],
    filename: str = "results.csv"
) -> str:
    """
    Save results to CSV file with id and suggested_keywords columns

    Args:
        output_dir: Directory to save the results
        results: List of result dictionaries containing id and suggested_keywords
        filename: Output filename (default: results.csv)

    Returns:
        Path to the saved CSV file
    """
    output_path = Path(output_dir) / filename

    try:
        with open(output_path, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = ['id', 'suggested_keywords']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

            writer.writeheader()
            for result in results:
                writer.writerow({
                    'id': result.get('id', ''),
                    'suggested_keywords': result.get('suggested_keywords', '')
                })

        logger.info(f"✅ Saved results to {output_path}")
        return str(output_path)

    except Exception as e:
        logger.error(f"❌ Failed to save results CSV: {e}")
        raise


def calculate_overall_accuracy(
    metadata: List[Dict[str, Any]],
    predictions: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Calculate overall accuracy metrics across all documents

    Args:
        metadata: List of metadata dictionaries with expected_subjects
        predictions: List of prediction dictionaries with predicted_subjects

    Returns:
        Dictionary with overall accuracy metrics
    """
    total_matched = 0
    total_expected = 0
    total_predicted = 0
    document_accuracies = []

    # Create mapping by id or file_name
    pred_map = {}
    for pred in predictions:
        key = pred.get('id') or pred.get('extracted_id') or pred.get('file_name')
        if key:
            pred_map[str(key)] = pred

    for meta in metadata:
        meta_id = str(meta.get('id', ''))
        file_name = meta.get('file_name', '')

        # Try to find matching prediction
        pred = pred_map.get(meta_id) or pred_map.get(file_name)

        if not pred:
            logger.warning(f"No prediction found for id={meta_id}, file={file_name}")
            continue

        # Parse keywords
        expected_kw = parse_keywords(meta.get('expected_subjects', ''))
        predicted_kw = parse_keywords(pred.get('predicted_subjects', ''))

        # Calculate accuracy for this document
        metrics = calculate_keyword_accuracy(expected_kw, predicted_kw)

        total_matched += metrics['matched_count']
        total_expected += metrics['expected_count']
        total_predicted += metrics['predicted_count']
        document_accuracies.append(metrics['accuracy'])

    # Calculate overall metrics
    overall_accuracy = (total_matched / total_expected * 100) if total_expected > 0 else 0.0
    overall_precision = (total_matched / total_predicted * 100) if total_predicted > 0 else 0.0

    if overall_accuracy + overall_precision > 0:
        overall_f1 = 2 * (overall_accuracy * overall_precision) / (overall_accuracy + overall_precision)
    else:
        overall_f1 = 0.0

    avg_document_accuracy = sum(document_accuracies) / len(document_accuracies) if document_accuracies else 0.0

    return {
        'overall_accuracy': round(overall_accuracy, 2),
        'overall_precision': round(overall_precision, 2),
        'overall_f1_score': round(overall_f1, 2),
        'average_document_accuracy': round(avg_document_accuracy, 2),
        'total_matched_keywords': total_matched,
        'total_expected_keywords': total_expected,
        'total_predicted_keywords': total_predicted,
        'documents_evaluated': len(document_accuracies)
    }
