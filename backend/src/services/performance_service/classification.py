"""Classification extraction and ANNIF post-processing."""
import pandas as pd
from typing import Any, Dict, List, Optional


def extract_classifications(output_df: pd.DataFrame, model_name: str) -> List[Dict[str, Any]]:
    """
    Build a list of classification items from output_df.
    Handles both ANNIF (subject prediction) and SAM (binary classification) outputs.
    """
    is_annif = 'annif' in model_name.lower()
    classifications = []

    for _, row in output_df.iterrows():
        item: Dict[str, Any] = {
            'file_name': row.get('file_name', 'unknown'),
            'file_path': row.get('file_path', 'unknown'),
        }

        if is_annif:
            for col in ('predicted_subjects', 'top_subjects', 'project_id', 'expected_subjects', 'notes'):
                if col in output_df.columns and pd.notna(row.get(col)):
                    item[col] = row[col]
            if 'subject_count' in output_df.columns and pd.notna(row.get('subject_count')):
                item['subject_count'] = int(row['subject_count'])
        else:
            if 'y_pred' in output_df.columns and pd.notna(row.get('y_pred')):
                pred = row['y_pred']
                if isinstance(pred, (int, float)):
                    item['classification'] = 'secure' if int(pred) == 1 else 'insecure'
                    item['classification_numeric'] = int(pred)
                else:
                    item['classification'] = str(pred).lower()
            elif 'prediction' in output_df.columns and pd.notna(row.get('prediction')):
                item['classification'] = str(row['prediction']).lower()

            for col in ('confidence', 'secure_probability', 'insecure_probability'):
                if col in output_df.columns and pd.notna(row.get(col)):
                    item[col] = float(row[col])

            for col in ('gender', 'age', 'true_value'):
                if col in output_df.columns and pd.notna(row.get(col)):
                    item[col] = row[col]

        if 'id' in output_df.columns and pd.notna(row.get('id')):
            item['id'] = row['id']
        if 'true_value' not in item and 'true_value' in output_df.columns and pd.notna(row.get('true_value')):
            item['true_value'] = row['true_value']

        classifications.append(item)

    return classifications


def process_annif_results(
    output_df: pd.DataFrame,
    classifications: List[Dict[str, Any]],
    output_location: str,
) -> Dict[str, Any]:
    """
    Generate results.csv and calculate accuracy for ANNIF models.
    Returns dict with results_csv_path and accuracy_metrics (if available).
    """
    results_for_csv = [
        {'id': c.get('id', ''), 'suggested_keywords': c.get('predicted_subjects', '')}
        for c in classifications
    ]

    results_csv_path = None
    accuracy_metrics = None

    try:
        results_csv_path = save_results_csv(output_location, results_for_csv)
        print(f"Saved results.csv to {results_csv_path}")
    except Exception as e:
        print(f"Error saving results.csv: {e}")

    if 'expected_subjects' in output_df.columns:
        try:
            metadata_list = [
                {'id': row.get('id', ''), 'file_name': row.get('file_name', ''), 'expected_subjects': row['expected_subjects']}
                for _, row in output_df.iterrows()
                if pd.notna(row.get('expected_subjects'))
            ]
            predictions_list = [
                {'id': row.get('id', ''), 'file_name': row.get('file_name', ''), 'predicted_subjects': row.get('predicted_subjects', ''), 'extracted_id': row.get('id', '')}
                for _, row in output_df.iterrows()
            ]
            accuracy_metrics = calculate_overall_accuracy(metadata_list, predictions_list)
        except Exception as e:
            print(f"Error calculating accuracy: {e}")

    return {'results_csv_path': results_csv_path, 'accuracy_metrics': accuracy_metrics}
