import pandas as pd
import json
import requests
from typing import Dict, Any, List, Union, Optional, Tuple
from pathlib import Path
import numpy as np
import os
import glob
import uuid
from datetime import datetime
from sqlmodel import Session, select

from src.models import *
from src.services.performance_service.functions import METRICS_REGISTRY

from src.services.utility_service.storage_service import (
    StorageManager, 
    parse_storage_location, 
    discover_input_data_with_metadata,
    save_output_data,
    InputFileMetadataManager,
)

def get_metric_function(metric_name: str):
    """Get fairness metric function by name."""
    if metric_name not in METRICS_REGISTRY:
        available_metrics = list(METRICS_REGISTRY.keys())
        raise ValueError(f"Fairness metric '{metric_name}' not found. Available metrics: {available_metrics}")
    return METRICS_REGISTRY[metric_name]


def evaluate_function(metric_name: str, **kwargs):
    """Universal metric evaluation function with error handling."""
    try:
        metric_func = get_metric_function(metric_name)
        return metric_func(**kwargs)
    except Exception as e:
        print(f"Error evaluating metric '{metric_name}': {str(e)}")
        return {
            "status": "cannot be calculated",
            "error": str(e),
            "error_type": type(e).__name__,
            "metric_name": metric_name
        }


def expand_numeric_range(start: str, end: str) -> List[str]:
    """
    Expand a numeric range like P2-P4 to [P2, P3, P4].

    Args:
        start: Start value (e.g., "P2")
        end: End value (e.g., "P4")

    Returns:
        List of expanded values, or [start, end] if not a valid numeric range
    """
    import re

    # Try to extract prefix and number from both start and end
    start_match = re.match(r'^([A-Za-z]*)(\d+)$', start.strip())
    end_match = re.match(r'^([A-Za-z]*)(\d+)$', end.strip())

    if start_match and end_match:
        start_prefix, start_num = start_match.groups()
        end_prefix, end_num = end_match.groups()

        # Only expand if prefixes match (e.g., both are "P")
        if start_prefix == end_prefix:
            start_int = int(start_num)
            end_int = int(end_num)

            # Ensure start <= end
            if start_int <= end_int:
                return [f"{start_prefix}{i}" for i in range(start_int, end_int + 1)]

    # Not a valid numeric range, return as-is
    return [start.strip(), end.strip()]


def parse_range_groups(ranges: List[str]) -> Tuple[Dict[str, List[str]], List[str]]:
    """
    Parse range specifications to handle grouped values.

    Args:
        ranges: List of range strings (e.g., ["P1-P2", "male", "female"])

    Returns:
        Tuple of:
        - range_groups: Dict mapping original range string to list of individual values
          e.g., {"P1-P2": ["P1", "P2"], "male": ["male"]}
        - expanded_ranges: Flat list of all individual values
          e.g., ["P1", "P2", "male", "female"]

    Examples:
        >>> parse_range_groups(["P1-P2", "male"])
        ({"P1-P2": ["P1", "P2"], "male": ["male"]}, ["P1", "P2", "male"])

        >>> parse_range_groups(["P1|P2|P3"])
        ({"P1|P2|P3": ["P1", "P2", "P3"]}, ["P1", "P2", "P3"])

        >>> parse_range_groups(["P1, P2"])
        ({"P1, P2": ["P1", "P2"]}, ["P1", "P2"])

        >>> parse_range_groups(["P1 - P2"])
        ({"P1 - P2": ["P1", "P2"]}, ["P1", "P2"])

        >>> parse_range_groups(["P2-P4"])
        ({"P2-P4": ["P2", "P3", "P4"]}, ["P2", "P3", "P4"])
    """
    import re

    range_groups = {}
    expanded_ranges = []

    for range_val in ranges:
        range_str = str(range_val)

        # Check for hyphen-based range that could be numeric (e.g., P2-P4)
        if '-' in range_str and '|' not in range_str and ',' not in range_str:
            # Split by hyphen
            parts = range_str.split('-')
            if len(parts) == 2:
                # Try to expand as numeric range (e.g., P2-P4 -> [P2, P3, P4])
                individual_values = expand_numeric_range(parts[0], parts[1])
            else:
                # Multiple hyphens - split all
                individual_values = [v.strip() for v in parts if v.strip()]

            range_groups[range_str] = individual_values
            expanded_ranges.extend(individual_values)
        elif '|' in range_str or ',' in range_str:
            # Use '|' and ',' as separators (explicit list, not a range)
            individual_values = re.split(r'[|,]', range_str)
            individual_values = [v.strip() for v in individual_values if v.strip()]
            range_groups[range_str] = individual_values
            expanded_ranges.extend(individual_values)
        else:
            # Single value, not a group
            range_groups[range_str] = [range_str.strip()]
            expanded_ranges.append(range_str.strip())

    return range_groups, expanded_ranges


def combine_confusion_matrices(matrices: List) -> List:
    """
    Combine multiple confusion matrices by summing them element-wise.

    Args:
        matrices: List of confusion matrices (2D arrays)

    Returns:
        Combined confusion matrix
    """
    if not matrices:
        return None

    import numpy as np
    result = np.array(matrices[0])
    for matrix in matrices[1:]:
        result = result + np.array(matrix)

    return result.tolist()


def combine_classification_results(all_groups: Dict, group_keys: List[str]) -> Dict:
    """
    Combine classification results from multiple groups by summing confusion matrices
    and recalculating metrics from the combined matrix.

    Args:
        all_groups: Dictionary of group results
        group_keys: List of group keys to combine

    Returns:
        Combined result dictionary with recalculated metrics
    """
    if not group_keys:
        return None

    import numpy as np

    # Create a case-insensitive lookup map for all_groups
    groups_lower_map = {str(k).lower(): k for k in all_groups.keys()}

    # Collect confusion matrices
    confusion_matrices = []
    total_samples = 0

    for key in group_keys:
        key_lower = str(key).lower()
        # Try exact match first, then case-insensitive
        if key in all_groups:
            actual_key = key
        elif key_lower in groups_lower_map:
            actual_key = groups_lower_map[key_lower]
        else:
            continue

        group_result = all_groups[actual_key]
        if isinstance(group_result, dict) and 'confusion_matrix' in group_result:
            confusion_matrices.append(group_result['confusion_matrix'])
            if 'sample_size' in group_result:
                total_samples += group_result['sample_size']
            elif 'count' in group_result:
                total_samples += group_result['count']

    if not confusion_matrices:
        # Fallback to averaging if no confusion matrices
        return combine_group_results(all_groups, group_keys)

    # Combine confusion matrices by summing
    combined_cm = combine_confusion_matrices(confusion_matrices)

    if combined_cm is None:
        return None

    # Recalculate metrics from combined confusion matrix
    cm = np.array(combined_cm)

    # For binary classification
    if cm.shape == (2, 2):
        tn, fp, fn, tp = cm.ravel()

        result = {
            'confusion_matrix': combined_cm,
            'true_positives': int(tp),
            'true_negatives': int(tn),
            'false_positives': int(fp),
            'false_negatives': int(fn),
        }

        # Calculate metrics
        accuracy = (tp + tn) / (tp + tn + fp + fn) if (tp + tn + fp + fn) > 0 else 0
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0
        specificity = tn / (tn + fp) if (tn + fp) > 0 else 0
        fpr = fp / (tn + fp) if (tn + fp) > 0 else 0
        fnr = fn / (tp + fn) if (tp + fn) > 0 else 0

        result.update({
            'accuracy': float(accuracy),
            'precision': float(precision),
            'recall': float(recall),
            'specificity': float(specificity),
            'false_positive_rate': float(fpr),
            'false_negative_rate': float(fnr),
            'sample_size': total_samples if total_samples > 0 else int(tp + tn + fp + fn)
        })

        return result
    else:
        # Multi-class or other format - just return the combined confusion matrix
        return {
            'confusion_matrix': combined_cm,
            'sample_size': total_samples
        }


def combine_group_results(all_groups: Dict, individual_values: List[str]) -> Dict:
    """
    Combine results from multiple individual values into a single grouped result.

    Args:
        all_groups: Dictionary of all group results from the metric evaluation
        individual_values: List of individual values to combine (e.g., ["P1", "P2"])

    Returns:
        Combined result dictionary with averaged metrics weighted by count
    """
    combined_result = None
    combined_count = 0

    for ind_val in individual_values:
        # Look for this individual value in the groups
        for group_key, group_result in all_groups.items():
            if str(group_key).lower() == str(ind_val).lower():
                if combined_result is None:
                    # Initialize with first group's structure
                    combined_result = group_result.copy() if isinstance(group_result, dict) else group_result
                    if isinstance(group_result, dict) and 'count' in group_result:
                        combined_count = group_result.get('count', 0)
                else:
                    # Combine with subsequent groups
                    if isinstance(group_result, dict):
                        combined_count += group_result.get('count', 0)
                        # Average numeric metrics, sum counts
                        for key, val in group_result.items():
                            if key == 'count':
                                continue
                            if isinstance(val, (int, float)) and key in combined_result:
                                # Weight by count if available
                                prev_count = combined_result.get('count', 1)
                                curr_count = group_result.get('count', 1)
                                total_count = prev_count + curr_count
                                combined_result[key] = (combined_result[key] * prev_count + val * curr_count) / total_count
                break

    if combined_result is not None and isinstance(combined_result, dict) and 'count' in combined_result:
        combined_result['count'] = combined_count

    return combined_result


def create_cross_tabulation_results(
    output_df: pd.DataFrame,
    features_config: List[Dict],
    metric_name: str,
    eval_kwargs_base: Dict,
    expected_col: Optional[str] = None,
    predicted_col: Optional[str] = None
) -> Dict:
    """
    Create cross-tabulated results for multiple underlying features.

    Args:
        output_df: The output DataFrame with all data
        features_config: List of feature configurations with range_groups
        metric_name: Name of the metric to evaluate
        eval_kwargs_base: Base eval_kwargs (y_pred, y_true, etc.)
        expected_col: Column name for expected subjects (keyword accuracy)
        predicted_col: Column name for predicted subjects (keyword accuracy)

    Returns:
        Nested dictionary with cross-tabulated results

    Example:
        features_config = [
            {'feature_name': 'phase', 'range_groups': {'P2-P3': ['P2', 'P3'], 'P4': ['P4']}},
            {'feature_name': 'gender', 'range_groups': {'male': ['male'], 'female': ['female']}}
        ]

        Returns:
        {
            'P2-P3': {
                'male': {...metrics...},
                'female': {...metrics...}
            },
            'P4': {
                'male': {...metrics...},
                'female': {...metrics...}
            }
        }
    """
    from itertools import product

    # Get first feature (e.g., phase) - this will be the outer grouping
    primary_feature = features_config[0]
    primary_name = primary_feature['feature_name']
    primary_range_groups = primary_feature['range_groups']

    # Get secondary feature(s) (e.g., gender) - this will be inner grouping
    secondary_features = features_config[1:]

    # Find columns in dataframe
    feature_cols = {}
    for feat_config in features_config:
        feat_name = feat_config['feature_name']
        if feat_name in output_df.columns:
            feature_cols[feat_name] = feat_name
        else:
            # Try case-insensitive match
            for col in output_df.columns:
                if col.lower() == feat_name.lower():
                    feature_cols[feat_name] = col
                    break

    if len(feature_cols) != len(features_config):
        return {
            'error': 'Some features not found in dataframe',
            'missing_features': [f['feature_name'] for f in features_config if f['feature_name'] not in feature_cols]
        }

    print(f"Cross-tabulation columns mapped: {feature_cols}")

    cross_tab_results = {}

    # Iterate through primary feature range groups (e.g., P2-P3, P4)
    for primary_range, primary_values in primary_range_groups.items():
        cross_tab_results[primary_range] = {}

        # Filter data for this primary range group
        primary_col = feature_cols[primary_name]
        primary_mask = pd.Series([False] * len(output_df), index=output_df.index)
        for val in primary_values:
            val_mask = output_df[primary_col].astype(str).str.lower() == str(val).lower()
            primary_mask = primary_mask | val_mask

        primary_filtered = output_df[primary_mask]

        if len(primary_filtered) == 0:
            cross_tab_results[primary_range] = {
                'status': 'no_data',
                'message': f'No data found for {primary_range}'
            }
            continue

        # Now iterate through secondary feature range groups (e.g., male, female)
        if len(secondary_features) > 0:
            secondary_feature = secondary_features[0]
            secondary_name = secondary_feature['feature_name']
            secondary_range_groups = secondary_feature['range_groups']
            secondary_col = feature_cols[secondary_name]

            for secondary_range, secondary_values in secondary_range_groups.items():
                # Further filter by secondary feature
                secondary_mask = pd.Series([False] * len(primary_filtered), index=primary_filtered.index)
                for val in secondary_values:
                    val_mask = primary_filtered[secondary_col].astype(str).str.lower() == str(val).lower()
                    secondary_mask = secondary_mask | val_mask

                combined_filtered = primary_filtered[secondary_mask]

                if len(combined_filtered) == 0:
                    cross_tab_results[primary_range][secondary_range] = {
                        'status': 'no_data',
                        'message': f'No data for {primary_range} + {secondary_range}'
                    }
                    continue

                # Prepare evaluation kwargs for this combination
                valid_indices = combined_filtered.index
                eval_kwargs = {}

                # For cross-tabulation, we DON'T pass sensitive_attr because we've already
                # filtered the data to the specific combination we want (e.g., P2-P3 + male)
                # This prevents the metric function from further grouping by individual values

                # Filter y_pred, y_true to match the combined filter
                if metric_name in ['keyword_accuracy', 'batch_keyword_accuracy']:
                    if expected_col and expected_col in combined_filtered.columns:
                        eval_kwargs['y_true'] = combined_filtered[expected_col].fillna('').values
                    if predicted_col and predicted_col in combined_filtered.columns:
                        eval_kwargs['y_pred'] = combined_filtered[predicted_col].fillna('').values
                else:
                    if 'y_pred' in combined_filtered.columns:
                        eval_kwargs['y_pred'] = combined_filtered['y_pred'].dropna().values
                    if 'y_true' in combined_filtered.columns:
                        eval_kwargs['y_true'] = combined_filtered['y_true'].dropna().values
                    if 'y_pred_proba' in combined_filtered.columns:
                        eval_kwargs['y_pred_proba'] = combined_filtered['y_pred_proba'].dropna().values

                # Evaluate metric
                try:
                    result = evaluate_function(metric_name, **eval_kwargs)

                    # If result contains 'groups', we need to combine them since we want
                    # P2-P3 as a single group, not separate P2 and P3 results
                    if isinstance(result, dict) and 'groups' in result:
                        # The metric function grouped the results (e.g., by P2, P3 separately)
                        # We need to combine all the groups into a single result
                        all_groups = result['groups']

                        # Use combine_classification_results which sums confusion matrices
                        # and recalculates metrics from the combined matrix
                        combined_result = combine_classification_results(all_groups, list(all_groups.keys()))

                        if combined_result is not None:
                            cross_tab_results[primary_range][secondary_range] = combined_result
                        else:
                            # Fallback: just store the first group's result
                            first_group = list(all_groups.values())[0]
                            cross_tab_results[primary_range][secondary_range] = first_group
                    else:
                        cross_tab_results[primary_range][secondary_range] = result
                except Exception as e:
                    cross_tab_results[primary_range][secondary_range] = {
                        'error': str(e),
                        'sample_size': len(combined_filtered)
                    }
        else:
            # No secondary features, just evaluate for primary
            eval_kwargs = {}

            # For cross-tabulation, we DON'T pass sensitive_attr because we've already
            # filtered the data to the specific range we want (e.g., P2-P3)

            if metric_name in ['keyword_accuracy', 'batch_keyword_accuracy']:
                if expected_col and expected_col in primary_filtered.columns:
                    eval_kwargs['y_true'] = primary_filtered[expected_col].fillna('').values
                if predicted_col and predicted_col in primary_filtered.columns:
                    eval_kwargs['y_pred'] = primary_filtered[predicted_col].fillna('').values
            else:
                if 'y_pred' in primary_filtered.columns:
                    eval_kwargs['y_pred'] = primary_filtered['y_pred'].dropna().values
                if 'y_true' in primary_filtered.columns:
                    eval_kwargs['y_true'] = primary_filtered['y_true'].dropna().values
                if 'y_pred_proba' in primary_filtered.columns:
                    eval_kwargs['y_pred_proba'] = primary_filtered['y_pred_proba'].dropna().values

            try:
                result = evaluate_function(metric_name, **eval_kwargs)

                # If result contains 'groups', combine them
                if isinstance(result, dict) and 'groups' in result:
                    all_groups = result['groups']
                    combined_result = combine_classification_results(all_groups, list(all_groups.keys()))

                    if combined_result is not None:
                        cross_tab_results[primary_range] = combined_result
                    else:
                        first_group = list(all_groups.values())[0]
                        cross_tab_results[primary_range] = first_group
                else:
                    cross_tab_results[primary_range] = result
            except Exception as e:
                cross_tab_results[primary_range] = {
                    'error': str(e),
                    'sample_size': len(primary_filtered)
                }

    return cross_tab_results


def prepare_model_input_sam(file_info: Dict[str, Any], model_metadata: 'Modelmetadata') -> Dict[str, Any]:
    """Prepare input for SAM (Secure Attachment Model) - sends file_location and model_type"""
    import os
    from pathlib import Path

    # Get the file path
    file_path = file_info['file_path']

    # Convert to Path object for easier manipulation
    path = Path(file_path)

    # If it's a relative path starting with 'storage/', convert it to Docker container path
    if str(path).startswith('storage/'):
        # Docker container has storage mounted at /app/storage
        file_path = '/app/' + str(path)
    elif not os.path.isabs(file_path):
        # Convert relative path to absolute, then to container path
        abs_path = os.path.abspath(file_path)
        # Replace the host storage path with container path
        if 'storage/' in abs_path:
            storage_part = abs_path.split('storage/', 1)[1]
            file_path = '/app/storage/' + storage_part
        else:
            file_path = abs_path
    else:
        # Already absolute path from host - convert to container path
        if 'storage/' in file_path:
            storage_part = file_path.split('storage/', 1)[1]
            file_path = '/app/storage/' + storage_part

    request_data = {
        "file_location": file_path,
        "model_type": "all"  # Get predictions from all 4 models
    }
    print(f"SAM request data: {request_data}")
    print(f"Container file path: {file_path}")
    return request_data

def prepare_model_input(file_info: Dict[str, Any], model_metadata: 'Modelmetadata') -> Dict[str, Any]:
    """Prepare input data for the model based on file info and model metadata."""
    is_generative = bool(model_metadata.model_type)

    if not is_generative:  # Predictive AI
        # Check for SAM-like models
        if (model_metadata.task and 'attachment' in model_metadata.task.lower()) or \
           (model_metadata.output_context and 'attachment' in model_metadata.output_context.lower()):

            # SAM-specific input format
            if file_info['file_type'] == 'audio':
                # Extract audit_id from metadata or file path
                audit_id = file_info['metadata'].get('audit_id',
                          file_info['metadata'].get('extracted_id', 'unknown'))

                return {
                    "file_location": {
                        "audit_id": audit_id,
                        "file_name": file_info['file_name']
                    },
                    "model_type": "mc2"
                }
            else:
                # Structured data for SAM
                input_data = file_info['data'] or {}
                return {
                    "file_location": {
                        "audit_id": input_data.get('audit_id', file_info['metadata'].get('audit_id', 'unknown')),
                        "file_name": input_data.get('file_name', file_info['file_name'])
                    },
                    "model_type": input_data.get('model_type', 'all')
                }
        else:
            # Generic predictive model (e.g., Annif for text analysis)
            # For text files, use 'text' field instead of 'prompt'
            if file_info['file_type'] == 'text' and file_info['data']:
                input_data = file_info['data']
                if isinstance(input_data, dict):
                    # Annif expects {"text": "...", "limit": 10, "threshold": 0.0, "language": ""} format
                    text_content = None
                    for field in ['text', 'content', 'prompt']:
                        if field in input_data:
                            text_content = input_data[field]
                            break

                    if text_content:
                        # Check if this is HTML content and extract body if needed
                        if model_metadata.name and 'annif' in model_metadata.name.lower():
                            # Check if content looks like HTML
                            text_str = str(text_content).strip()
                            if text_str.startswith('<') and ('html' in text_str.lower() or '<body' in text_str.lower()):
                                from src.services.model_service.models.ANNIF.annif_predictor import AnnifPredictor
                                text_content = AnnifPredictor.extract_text_from_html(text_content)
                                # print(f"🔍 Extracted text from HTML: {len(text_content)} characters")

                        # Prepare Annif-specific request with parameters
                        return {
                            "text": text_content,
                            "project_id": input_data.get('project_id', 'yso-en'),  # Default: yso-en
                            "limit": 15,
                            "threshold": input_data.get('threshold', 0.0)
                        }
                    return {"text": str(input_data), "project_id": "yso-en", "limit": 15, "threshold": 0.0}
                else:
                    return {"text": str(input_data), "project_id": "yso-en", "limit": 15, "threshold": 0.0}
            # For other predictive models, return data as-is
            return file_info['data'] or {'file_path': file_info['file_path']}

    else:  # Generative AI
        # Prepare prompt for generative models
        if file_info['data']:
            input_data = file_info['data']
            if isinstance(input_data, dict):
                # Look for prompt-like fields
                for field in ['prompt', 'text', 'content', 'message', 'query']:
                    if field in input_data:
                        return {"prompt": input_data[field]}

                # Create prompt from all data
                prompt_parts = [f"{k}: {v}" for k, v in input_data.items() if pd.notna(v)]
                return {"prompt": " | ".join(prompt_parts)}
            else:
                return {"prompt": str(input_data)}
        else:
            return {"prompt": f"Process file: {file_info['file_name']}"}


def transform_model_output_sam(raw_output: Any, model_metadata: 'Modelmetadata', file_info: Dict[str, Any]) -> Dict[str, Any]:
    """Transform SAM model output - handles multiple model predictions"""
    result = {
        'file_path': file_info['file_path'],
        'file_name': file_info['file_name'],
        'model_id': model_metadata.id,
        'model_name': model_metadata.name,
    }

    # Add metadata (gender, age, etc.)
    result.update(file_info.get('metadata', {}))

    # Map true_value to y_true if it exists in metadata
    if 'true_value' in result:
        true_val = result['true_value']
        if isinstance(true_val, str):
            true_val_lower = true_val.lower().strip()
            if true_val_lower in ['secure', 'safe', 'positive', '1', 'true', 'yes']:
                result['y_true'] = 1
            elif true_val_lower in ['insecure', 'unsafe', 'negative', '0', 'false', 'no']:
                result['y_true'] = 0
        elif isinstance(true_val, (int, float)):
            result['y_true'] = int(true_val)

    # SAM returns {'output': {'audio': {...}, 'text': {...}, 'mc1': {...}, 'mc2': {...}}}
    # Extract the 4 model outputs, prioritizing MC2
    model_outputs = []
    mc2_output = None

    if isinstance(raw_output, dict) and 'output' in raw_output:
        output_dict = raw_output['output']

        # First, extract MC2 specifically
        if 'mc2' in output_dict and isinstance(output_dict['mc2'], dict):
            mc2_output = output_dict['mc2']
            if mc2_output.get('success', False):
                model_outputs.append(mc2_output)

        # Then extract other models
        for model_key in ['audio', 'text', 'mc1']:
            if model_key in output_dict and isinstance(output_dict[model_key], dict):
                model_out = output_dict[model_key]
                # Only include successful predictions
                if model_out.get('success', False):
                    model_outputs.append(model_out)
    elif isinstance(raw_output, list):
        # Fallback: if raw_output is already a list of model outputs
        model_outputs = raw_output
    elif isinstance(raw_output, dict):
        # Fallback: if raw_output is a single model output
        model_outputs = [raw_output]

    # Use MC2 as primary prediction if available, otherwise use aggregation
    if mc2_output and mc2_output.get('success', False):
        # Use MC2 predictions directly as primary
        mc2_pred = mc2_output.get('prediction')
        if mc2_pred is not None:
            if isinstance(mc2_pred, str):
                if mc2_pred.lower() == 'secure':
                    result['y_pred'] = 1
                elif mc2_pred.lower() == 'insecure':
                    result['y_pred'] = 0
            else:
                result['y_pred'] = mc2_pred

        # Use MC2 probabilities
        if mc2_output.get('secure_probability') is not None:
            result['secure_probability'] = mc2_output.get('secure_probability')
        if mc2_output.get('insecure_probability') is not None:
            result['insecure_probability'] = mc2_output.get('insecure_probability')
        if mc2_output.get('confidence') is not None:
            result['confidence'] = mc2_output.get('confidence')

    elif model_outputs:
        # Fallback: Use majority voting for y_pred if MC2 not available
        predictions = [model_out.get('prediction') for model_out in model_outputs if 'prediction' in model_out]
        if predictions:
            from collections import Counter
            # Map 'Secure' to 1, 'Insecure' to 0
            numeric_predictions = []
            for pred in predictions:
                if isinstance(pred, str):
                    if pred.lower() == 'secure':
                        numeric_predictions.append(1)
                    elif pred.lower() == 'insecure':
                        numeric_predictions.append(0)
                else:
                    numeric_predictions.append(pred)

            # Use majority voting
            if numeric_predictions:
                result['y_pred'] = Counter(numeric_predictions).most_common(1)[0][0]

        # Average the probabilities
        secure_probs = [model_out.get('secure_probability', 0) for model_out in model_outputs if model_out.get('secure_probability') is not None]
        insecure_probs = [model_out.get('insecure_probability', 0) for model_out in model_outputs if model_out.get('insecure_probability') is not None]

        if secure_probs:
            result['secure_probability'] = sum(secure_probs) / len(secure_probs)
        if insecure_probs:
            result['insecure_probability'] = sum(insecure_probs) / len(insecure_probs)

        # Calculate confidence from probabilities
        if 'secure_probability' in result and 'insecure_probability' in result:
            result['confidence'] = max(result['secure_probability'], result['insecure_probability'])

    # Store individual model outputs for all models
    if model_outputs:
        for model_out in model_outputs:
            model_type = model_out.get('model_type', 'unknown')
            # Clean model_type for use as column name (remove spaces, lowercase)
            clean_model_type = model_type.lower().replace(' ', '_').replace('model', '').replace('multimodal', 'mm').strip('_')
            result[f'{clean_model_type}_prediction'] = model_out.get('prediction')
            result[f'{clean_model_type}_confidence'] = model_out.get('confidence')
            result[f'{clean_model_type}_secure_prob'] = model_out.get('secure_probability')
            result[f'{clean_model_type}_insecure_prob'] = model_out.get('insecure_probability')

    return result

def transform_model_output_annif(raw_output: Any, model_metadata: 'Modelmetadata', file_info: Dict[str, Any]) -> Dict[str, Any]:
    """Transform Annif model output - extract labels and scores"""
    result = {
        'file_path': file_info['file_path'],
        'file_name': file_info['file_name'],
        'model_id': model_metadata.id,
        'model_name': model_metadata.name,
    }

    # Add metadata
    result.update(file_info.get('metadata', {}))

    # Extract Annif output
    if isinstance(raw_output, dict) and 'output' in raw_output:
        output_data = raw_output['output']

        if output_data.get('success') and 'results' in output_data:
            results = output_data['results']

            # Extract labels as comma-separated string
            labels = [item.get('label', '') for item in results if 'label' in item]
            result['predicted_subjects'] = '; '.join(labels)  # Semicolon-separated for better readability

            # Extract top 3 labels for quick view
            top_3_labels = labels[:3] if len(labels) >= 3 else labels
            result['top_subjects'] = '; '.join(top_3_labels)

            # Store full results as JSON string for detailed analysis
            result['full_results'] = json.dumps(results)

            # Add metadata
            result['project_id'] = output_data.get('project_id', 'unknown')
            result['subject_count'] = output_data.get('count', len(results))
            result['prediction_success'] = True
        else:
            # Handle error case
            result['predicted_subjects'] = ''
            result['top_subjects'] = ''
            result['error'] = output_data.get('error', 'Unknown error')
            result['prediction_success'] = False

    # Store raw output
    result['raw_model_output'] = json.dumps(raw_output) if not isinstance(raw_output, str) else raw_output

    return result

def transform_model_output(raw_output: Any, model_metadata: 'Modelmetadata', file_info: Dict[str, Any]) -> Dict[str, Any]:
    """Transform raw model output based on model metadata."""
    # Check if this is Annif model
    model_name = model_metadata.name.lower()
    is_annif = 'annif' in model_name

    if is_annif:
        return transform_model_output_annif(raw_output, model_metadata, file_info)

    # Initialize result with file metadata
    result = {
        'file_path': file_info['file_path'],
        'file_name': file_info['file_name'],
        'file_type': file_info['file_type'],
        'model_id': model_metadata.id,
        'model_name': model_metadata.name,
        'model_task': model_metadata.task,
        'output_context': model_metadata.output_context,
    }

    # Add file metadata
    result.update(file_info['metadata'])

    # Add input data if available
    if file_info['data']:
        if isinstance(file_info['data'], dict):
            result.update({f"input_{k}": v for k, v in file_info['data'].items()})
        else:
            result['input_data'] = file_info['data']

    # Transform output based on model type
    is_generative = bool(model_metadata.model_type)
    
    if not is_generative:  # Predictive AI
        if isinstance(raw_output, dict) and 'output' in raw_output:
            output_data = raw_output['output']
            if isinstance(output_data, dict):
                # Extract prediction fields
                prediction_fields = {
                    'prediction': 'y_pred',
                    'secure_probability': 'y_pred_proba',
                    'insecure_probability': 'y_pred_proba_insecure', 
                    'confidence': 'confidence',
                    'model_type': 'model_subtype_used',
                    'success': 'prediction_success'
                }
                
                for src_field, dest_field in prediction_fields.items():
                    if src_field in output_data:
                        result[dest_field] = output_data[src_field]
        elif isinstance(raw_output, (int, float, str, bool)):
            result['y_pred'] = raw_output
    
    else:  # Generative AI
        if isinstance(raw_output, dict):
            generation_fields = {
                'output': 'generated_text',
                'success': 'generation_success',
                'usage': 'token_usage',
                'cost': 'generation_cost',
                'error': 'generation_error'
            }
            
            for src_field, dest_field in generation_fields.items():
                if src_field in raw_output:
                    result[dest_field] = raw_output[src_field]
        else:
            result['generated_text'] = str(raw_output)
    
    # Store raw output
    result['raw_model_output'] = json.dumps(raw_output) if not isinstance(raw_output, str) else raw_output
    
    return result


def run_model_inference(model_metadata: 'Modelmetadata', input_data: Dict[str, Any], api_key: Optional[str] = None) -> Any:
    """Run inference using either server request or direct function call."""
    model_location = model_metadata.location

    # Add http:// if missing
    if model_location and not model_location.startswith(('http://', 'https://')):
        model_location = f"http://{model_location}"
    
    if model_location.lower() == "with_api_key":
        if not bool(model_metadata.model_type):
            raise ValueError("run_inference is only supported for Generative AI models")
        
        if not api_key:
            raise ValueError("API key required for run_inference")
        
        # Determine provider and model name
        model_name = model_metadata.name.lower()
        if 'gpt' in model_name or 'openai' in model_name:
            input_data["model_provider"] = 'openai'
        elif 'claude' in model_name or 'anthropic' in model_name:
            input_data["model_provider"] = 'anthropic'
        elif 'gemini' in model_name or 'google' in model_name:
            input_data["model_provider"] = 'gemini'
        else:
            input_data["model_provider"] = 'openai'
        
        input_data["api_key"]= api_key
        
        try:
            response = requests.post(f"{model_location}/predict", json=input_data, timeout=60)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return {"error": str(e), "success": False}
    
    else:
        # Server request
        try:
            # Check if this is an Annif model (requires form-urlencoded format)
            model_name = model_metadata.name.lower()
            is_annif = 'annif' in model_name or 'annif' in model_location.lower()

            if is_annif:
                # Annif local wrapper expects JSON format with specific fields
                json_data = {
                    'text': input_data.get('text', ''),
                    'project_id': input_data.get('project_id', 'yso-en'),  # Default project
                    'limit': 15,
                    'threshold': input_data.get('threshold', 0.0)
                }
                print(f"Sending POST to {model_location}/predict")
                response = requests.post(
                    f"{model_location}/predict",
                    json=json_data,  # Send as JSON (not form-urlencoded)
                    timeout=60
                )
            else:
                # Regular JSON request for other models (SAM, etc.)
                print(f"Sending POST to {model_location}/predict with data: {input_data}")
                response = requests.post(f"{model_location}/predict", json=input_data, timeout=60)

            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Request failed: {e}")
            return {"error": str(e), "success": False}


def run_evaluation(
    session: Session,
    model_metadata: Modelmetadata,
    input_dataset_metadata: InputDatasetMetadata,
    output_dataset_metadata: OutputDatasetMetadata,
    metric_name: str,
    user_id: Optional[str] = None,
    storage_base_path: str = "storage",
    api_key = None,
    metric_value_id: Optional[int] = None  # NEW: specific MetricsValues.id to evaluate
) -> Dict[str, Any]:
    """
    Run model evaluation with storage-aware file handling.
    First checks for existing results.csv and metadata.csv in output, otherwise performs inference.
    
    Args:
        session: Database session
        model_metadata: Model metadata
        input_dataset_metadata: Input dataset metadata
        output_dataset_metadata: Output dataset metadata  
        metric_name: Evaluation metric name
        user_id: User ID for API key lookup
        storage_base_path: Base path for storage directory
        
    Returns:
        Evaluation results dictionary
    """
    # try:
    storage_manager = StorageManager(storage_base_path)
    
    # Extract metadata
    model_name = model_metadata.name
    model_location = model_metadata.location
    input_location = input_dataset_metadata.location
    output_location = output_dataset_metadata.location
    datatypes_info = input_dataset_metadata.datatypes or {}

    # Get API key if needed
    if model_location == "run_inference" and user_id and model_metadata.id:
        raise ValueError("No api key contact the Audit Instigator")

    metadata_manager = InputFileMetadataManager(storage_base_path)

    # First, check if results.csv and metadata.csv exist in the output directory
    actual_input_path, _ = parse_storage_location(input_location, storage_manager)
    input_path = Path(actual_input_path)
    actual_output_path, _ = parse_storage_location(output_location, storage_manager)
    output_path = Path(actual_output_path)

    # If output_path is a directory, append results.csv to it
    if output_path.is_dir():
        results_csv_path = output_path / "results.csv"
    else:
        results_csv_path = output_path

    metadata_csv_path = input_path / "metadata.csv"

    if results_csv_path.exists():
        print(f"Found existing results.csv at: {results_csv_path}")
        
        # try:
        # Load existing results - try different separators
        try:
            results_df = pd.read_csv(results_csv_path)
            # If we only get one column, try different separators
            if len(results_df.columns) == 1:
                if ', ' in results_df.columns[0]:
                    results_df = pd.read_csv(results_csv_path, sep=', ')
                elif '\t' in results_df.columns[0]:
                    results_df = pd.read_csv(results_csv_path, sep='\t')
        except:
            # Try comma with space as separator
            try:
                results_df = pd.read_csv(results_csv_path, sep=', ')
            except:
                results_df = pd.read_csv(results_csv_path, sep='\t')

        # Clean column names by stripping whitespace
        results_df.columns = results_df.columns.str.strip()
        print(f"Loaded results.csv with {len(results_df)} rows")

        # Check if results has multiple runs that need aggregation
        if 'child_id' in results_df.columns and 'run' in results_df.columns:
            unique_participants = results_df['child_id'].nunique()
            total_rows = len(results_df)

            if total_rows > unique_participants:
                num_runs = total_rows // unique_participants
                print(f"\n{'='*80}")
                print(f"DETECTED MULTIPLE RUNS IN RESULTS")
                print(f"Total rows: {total_rows}")
                print(f"Unique participants: {unique_participants}")
                print(f"Number of runs detected: {num_runs}")
                print(f"Aggregating predictions across {num_runs} runs per participant...")
                print(f"{'='*80}\n")

                # Aggregate predictions by taking mode (most common) across runs for each participant
                # For 'output' column, take the mode (most common prediction across runs)
                if 'output' in results_df.columns:
                    aggregated_results = results_df.groupby('child_id', as_index=False).agg({
                        'output': lambda x: x.mode()[0] if not x.mode().empty else x.iloc[0]
                    })

                    # Rename child_id to id for consistency
                    aggregated_results['id'] = aggregated_results['child_id']

                    print(f"Aggregated results from {total_rows} rows to {len(aggregated_results)} unique participants")
                    print(f"Sample aggregated predictions:")
                    print(aggregated_results.head(10))
                    print()

                    results_df = aggregated_results

        # Check if metadata.csv exists and load it
        combined_df = results_df.copy()

        if metadata_csv_path.exists():
            print(f"Found metadata.csv at: {metadata_csv_path}")
            try:
                metadata_df = pd.read_csv(metadata_csv_path)
                # If we only get one column, try different separators
                if len(metadata_df.columns) == 1:
                    if ', ' in metadata_df.columns[0]:
                        metadata_df = pd.read_csv(metadata_csv_path, sep=', ')
                    elif '\t' in metadata_df.columns[0]:
                        metadata_df = pd.read_csv(metadata_csv_path, sep='\t')
            except:
                # Try comma with space as separator
                try:
                    metadata_df = pd.read_csv(metadata_csv_path, sep=', ')
                except:
                    metadata_df = pd.read_csv(metadata_csv_path, sep='\t')

            # Clean column names by stripping whitespace
            metadata_df.columns = metadata_df.columns.str.strip()
            print(f"Loaded metadata.csv with {len(metadata_df)} rows")

            # Check if metadata has multiple runs (more rows than results)
            if 'id' in metadata_df.columns and 'child_id' in metadata_df.columns:
                # Detect if we have multiple runs per participant
                unique_ids = metadata_df['id'].nunique()
                total_rows = len(metadata_df)

                if total_rows > unique_ids:
                    num_runs = total_rows // unique_ids
                    print(f"Detected {num_runs} runs with {unique_ids} unique participants")
                    print(f"Aggregating metadata across {num_runs} runs per participant...")

                    # Group by child_id and aggregate
                    # For categorical columns (gender, age), take the first value (they should be the same across runs)
                    # For true_value, we'll take mode (most common value) or first if tie
                    agg_dict = {}

                    # Keep first value for demographic info
                    for col in ['gender', 'age', 'file']:
                        if col in metadata_df.columns:
                            agg_dict[col] = 'first'

                    # For true_value, aggregate by taking the mode (most common value across runs)
                    if 'true_value' in metadata_df.columns:
                        agg_dict['true_value'] = lambda x: x.mode()[0] if not x.mode().empty else x.iloc[0]

                    # Aggregate by child_id
                    aggregated_metadata = metadata_df.groupby('child_id', as_index=False).agg(agg_dict)

                    # Rename child_id to id for merging with results
                    aggregated_metadata['id'] = aggregated_metadata['child_id']

                    print(f"Aggregated metadata to {len(aggregated_metadata)} unique participants")
                    print(f"Sample aggregated data:")
                    print(aggregated_metadata.head())

                    metadata_df = aggregated_metadata

            # Merge on 'id' column if it exists in both
            if 'id' in results_df.columns and 'id' in metadata_df.columns:
                combined_df = pd.merge(results_df, metadata_df, on='id', how='left')
                print(f"Merged datasets on 'id' column, resulting in {len(combined_df)} rows")
            else:
                print("Warning: 'id' column not found in both files, cannot merge")
                # If no id column, try to merge by index
                if len(results_df) == len(metadata_df):
                    combined_df = pd.concat([results_df, metadata_df], axis=1)
                    print("Merged by index position")
                else:
                    print("Cannot merge: different number of rows and no common 'id' column")
        else:
            print("No metadata.csv found, using results.csv only")
        
        # Map column names for evaluation
        output_df = combined_df.copy()

        # Clean column names by stripping whitespace
        output_df.columns = output_df.columns.str.strip()

        # Map 'output' column to 'y_pred' if it exists
        if 'output' in output_df.columns:
            # Try to extract predictions from output column
            if output_df['output'].dtype == 'object':
                # If output contains JSON or structured data, try to parse
                try:
                    # Try to parse as JSON first
                    parsed_outputs = output_df['output'].apply(lambda x: json.loads(x) if isinstance(x, str) else x)
                    # If parsed outputs are dicts, try to extract prediction
                    if parsed_outputs.iloc[0] and isinstance(parsed_outputs.iloc[0], dict):
                        if 'prediction' in parsed_outputs.iloc[0]:
                            output_df['y_pred'] = parsed_outputs.apply(lambda x: x.get('prediction') if isinstance(x, dict) else x)
                        elif 'output' in parsed_outputs.iloc[0]:
                            output_df['y_pred'] = parsed_outputs.apply(lambda x: x.get('output') if isinstance(x, dict) else x)
                        else:
                            # Use the output column directly
                            output_df['y_pred'] = output_df['output']
                    else:
                        output_df['y_pred'] = output_df['output']
                except:
                    # If parsing fails, use output column directly
                    output_df['y_pred'] = output_df['output']
            else:
                output_df['y_pred'] = output_df['output']
        
        # Map 'true_value' to 'y_true' if it exists
        if 'true_value' in output_df.columns:
            output_df['y_true'] = output_df['true_value']

        # Convert string predictions to numeric values for evaluation
        if 'y_pred' in output_df.columns:
            # Check if y_pred contains string values that need encoding
            if output_df['y_pred'].dtype == 'object':
                # Common mappings for security predictions
                secure_values = ['secure', 'safe', 'positive', '1', 'true', 'yes']
                insecure_values = ['insecure', 'unsafe', 'negative', '0', 'false', 'no']

                # Create a mapping function
                def map_prediction(val):
                    if pd.isna(val):
                        return val
                    val_str = str(val).lower().strip()
                    if val_str in secure_values:
                        return 1
                    elif val_str in insecure_values:
                        return 0
                    else:
                        # Try to convert to float if possible
                        try:
                            return float(val_str)
                        except:
                            return val  # Keep original if can't convert

                output_df['y_pred'] = output_df['y_pred'].apply(map_prediction)

        if 'y_true' in output_df.columns:
            # Check if y_true contains string values that need encoding
            if output_df['y_true'].dtype == 'object':
                # Same mapping for ground truth
                secure_values = ['secure', 'safe', 'positive', '1', 'true', 'yes']
                insecure_values = ['insecure', 'unsafe', 'negative', '0', 'false', 'no']

                def map_true_value(val):
                    if pd.isna(val):
                        return val
                    val_str = str(val).lower().strip()
                    if val_str in secure_values:
                        return 1
                    elif val_str in insecure_values:
                        return 0
                    else:
                        try:
                            return float(val_str)
                        except:
                            return val

                output_df['y_true'] = output_df['y_true'].apply(map_true_value)
        
        # Add sensitive attributes with label_ prefix for easier identification
        sensitive_attrs = ['gender', 'age']
        for attr in sensitive_attrs:
            if attr in output_df.columns:
                output_df[f'label_{attr}'] = output_df[attr]
        
        # Update output dataset metadata
        output_dataset_metadata.headers = {col: f"Column {col}" for col in output_df.columns}
        output_dataset_metadata.datatypes = {col: str(output_df[col].dtype) for col in output_df.columns}
        output_dataset_metadata.location = str(results_csv_path)
        
        # Run evaluation on existing results
        evaluation_result = None
        if metric_name:
            try:
                print(f"Running evaluation with metric function: {metric_name}")
                print(f"Specific MetricsValues ID: {metric_value_id}")

                # If metric_value_id is provided, only evaluate underlying features for that specific record
                if metric_value_id:
                    # Get underlying features for the specific MetricsValues record
                    metric_values = session.exec(
                        select(MetricsValues, MetricsUnderlyingFeatures, UnderlyingFeatures)
                        .join(MetricsUnderlyingFeatures, MetricsValues.id == MetricsUnderlyingFeatures.metric_values_id)
                        .join(UnderlyingFeatures, MetricsUnderlyingFeatures.feature_id == UnderlyingFeatures.id)
                        .where(MetricsValues.id == metric_value_id)
                    ).all()

                    print(f"Found {len(metric_values)} underlying features for MetricsValues.id={metric_value_id}")
                else:
                    # Fallback: Find metric by matching target feature function_name
                    metric_with_target = session.exec(
                        select(Metrics, TargetFeatures)
                        .join(MetricsTargetFeatures, Metrics.id == MetricsTargetFeatures.metric_values_id)
                        .join(TargetFeatures, MetricsTargetFeatures.target_feature_id == TargetFeatures.id)
                        .where(TargetFeatures.function_name == metric_name)
                    ).first()

                    metric = None
                    if metric_with_target:
                        metric, target_feature = metric_with_target
                        print(f"Found metric via target feature:")
                        print(f"  - Metric: {metric.name} (ID: {metric.id})")
                        print(f"  - Target Feature: {target_feature.target_feature} (Function: {target_feature.function_name})")

                    if metric:
                        # Get metric values with underlying features
                        metric_values = session.exec(
                            select(MetricsValues, MetricsUnderlyingFeatures, UnderlyingFeatures)
                            .join(MetricsUnderlyingFeatures, MetricsValues.id == MetricsUnderlyingFeatures.metric_values_id)
                            .join(UnderlyingFeatures, MetricsUnderlyingFeatures.feature_id == UnderlyingFeatures.id)
                            .join(MetricsTargetFeatures, MetricsValues.id == MetricsTargetFeatures.metric_values_id)
                            .join(TargetFeatures, MetricsTargetFeatures.target_feature_id == TargetFeatures.id)
                            .where(TargetFeatures.function_name == metric_name)
                        ).all()
                    else:
                        print(f"No metric found with target feature function_name = '{metric_name}'")
                        metric_values = []

                if metric_values:
                    print(f"\n{'='*80}")
                    print(f"UNDERLYING FEATURES QUERY RESULTS:")
                    print(f"Total rows returned: {len(metric_values)}")
                    for idx, (mv, fm, feat) in enumerate(metric_values):
                        print(f"\nRow {idx + 1}:")
                        print(f"  - MetricsValues.id: {mv.id}")
                        print(f"  - UnderlyingFeatures.id: {feat.id}")
                        print(f"  - UnderlyingFeatures.feature_name: '{feat.feature_name}'")
                        print(f"  - MetricsUnderlyingFeatures.ranges: {fm.ranges}")
                    print(f"\nDataFrame columns available: {list(output_df.columns)}")
                    print(f"{'='*80}\n")

                    # First, collect all features and their configurations
                    features_config = []
                    for _, feature_mapping, feature in metric_values:
                        feature_name = feature.feature_name
                        ranges = feature_mapping.ranges or []
                        if not isinstance(ranges, list):
                            ranges = []

                        range_groups, expanded_ranges = parse_range_groups(ranges)
                        features_config.append({
                            'feature_name': feature_name,
                            'ranges': ranges,
                            'range_groups': range_groups,
                            'expanded_ranges': expanded_ranges
                        })

                    print(f"Features configuration: {features_config}")

                    # Determine if we should do cross-tabulation (multiple features with ranges)
                    features_with_ranges = [f for f in features_config if len(f['ranges']) > 0]
                    use_cross_tabulation = len(features_with_ranges) > 1
                    print(f"Cross-tabulation mode: {use_cross_tabulation} ({len(features_with_ranges)} features with ranges)")

                    # Structure results by underlying features
                    underlying_features_results = {}

                    # If cross-tabulation is needed, use specialized function
                    if use_cross_tabulation:
                        print("Using cross-tabulation for multiple features")

                        # Detect column names for keyword accuracy
                        expected_col = None
                        predicted_col = None
                        if metric_name in ['keyword_accuracy', 'batch_keyword_accuracy']:
                            for col in output_df.columns:
                                if col == 'expected_subjects' or col.startswith('expected_subjects_'):
                                    expected_col = col
                                if col == 'predicted_subjects' or col.startswith('predicted_subjects_'):
                                    predicted_col = col

                        # Prepare base eval_kwargs
                        eval_kwargs_base = {}
                        if metric_name in ['keyword_accuracy', 'batch_keyword_accuracy']:
                            if expected_col and predicted_col:
                                eval_kwargs_base['y_true'] = output_df[expected_col].fillna('').values
                                eval_kwargs_base['y_pred'] = output_df[predicted_col].fillna('').values
                        else:
                            if 'y_pred' in output_df.columns:
                                eval_kwargs_base['y_pred'] = output_df['y_pred'].dropna().values
                            if 'y_true' in output_df.columns:
                                eval_kwargs_base['y_true'] = output_df['y_true'].dropna().values
                            if 'y_pred_proba' in output_df.columns:
                                eval_kwargs_base['y_pred_proba'] = output_df['y_pred_proba'].dropna().values

                        # Create cross-tabulated results
                        cross_tab_results = create_cross_tabulation_results(
                            output_df=output_df,
                            features_config=features_with_ranges,
                            metric_name=metric_name,
                            eval_kwargs_base=eval_kwargs_base,
                            expected_col=expected_col,
                            predicted_col=predicted_col
                        )

                        # Store cross-tab results directly (not nested by feature name)
                        underlying_features_results = cross_tab_results

                    # Otherwise, process each feature independently (original behavior)
                    else:
                        for _, feature_mapping, feature in metric_values:
                            feature_name = feature.feature_name
                            ranges = feature_mapping.ranges or []

                        # Ensure ranges is a list
                        if not isinstance(ranges, list):
                            ranges = []

                        if feature_name not in underlying_features_results:
                            underlying_features_results[feature_name] = {}

                        # Parse ranges to handle grouped values (e.g., "P1-P2" -> ["P1", "P2"])
                        range_groups, expanded_ranges = parse_range_groups(ranges)
                        print(f"  Range groups: {range_groups}")
                        print(f"  Expanded ranges: {expanded_ranges}")

                        # Calculate metric with the underlying feature as sensitive attribute
                        eval_kwargs = {}

                        # Detect column names for keyword accuracy (needed for both initial setup and filtering)
                        expected_col = None
                        predicted_col = None
                        if metric_name in ['keyword_accuracy', 'batch_keyword_accuracy']:
                            for col in output_df.columns:
                                if col == 'expected_subjects' or col.startswith('expected_subjects_'):
                                    expected_col = col
                                if col == 'predicted_subjects' or col.startswith('predicted_subjects_'):
                                    predicted_col = col

                        # Special handling for keyword accuracy (ANNIF models)
                        if metric_name in ['keyword_accuracy', 'batch_keyword_accuracy']:
                            if expected_col and predicted_col:
                                eval_kwargs['y_true'] = output_df[expected_col].fillna('').values
                                eval_kwargs['y_pred'] = output_df[predicted_col].fillna('').values
                        else:
                            # Standard metrics use y_pred and y_true
                            if 'y_pred' in output_df.columns:
                                eval_kwargs['y_pred'] = output_df['y_pred'].dropna().values
                            if 'y_true' in output_df.columns:
                                eval_kwargs['y_true'] = output_df['y_true'].dropna().values
                            if 'y_pred_proba' in output_df.columns:
                                eval_kwargs['y_pred_proba'] = output_df['y_pred_proba'].dropna().values

                        # Add the underlying feature as sensitive attribute
                        # Try exact match first, then case-insensitive match
                        sensitive_col = None
                        if feature_name in output_df.columns:
                            sensitive_col = feature_name
                        else:
                            # Try case-insensitive match
                            for col in output_df.columns:
                                if col.lower() == feature_name.lower():
                                    sensitive_col = col
                                    break

                        if sensitive_col:
                            # Filter data to only include rows where the sensitive attribute matches defined ranges (if any)
                            if ranges:
                                # Create mask for rows that match any of the EXPANDED individual values
                                mask = pd.Series([False] * len(output_df), index=output_df.index)
                                for individual_val in expanded_ranges:
                                    individual_val_str = str(individual_val).lower()
                                    col_mask = output_df[sensitive_col].astype(str).str.lower() == individual_val_str
                                    mask = mask | col_mask

                                # Apply mask to get only data within defined ranges
                                filtered_df = output_df[mask]
                                print(f"  Filtered to {len(filtered_df)} rows (from {len(output_df)}) matching expanded ranges: {expanded_ranges}")

                                # Check if filtered data is empty - means ranges don't match output data
                                if len(filtered_df) == 0:
                                    print(f"  WARNING: No data found matching defined ranges {expanded_ranges}")
                                    print(f"  Available values in output: {output_df[sensitive_col].unique().tolist()}")
                                    print(f"  Skipping evaluation for {feature_name} - ranges need to be updated to match output data")
                                    underlying_features_results[feature_name] = {
                                        'status': 'no_matching_data',
                                        'error': f'No data found matching defined ranges: {ranges}',
                                        'defined_ranges': ranges,
                                        'expanded_ranges': expanded_ranges,
                                        'available_values': output_df[sensitive_col].unique().tolist(),
                                        'message': 'Please update the ranges to match the available values in the output data, or leave ranges empty to evaluate all values.'
                                    }
                            else:
                                # No ranges defined, use all data
                                filtered_df = output_df
                                print(f"  No ranges defined, using all {len(filtered_df)} rows")

                            # Get non-null values from filtered data
                            valid_indices = filtered_df[sensitive_col].notna()
                            eval_kwargs['sensitive_attr'] = filtered_df.loc[valid_indices, sensitive_col].values

                            # Also filter other columns to match indices
                            # For keyword_accuracy, preserve the expected_subjects/predicted_subjects columns
                            if metric_name in ['keyword_accuracy', 'batch_keyword_accuracy']:
                                if expected_col and expected_col in filtered_df.columns:
                                    eval_kwargs['y_true'] = filtered_df.loc[valid_indices, expected_col].fillna('').values
                                if predicted_col and predicted_col in filtered_df.columns:
                                    eval_kwargs['y_pred'] = filtered_df.loc[valid_indices, predicted_col].fillna('').values
                            else:
                                # Standard metrics
                                if 'y_pred' in filtered_df.columns:
                                    eval_kwargs['y_pred'] = filtered_df.loc[valid_indices, 'y_pred'].dropna().values
                                if 'y_true' in filtered_df.columns:
                                    eval_kwargs['y_true'] = filtered_df.loc[valid_indices, 'y_true'].dropna().values
                                if 'y_pred_proba' in filtered_df.columns:
                                    eval_kwargs['y_pred_proba'] = filtered_df.loc[valid_indices, 'y_pred_proba'].dropna().values
                        else:
                            print(f"Warning: Feature '{feature_name}' not found in dataframe columns: {list(output_df.columns)}")

                        if len(eval_kwargs) >= 2 and 'sensitive_attr' in eval_kwargs:
                            try:
                                print(f"Evaluating {metric_name} for {feature_name} with {len(eval_kwargs['sensitive_attr'])} samples")
                                print(f"  Original ranges: {ranges}")
                                print(f"  Expanded ranges: {expanded_ranges}")

                                # Check unique values in the sensitive attribute
                                unique_values = set(eval_kwargs['sensitive_attr'])
                                print(f"  Unique values in data: {unique_values}")

                                # Check for mismatches between defined ranges and actual data
                                if ranges:
                                    expanded_ranges_lower = [str(r).lower() for r in expanded_ranges]
                                    unique_values_lower = [str(v).lower() for v in unique_values]

                                    # Check for unexpected values in data (not in defined ranges)
                                    unexpected_values = [v for v in unique_values if str(v).lower() not in expanded_ranges_lower]
                                    if unexpected_values:
                                        print(f"  WARNING: Data contains values not in defined ranges: {unexpected_values}")

                                    # Check for missing values (defined ranges not found in data)
                                    missing_values = [r for r in expanded_ranges if str(r).lower() not in unique_values_lower]
                                    if missing_values:
                                        print(f"  WARNING: Some defined ranges not found in data: {missing_values}")
                                        print(f"  Note: Results will only include data for values that exist: {list(unique_values)}")

                                result = evaluate_function(metric_name, **eval_kwargs)

                                # Check if metric calculation failed
                                if isinstance(result, dict) and result.get("status") == "cannot be calculated":
                                    underlying_features_results[feature_name] = result
                                # The detailed metrics return results grouped by feature values
                                # Some metrics return {'groups': {...}}, others return direct dict of groups
                                elif isinstance(result, dict):
                                    # Determine if this is a grouped result
                                    if 'groups' in result:
                                        all_groups = result['groups']
                                    else:
                                        # Check if result is a dict of group results (each value is a dict with metrics)
                                        # by checking if keys match sensitive_attr values and values are dicts
                                        unique_values_str = set(str(v) for v in eval_kwargs.get('sensitive_attr', []))
                                        result_keys_str = set(str(k) for k in result.keys())

                                        # If result keys overlap with sensitive attr values, it's grouped results
                                        if result_keys_str & unique_values_str:
                                            all_groups = result
                                        else:
                                            # Single result, not grouped
                                            underlying_features_results[feature_name] = {'overall': result}
                                            all_groups = None

                                    # Process ranges: combine groups if needed based on range_groups
                                    if all_groups is not None:
                                        if ranges:
                                            processed_groups = {}

                                            for original_range, individual_values in range_groups.items():
                                                if len(individual_values) > 1:
                                                    # This is a grouped range (e.g., "P1-P2" or "P2-P4")
                                                    # Combine results from all individual values using confusion matrix combination
                                                    combined_result = combine_classification_results(all_groups, individual_values)
                                                    if combined_result is not None:
                                                        processed_groups[original_range] = combined_result
                                                    else:
                                                        # Fallback to simple combination
                                                        combined_result = combine_group_results(all_groups, individual_values)
                                                        if combined_result is not None:
                                                            processed_groups[original_range] = combined_result
                                                else:
                                                    # Single value range - keep as is
                                                    for group_key, group_result in all_groups.items():
                                                        if str(group_key).lower() == str(original_range).lower():
                                                            processed_groups[original_range] = group_result
                                                            break

                                            underlying_features_results[feature_name] = processed_groups
                                        else:
                                            # No ranges defined, use all groups
                                            underlying_features_results[feature_name] = all_groups
                                else:
                                    # Non-dict result
                                    underlying_features_results[feature_name] = {'overall': result}
                            except Exception as e:
                                error_msg = f"Error evaluating {metric_name} for {feature_name}: {str(e)}"
                                print(error_msg)
                                import traceback
                                traceback.print_exc()

                                # Include more details in the error
                                underlying_features_results[feature_name] = {
                                    'error': str(e),
                                    'error_type': type(e).__name__,
                                    'feature_name': feature_name,
                                    'defined_ranges': ranges if ranges else [],
                                    'data_sample_count': len(eval_kwargs.get('sensitive_attr', [])),
                                    'unique_values_in_data': list(set(eval_kwargs.get('sensitive_attr', []))) if 'sensitive_attr' in eval_kwargs else []
                                }
                        else:
                            print(f"Insufficient data for {feature_name}: eval_kwargs keys = {list(eval_kwargs.keys())}")

                    # Convert numpy types to JSON serializable types (including dict keys)
                    import numpy as np
                    def convert_numpy(obj):
                        if isinstance(obj, np.ndarray):
                            return obj.tolist()
                        elif isinstance(obj, dict):
                            # Convert both keys and values
                            converted_dict = {}
                            for k, v in obj.items():
                                # Convert numpy keys to native Python types
                                if isinstance(k, (np.int64, np.int32, np.int16, np.int8)):
                                    new_key = int(k)
                                elif isinstance(k, (np.float64, np.float32, np.float16)):
                                    new_key = float(k)
                                elif isinstance(k, np.str_):
                                    new_key = str(k)
                                else:
                                    new_key = k
                                converted_dict[new_key] = convert_numpy(v)
                            return converted_dict
                        elif isinstance(obj, list):
                            return [convert_numpy(item) for item in obj]
                        elif isinstance(obj, (np.int64, np.int32, np.int16, np.int8)):
                            return int(obj)
                        elif isinstance(obj, (np.float64, np.float32, np.float16)):
                            return float(obj)
                        elif isinstance(obj, np.str_):
                            return str(obj)
                        else:
                            return obj

                    evaluation_result = {"underlying_features": convert_numpy(underlying_features_results)}
                    print(f"Evaluation completed with underlying features structure: {evaluation_result}")
                else:
                    # Fallback if metric not found in database
                    eval_kwargs = {}

                    # Special handling for keyword accuracy (ANNIF models)
                    if metric_name in ['keyword_accuracy', 'batch_keyword_accuracy']:
                        # Handle column names with potential _x, _y suffixes from joins
                        expected_col = None
                        predicted_col = None

                        for col in output_df.columns:
                            if col == 'expected_subjects' or col.startswith('expected_subjects_'):
                                expected_col = col
                            if col == 'predicted_subjects' or col.startswith('predicted_subjects_'):
                                predicted_col = col

                        if expected_col and predicted_col:
                            eval_kwargs['y_true'] = output_df[expected_col].fillna('').values
                            eval_kwargs['y_pred'] = output_df[predicted_col].fillna('').values
                        elif expected_col and not predicted_col:
                            # Have expected_subjects but no predicted_subjects - need to run output classification first
                            evaluation_result = {
                                "error": "Missing predicted_subjects column",
                                "message": "Please run output classification first (/results/{audit_id}/generate/output) to generate predictions before evaluating.",
                                "available_columns": list(output_df.columns),
                                "found_expected": expected_col,
                                "missing": "predicted_subjects"
                            }
                            print(f"❌ Cannot evaluate keyword_accuracy: found {expected_col} but missing predicted_subjects column")
                            print(f"   Run output classification endpoint first to generate ANNIF predictions")
                            return evaluation_result
                    else:
                        # Standard metrics
                        if 'y_pred' in output_df.columns:
                            eval_kwargs['y_pred'] = output_df['y_pred'].dropna().values
                        if 'y_true' in output_df.columns:
                            eval_kwargs['y_true'] = output_df['y_true'].dropna().values

                    print(f"🔍 eval_kwargs keys: {list(eval_kwargs.keys())}, len={len(eval_kwargs)}")
                    if 'y_true' in eval_kwargs:
                        print(f"   y_true samples: {len(eval_kwargs['y_true'])}")
                    if 'y_pred' in eval_kwargs:
                        print(f"   y_pred samples: {len(eval_kwargs['y_pred'])}")

                    if len(eval_kwargs) >= 2:
                        print(f"✅ Running evaluation with {metric_name}")
                        result = evaluate_function(metric_name, **eval_kwargs)
                        evaluation_result = {"underlying_features": {"all": {"all": result}}}
                    else:
                        print(f"❌ Insufficient data - need at least 2 kwargs, got {len(eval_kwargs)}")
                        evaluation_result = {"warning": "Insufficient data for evaluation", "available_columns": list(output_df.columns)}

            except Exception as e:
                print(f"Evaluation failed: {str(e)}")
                evaluation_result = {"error": str(e), "available_columns": list(output_df.columns)}
    
        result_dict = {
            "success": True,
            "model_id": model_metadata.id,
            "model_name": model_name,
            "model_type": "Generative AI" if model_metadata.model_type else "Predictive AI",
            "total_entries_processed": len(output_df),
            # "successful_predictions": len(output_df[output_df.get('prediction_success', True) != False]),
            "input_location": input_location,
            "output_location": str(results_csv_path),
            "evaluation_result": evaluation_result,
            "metric_name": metric_name,
            "output_columns": list(output_df.columns),
            "used_existing_results": True,
            "results_source": "existing_results_csv",
            "metadata_merged": metadata_csv_path.exists(),
            "merged_rows": len(combined_df) if metadata_csv_path.exists() else len(results_df)
        }

        # If no evaluation was performed (metric_name is None), include the raw predictions
        # This is useful for qualitative metrics that need the model output
        if metric_name is None and not output_df.empty:
            # Replace NaN values with None before converting to dict
            # Use pandas fillna to handle all types of missing values
            predictions_df = output_df.where(pd.notnull(output_df), None)
            result_dict["predictions"] = predictions_df.to_dict('records')
            print(f"Including {len(predictions_df)} prediction records (no evaluation performed)")

        return result_dict
            
        # except Exception as e:
        #     print(f"Error loading existing results: {e}")
        #     print("Falling back to inference mode...")
    
    # No existing results.csv found or error loading it, proceed with inference
    print("Using enhanced metadata discovery for inference...")

    # Check if there's a metadata.csv in the input directory we can use
    actual_input_path, _ = parse_storage_location(input_location, storage_manager)
    input_path = Path(actual_input_path)
    input_metadata_path = input_path / "metadata.csv"
    print(input_metadata_path)
    if input_metadata_path.exists():
        print(f"📋 Found metadata.csv in input directory: {input_metadata_path}")
        # Read metadata.csv to determine available columns
        try:
            metadata_df = pd.read_csv(input_metadata_path)
            available_columns = [col for col in metadata_df.columns if col != 'file_name']
            print(f"📊 Metadata columns available: {available_columns}")
        except Exception as e:
            print(f"Could not read metadata.csv columns: {e}")
            # Fallback to common columns
            available_columns = ['id', 'gender', 'age', 'true_value', 'expected_subjects', 'notes']

        metadata_manager.add_metadata_file(
            str(input_metadata_path),
            'csv',
            'file_name',  # Column that maps to actual files
            available_columns  # Extract all available metadata columns
        )

    discovered_entries = discover_input_data_with_metadata(
        input_location, datatypes_info, storage_manager, metadata_manager
    )
    
    if not discovered_entries:
        raise ValueError(f"No valid input data found at: {input_location}")
    
    # Process each entry for inference
    print(f"Running inference with model: {model_name} at {model_location}")
    output_rows = []

    # Check if this is SAM model (Secure Attachment Model)
    is_sam_model = "sam" in model_name.lower() or "attachment" in model_name.lower() or "sentiment" in model_name.lower()
    print(f"Model name: {model_name}, is_sam_model: {is_sam_model}")

    for idx, file_info in enumerate(discovered_entries):
        print(f"Processing entry {idx + 1}/{len(discovered_entries)} - {file_info['file_name']}")

        try:
            # Prepare model input
            print(f"Preparing model input for {file_info['file_name']}")
            if is_sam_model:
                model_input = prepare_model_input_sam(file_info, model_metadata)
            else:
                model_input = prepare_model_input(file_info, model_metadata)
            # print(f"Model input prepared: {list(model_input.keys())}")

            # Run inference
            print(f"Calling model at {model_location}/predict")
            raw_output = run_model_inference(model_metadata, model_input, api_key)
            # print(f"Raw output received: {raw_output}")

            # Transform output
            if is_sam_model:
                transformed_output = transform_model_output_sam(raw_output, model_metadata, file_info)
            else:
                transformed_output = transform_model_output(raw_output, model_metadata, file_info)
            print(f"Transformed output: {transformed_output}")
            output_rows.append(transformed_output)
            
        except Exception as e:
            print(f"Error processing entry {idx + 1}: {e}")
            # Add error entry
            error_output = {
                'file_path': file_info['file_path'],
                'file_name': file_info['file_name'],
                'model_id': model_metadata.id,
                'model_name': model_metadata.name,
                'processing_error': str(e),
                'prediction_success': False
            }
            error_output.update(file_info['metadata'])
            output_rows.append(error_output)
    
    # Create output DataFrame
    output_df = pd.DataFrame(output_rows)
    # Save output data as results.csv in the output directory
    # Ensure parent directory exists (output_path might be a file path like results.csv)
    if output_path.suffix:  # If it has a file extension, it's a file path
        output_path.parent.mkdir(parents=True, exist_ok=True)
        actual_results_path = output_path
    else:  # It's a directory path
        output_path.mkdir(parents=True, exist_ok=True)
        actual_results_path = output_path / "results.csv"

    print(f"Saving inference results to: {actual_results_path}")
    output_df.to_csv(actual_results_path, index=False)
    
    # Update output dataset metadata
    output_dataset_metadata.headers = {col: f"Column {col}" for col in output_df.columns}
    output_dataset_metadata.datatypes = {col: str(output_df[col].dtype) for col in output_df.columns}
    output_dataset_metadata.location = str(actual_results_path)
    
    # Run evaluation if we have required columns
    evaluation_result = None
    if metric_name:
        try:
            print(f"Running evaluation with metric: {metric_name}")

            eval_kwargs = {}

            # Special handling for keyword accuracy (ANNIF models)
            if metric_name in ['keyword_accuracy', 'batch_keyword_accuracy']:
                expected_col = None
                predicted_col = None

                for col in output_df.columns:
                    if col == 'expected_subjects' or col.startswith('expected_subjects_'):
                        expected_col = col
                    if col == 'predicted_subjects' or col.startswith('predicted_subjects_'):
                        predicted_col = col

                if expected_col and predicted_col:
                    eval_kwargs['y_true'] = output_df[expected_col].fillna('').values
                    eval_kwargs['y_pred'] = output_df[predicted_col].fillna('').values
                    print(f"Found ANNIF columns: {expected_col}, {predicted_col}")
            else:
                # Standard classification metrics
                if 'y_pred' in output_df.columns:
                    eval_kwargs['y_pred'] = output_df['y_pred'].dropna().values
                if 'y_true' in output_df.columns:
                    eval_kwargs['y_true'] = output_df['y_true'].dropna().values
                if 'y_pred_proba' in output_df.columns:
                    eval_kwargs['y_pred_proba'] = output_df['y_pred_proba'].dropna().values

                # Look for sensitive attributes in metadata labels
                for col in output_df.columns:
                    if col.startswith('label_') and any(sens in col.lower() for sens in ['gender', 'age']):
                        eval_kwargs['sensitive_attr'] = output_df[col].dropna().values
                        break
            print(eval_kwargs)
            if len(eval_kwargs) >= 2:
                result = evaluate_function(metric_name, **eval_kwargs)
                evaluation_result = {"underlying_features": {"all": {"all": result}}}
            else:
                evaluation_result = {"warning": "Insufficient data for evaluation"}
                
        except Exception as e:
            print(f"Evaluation failed: {str(e)}")
            evaluation_result = {"error": str(e)}
    print(output_df)

    # Calculate successful predictions count
    successful_count = len(output_df)
    if 'prediction_success' in output_df.columns:
        successful_count = len(output_df[output_df['prediction_success'] != False])
    elif 'generation_success' in output_df.columns:
        successful_count = len(output_df[output_df['generation_success'] != False])

    result_dict = {
        "success": True,
        "model_id": model_metadata.id,
        "model_name": model_name,
        "model_type": "Generative AI" if model_metadata.model_type else "Predictive AI",
        "total_entries_processed": len(output_df),
        "successful_predictions": successful_count,
        "input_location": input_location,
        "output_location": str(actual_results_path),
        "evaluation_result": evaluation_result,
        "metric_name": metric_name,
        "output_columns": list(output_df.columns),
        "metadata_enhanced": metadata_manager is not None,
        "used_existing_results": False,
        "results_source": "new_inference",
        "sample_metadata": {
            discovered_entries[0]['file_name']: {k: v for k, v in discovered_entries[0].items() if k.startswith('label_')}
        } if metadata_manager and discovered_entries else None
    }

    # If no evaluation was performed (metric_name is None), include the raw predictions
    # This is useful for qualitative metrics that need the model output
    if metric_name is None and not output_df.empty:
        # Replace NaN values with None before converting to dict
        # Use pandas fillna to handle all types of missing values
        predictions_df = output_df.where(pd.notnull(output_df), None)
        result_dict["predictions"] = predictions_df.to_dict('records')
        print(f"Including {len(predictions_df)} prediction records from new inference (no evaluation performed)")

    return result_dict
        
    # except Exception as e:
    #     return {
    #         "success": False,
    #         "error": str(e),
    #         "model_id": getattr(model_metadata, 'id', None),
    #         "model_name": getattr(model_metadata, 'name', 'unknown'),
    #         "output_location": None,
    #         "evaluation_result": None
    #     }
        
def run_output_classification(
    session: Session,
    model_metadata: Modelmetadata,
    input_dataset_metadata: OutputEvaluationData,
    user_id: Optional[str] = None,
    storage_base_path: str = "storage",
    api_key = None,
    *args, **kwargs
) -> Dict[str, Any]:
    """
    Run output-only classification evaluation - gets model output and classifies it.
    For example, for SAM: classifies output as secure/insecure.
    Does NOT compute metrics, just returns the classification of the output.

    Args:
        session: Database session
        model_metadata: Model metadata
        input_dataset_metadata: Input evaluation data with location
        user_id: User ID for API key lookup
        storage_base_path: Base path for storage directory
        api_key: Optional API key for model inference

    Returns:
        Dictionary with classification results
    """
    print(f"\n{'='*80}")
    print(f"🔍 run_output_classification called")
    print(f"{'='*80}\n")

    try:
        storage_manager = StorageManager(storage_base_path)

        # Extract metadata
        model_name = model_metadata.name
        model_location = model_metadata.location

        print(f"=" * 80)
        print(f"MODEL INFO:")
        print(f"  Name: '{model_name}'")
        print(f"  Location: '{model_location}'")
        print(f"=" * 80)

        # Get the directory path (remove filename if it's a file path)
        from pathlib import Path
        location_path = Path(input_dataset_metadata.location)

        if location_path.suffix:  # Has file extension like .wav, .csv, etc.
            input_location = str(location_path.parent)
        else:
            input_location = input_dataset_metadata.location

        # Output location is in the same user storage folder as input
        output_location = input_location.replace('/input', '/output')
        datatypes_info = {}

        # Get API key if needed
        if model_location == "run_inference" and user_id and model_metadata.id:
            raise ValueError("No api key contact the Audit Instigator")

        metadata_manager = InputFileMetadataManager(storage_base_path)
        print("🏷️  Using enhanced metadata discovery...")
        print(f"Input location: {input_location}")
        print(f"Output location: {output_location}")

        # Register metadata.csv if it exists in the input directory
        input_path = Path(input_location)
        metadata_csv_path = input_path / "metadata.csv"
        if metadata_csv_path.exists():
            print(f"📋 Found metadata.csv at: {metadata_csv_path}")
            # Read metadata.csv to determine available columns
            try:
                metadata_df = pd.read_csv(metadata_csv_path)
                available_columns = [col for col in metadata_df.columns if col != 'file_name']
                print(f"📊 Metadata columns available: {available_columns}")
            except Exception as e:
                print(f"Could not read metadata.csv columns: {e}")
                # Fallback to common columns
                available_columns = ['id', 'gender', 'age', 'true_value', 'expected_subjects', 'notes']

            metadata_manager.add_metadata_file(
                str(metadata_csv_path),
                'csv',
                'file_name',  # Column that maps to actual files
                available_columns  # Extract all available metadata columns
            )

        discovered_entries = discover_input_data_with_metadata(
            input_location, datatypes_info, storage_manager, metadata_manager
        )

        if not discovered_entries:
            print(f"❌ No input data found at: {input_location}")
            return {
                "success": False,
                "error": "no_input_data",
                "message": "No input data found. Please upload input files before generating results.",
                "classifications": []
            }

        print(f"Discovered {len(discovered_entries)} files")

        # Check if we can run inference or need to use existing output.csv
        can_run_inference = bool(model_location and model_location.strip())

        # First, check if output.csv already exists
        output_csv_path = Path(output_location) / "output.csv"
        existing_output_df = None

        if output_csv_path.exists():
            print(f"✅ Found existing output.csv at: {output_csv_path}")
            try:
                existing_output_df = pd.read_csv(output_csv_path)
                print(f"📊 Loaded existing output with {len(existing_output_df)} rows")

                # Validate that output contains all input files
                input_file_names = {entry['file_name'] for entry in discovered_entries}
                print(f"📋 Input files: {len(input_file_names)} files")

                # Check if file_name column exists in output
                if 'file_name' in existing_output_df.columns:
                    output_file_names = set(existing_output_df['file_name'].dropna().unique())
                    print(f"📋 Output files: {len(output_file_names)} files")
                    missing_files = input_file_names - output_file_names

                    if missing_files:
                        print(f"Output CSV is missing {len(missing_files)} input files:")
                        for missing_file in list(missing_files)[:5]:  # Show first 5
                            print(f"   - {missing_file}")
                        if len(missing_files) > 5:
                            print(f"   ... and {len(missing_files) - 5} more")
                        print(f"🔄 Will re-run inference to generate complete output")
                        existing_output_df = None  # Force re-run
                    else:
                        print(f"✅ Output CSV contains all {len(input_file_names)} input files")
                else:
                    print(f"Output CSV missing 'file_name' column, will re-run inference")
                    existing_output_df = None

            except Exception as e:
                print(f"Error loading existing output.csv: {e}")
                existing_output_df = None

        # Determine if we need to run inference
        if existing_output_df is not None:
            # Use existing output.csv
            print(f"🔄 Using existing output.csv instead of running inference")
            output_df = existing_output_df

        elif not can_run_inference:
            # No API connection and no output.csv - return error
            print(f"❌ No API connection available and no output.csv found")
            return {
                "success": False,
                "error": "no_inference_available",
                "message": "Classification will be calculated later. No API connection is available and no pre-computed output file was found.",
                "classifications": []
            }

        else:
            # Run inference with API
            print(f"Running inference with model: {model_name} at {model_location}")
            output_rows = []

            # Check if this is SAM model (Secure Attachment Model)
            is_sam_model = "sam" in model_name.lower() or "attachment" in model_name.lower() or "sentiment" in model_name.lower()
            print(f"Model name: {model_name}, is_sam_model: {is_sam_model}")

            api_connection_failed = False

            for idx, file_info in enumerate(discovered_entries):
                print(f"Processing entry {idx + 1}/{len(discovered_entries)} - {file_info['file_name']}")

                try:
                    # Prepare model input
                    print(f"Preparing model input for {file_info['file_name']}")
                    if is_sam_model:
                        model_input = prepare_model_input_sam(file_info, model_metadata)
                    else:
                        model_input = prepare_model_input(file_info, model_metadata)
                    # print(f"Model input prepared: {list(model_input.keys())}")

                    # Run inference
                    print(f"Calling model at {model_location}/predict")
                    raw_output = run_model_inference(model_metadata, model_input, api_key)
                    # print(f"Raw output received: {raw_output}")

                    # Check if API call failed
                    if isinstance(raw_output, dict) and raw_output.get('error') and not raw_output.get('success', True):
                        api_connection_failed = True
                        print(f"API connection failed: {raw_output.get('error')}")
                        break

                    # Transform output
                    if is_sam_model:
                        transformed_output = transform_model_output_sam(raw_output, model_metadata, file_info)
                    else:
                        transformed_output = transform_model_output(raw_output, model_metadata, file_info)
                    # print(f"Transformed output: {transformed_output}")
                    output_rows.append(transformed_output)

                except Exception as e:
                    print(f"Error processing entry {idx + 1}: {e}")
                    # Check if it's a connection error
                    if "Connection" in str(e) or "timeout" in str(e).lower() or "refused" in str(e).lower():
                        api_connection_failed = True
                        print(f"Connection error detected: {e}")
                        break

                    # Add error entry
                    error_output = {
                        'file_path': file_info['file_path'],
                        'file_name': file_info['file_name'],
                        'model_id': model_metadata.id,
                        'model_name': model_metadata.name,
                        'processing_error': str(e),
                        'prediction_success': False
                    }
                    error_output.update(file_info['metadata'])
                    output_rows.append(error_output)

            # If API failed, check for output.csv fallback
            if api_connection_failed:
                print(f"🔍 API connection failed, checking for output.csv fallback...")
                if output_csv_path.exists():
                    print(f"✅ Found output.csv fallback at: {output_csv_path}")
                    try:
                        output_df = pd.read_csv(output_csv_path)
                        print(f"📊 Loaded fallback output with {len(output_df)} rows")
                    except Exception as e:
                        print(f"❌ Error loading output.csv: {e}")
                        return {
                            "success": False,
                            "error": "api_connection_failed",
                            "message": "Classification will be calculated later. API connection failed and output.csv could not be loaded.",
                            "classifications": []
                        }
                else:
                    print(f"❌ No output.csv found as fallback")
                    return {
                        "success": False,
                        "error": "api_connection_failed",
                        "message": "Classification will be calculated later. API connection failed and no output.csv file was found.",
                        "classifications": []
                    }
            else:
                # Create output DataFrame from successful inference
                output_df = pd.DataFrame(output_rows)

        # Save output data
        print(f"Saving output data to: {output_location}")
        actual_output_path = save_output_data(
            output_df,
            output_location,
            storage_manager,
            f"{model_name}_classification"
        )

        # Extract classifications from output
        classifications = []

        # Clean column names
        output_df.columns = output_df.columns.str.strip()

        # Debug: Print available columns
        print(f"📊 Available columns in output_df: {list(output_df.columns)}")
        print(f"📊 First row sample: {output_df.head(1).to_dict('records')}")

        # Detect model type for proper classification extraction
        is_annif = 'annif' in model_name.lower()
        print(f"🔍 Model detection: is_annif={is_annif}, model_name={model_name}")

        for _, row in output_df.iterrows():
            classification_item = {
                'file_name': row.get('file_name', 'unknown'),
                'file_path': row.get('file_path', 'unknown'),
            }

            if is_annif:
                # Annif-specific classification fields
                if 'predicted_subjects' in output_df.columns and pd.notna(row['predicted_subjects']):
                    classification_item['predicted_subjects'] = row['predicted_subjects']

                if 'top_subjects' in output_df.columns and pd.notna(row['top_subjects']):
                    classification_item['top_subjects'] = row['top_subjects']

                if 'subject_count' in output_df.columns and pd.notna(row['subject_count']):
                    classification_item['subject_count'] = int(row['subject_count'])

                if 'project_id' in output_df.columns and pd.notna(row['project_id']):
                    classification_item['project_id'] = row['project_id']

                # Add expected subjects from metadata if available
                if 'expected_subjects' in output_df.columns and pd.notna(row['expected_subjects']):
                    classification_item['expected_subjects'] = row['expected_subjects']

                if 'notes' in output_df.columns and pd.notna(row['notes']):
                    classification_item['notes'] = row['notes']

            else:
                # SAM-specific classification fields (binary classification)
                # Add classification - look for y_pred or prediction column
                if 'y_pred' in output_df.columns:
                    pred = row['y_pred']
                    # Map numeric to text if needed
                    if pd.notna(pred):
                        if isinstance(pred, (int, float)):
                            classification_item['classification'] = 'secure' if int(pred) == 1 else 'insecure'
                            classification_item['classification_numeric'] = int(pred)
                        else:
                            classification_item['classification'] = str(pred).lower()
                elif 'prediction' in output_df.columns:
                    pred = row['prediction']
                    if pd.notna(pred):
                        classification_item['classification'] = str(pred).lower()

                # Add confidence if available
                if 'confidence' in output_df.columns and pd.notna(row['confidence']):
                    classification_item['confidence'] = float(row['confidence'])

                # Add probabilities if available
                if 'secure_probability' in output_df.columns and pd.notna(row['secure_probability']):
                    classification_item['secure_probability'] = float(row['secure_probability'])
                if 'insecure_probability' in output_df.columns and pd.notna(row['insecure_probability']):
                    classification_item['insecure_probability'] = float(row['insecure_probability'])

                # Add metadata columns
                for col in ['gender', 'age', 'true_value']:
                    if col in output_df.columns and pd.notna(row[col]):
                        classification_item[col] = row[col]

            # Add id column (common to both)
            if 'id' in output_df.columns and pd.notna(row['id']):
                classification_item['id'] = row['id']

            # Add true_value if not already added (common to both ANNIF and SAM)
            if 'true_value' not in classification_item and 'true_value' in output_df.columns and pd.notna(row['true_value']):
                classification_item['true_value'] = row['true_value']

            classifications.append(classification_item)

        print(f"Extracted {len(classifications)} classifications")

        # For ANNIF models, generate results.csv and calculate accuracy
        results_csv_path = None
        accuracy_metrics = None
        if is_annif:
            try:
                from src.services.performance_service.keyword_matching import (
                    save_results_csv,
                    calculate_overall_accuracy
                )

                # Prepare results for CSV (id and suggested_keywords)
                results_for_csv = []
                for classification in classifications:
                    results_for_csv.append({
                        'id': classification.get('id', ''),
                        'suggested_keywords': classification.get('predicted_subjects', '')
                    })

                # Save results.csv
                results_csv_path = save_results_csv(output_location, results_for_csv)
                print(f"✅ Saved results.csv to {results_csv_path}")

                # Calculate accuracy if expected_subjects available
                if 'expected_subjects' in output_df.columns:
                    # Prepare metadata list with expected subjects
                    metadata_list = []
                    for _, row in output_df.iterrows():
                        if pd.notna(row.get('expected_subjects')):
                            metadata_list.append({
                                'id': row.get('id', ''),
                                'file_name': row.get('file_name', ''),
                                'expected_subjects': row['expected_subjects']
                            })

                    # Prepare predictions list
                    predictions_list = []
                    for _, row in output_df.iterrows():
                        predictions_list.append({
                            'id': row.get('id', ''),
                            'file_name': row.get('file_name', ''),
                            'predicted_subjects': row.get('predicted_subjects', ''),
                            'extracted_id': row.get('id', '')
                        })

                    # Calculate overall accuracy
                    accuracy_metrics = calculate_overall_accuracy(metadata_list, predictions_list)
                    print(f"📊 Accuracy metrics: {accuracy_metrics}")

            except Exception as e:
                print(f"Error generating results.csv or calculating accuracy: {e}")
                import traceback
                traceback.print_exc()

        response_data = {
            "success": True,
            "model_id": model_metadata.id,
            "model_name": model_name,
            "model_type": "Generative AI" if model_metadata.model_type else "Predictive AI",
            "total_entries_processed": len(output_df),
            "input_location": input_location,
            "output_location": actual_output_path,
            "classifications": classifications,
            "output_columns": list(output_df.columns),
        }

        # Add ANNIF-specific fields to response
        if is_annif and results_csv_path:
            response_data["results_csv_path"] = results_csv_path
        if is_annif and accuracy_metrics:
            response_data["accuracy_metrics"] = accuracy_metrics

        return response_data

    except Exception as e:
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "error": str(e),
            "model_id": getattr(model_metadata, 'id', None),
            "model_name": getattr(model_metadata, 'name', 'unknown'),
            "output_location": None,
            "classifications": []
        }

def run_output_evaluation(
    session: Session,
    model_metadata: Modelmetadata,
    input_dataset_metadata: OutputEvaluationData,
    metric_name: str,
    user_id: Optional[str] = None,
    storage_base_path: str = "storage",
    api_key = None,
    metric_value_id: Optional[int] = None  # NEW: specific MetricsValues.id to evaluate
) -> Dict[str, Any]:
    print(f"\n{'='*80}")
    print(f"🚀 run_output_evaluation called for metric: {metric_name}")
    print(f"{'='*80}\n")
    try:
        storage_manager = StorageManager(storage_base_path)
        
        # Extract metadata
        model_name = model_metadata.name
        model_location = model_metadata.location

        print(f"=" * 80)
        print(f"MODEL INFO:")
        print(f"  Name: '{model_name}'")
        print(f"  Location: '{model_location}'")
        print(f"=" * 80)

        # Get the directory path (remove filename if it's a file path)
        from pathlib import Path
        location_path = Path(input_dataset_metadata.location)
        # Check if location looks like a file path (has an extension)
        print(input_dataset_metadata.location)
        if location_path.suffix:  # Has file extension like .wav, .csv, etc.
            input_location = str(location_path.parent)
        else:
            input_location = input_dataset_metadata.location

        # Output location is in the same user storage folder as input
        output_location = input_location.replace('/input', '/output')
        datatypes_info = {}
        
        # Get API key if needed
        
        if model_location == "run_inference" and user_id and model_metadata.id:
            raise ValueError("No api key contact the Audit Instigator")
        
        metadata_manager = InputFileMetadataManager(storage_base_path)
        print("🏷️  Using enhanced metadata discovery...")
        print(f"Input location: {input_location}")
        print(f"Output location: {output_location}")

        # Register metadata.csv if it exists in the input directory
        from pathlib import Path
        input_path = Path(input_location)
        metadata_csv_path = input_path / "metadata.csv"
        if metadata_csv_path.exists():
            print(f"📋 Found metadata.csv at: {metadata_csv_path}")
            # Read metadata.csv to determine available columns
            try:
                metadata_df = pd.read_csv(metadata_csv_path)
                available_columns = [col for col in metadata_df.columns if col != 'file_name']
                print(f"📊 Metadata columns available: {available_columns}")
            except Exception as e:
                print(f"Could not read metadata.csv columns: {e}")
                # Fallback to common columns
                available_columns = ['id', 'gender', 'age', 'true_value', 'expected_subjects', 'notes']

            metadata_manager.add_metadata_file(
                str(metadata_csv_path),
                'csv',
                'file_name',  # Column that maps to actual files
                available_columns  # Extract all available metadata columns
            )

        discovered_entries = discover_input_data_with_metadata(
            input_location, datatypes_info, storage_manager, metadata_manager
        )

        if not discovered_entries:
            print(f"❌ No input data found at: {input_location}")
            return {
                "success": False,
                "error": "no_input_data",
                "message": "No input data found. Please upload input files before generating results.",
                "model_id": model_metadata.id,
                "model_name": model_metadata.name,
                "output_location": None,
                "evaluation_result": {
                    "error": "No input data available",
                    "status": "pending",
                    "details": f"Please upload input data files to: {input_location}"
                }
            }

        print(f"Discovered {len(discovered_entries)} files")

        # Check if we can run inference or need to use existing output.csv
        can_run_inference = bool(model_location and model_location.strip())

        # First, check if output.csv already exists
        output_csv_path = Path(output_location) / "output.csv"
        existing_output_df = None

        if output_csv_path.exists():
            print(f"✅ Found existing output.csv at: {output_csv_path}")
            try:
                existing_output_df = pd.read_csv(output_csv_path)
                print(f"📊 Loaded existing output with {len(existing_output_df)} rows")

                # Validate that output contains all input files
                input_file_names = {entry['file_name'] for entry in discovered_entries}
                print(f"📋 Input files: {len(input_file_names)} files")

                # Check if file_name column exists in output
                if 'file_name' in existing_output_df.columns:
                    output_file_names = set(existing_output_df['file_name'].dropna().unique())
                    print(f"📋 Output files: {len(output_file_names)} files")
                    missing_files = input_file_names - output_file_names

                    if missing_files:
                        print(f"Output CSV is missing {len(missing_files)} input files:")
                        for missing_file in list(missing_files)[:5]:  # Show first 5
                            print(f"   - {missing_file}")
                        if len(missing_files) > 5:
                            print(f"   ... and {len(missing_files) - 5} more")
                        print(f"🔄 Will re-run inference to generate complete output")
                        existing_output_df = None  # Force re-run
                    else:
                        print(f"✅ Output CSV contains all {len(input_file_names)} input files")
                else:
                    print(f"Output CSV missing 'file_name' column, will re-run inference")
                    existing_output_df = None

            except Exception as e:
                print(f"Error loading existing output.csv: {e}")
                existing_output_df = None

        # Determine if we need to run inference
        if existing_output_df is not None:
            # Use existing output.csv
            print(f"🔄 Using existing output.csv instead of running inference")
            output_df = existing_output_df

        elif not can_run_inference:
            # No API connection and no output.csv - return error
            print(f"❌ No API connection available and no output.csv found")
            return {
                "success": False,
                "error": "no_inference_available",
                "message": "Results will be calculated later. No API connection is available and no pre-computed output file was found.",
                "evaluation_result": {
                    "error": "Results will be calculated later",
                    "status": "pending",
                    "details": "Please ensure the model API is accessible or upload an output.csv file with pre-computed results."
                }
            }

        else:
            # Run inference with API
            print(f"Running inference with model: {model_name} at {model_location}")
            output_rows = []

            # Check if this is SAM model (Secure Attachment Model)
            is_sam_model = "sam" in model_name.lower() or "attachment" in model_name.lower() or "sentiment" in model_name.lower()
            print(f"Model name: {model_name}, is_sam_model: {is_sam_model}")

            api_connection_failed = False

            for idx, file_info in enumerate(discovered_entries):
                print(f"Processing entry {idx + 1}/{len(discovered_entries)} - {file_info['file_name']}")

                try:
                    # Prepare model input
                    print(f"Preparing model input for {file_info['file_name']}")
                    if is_sam_model:
                        model_input = prepare_model_input_sam(file_info, model_metadata)
                    else:
                        model_input = prepare_model_input(file_info, model_metadata)
                    print(f"Model input prepared: {list(model_input.keys())}")

                    # Run inference
                    print(f"Calling model at {model_location}/predict")
                    raw_output = run_model_inference(model_metadata, model_input, api_key)
                    print(f"Raw output received: {raw_output}")

                    # Check if API call failed
                    if isinstance(raw_output, dict) and raw_output.get('error') and not raw_output.get('success', True):
                        api_connection_failed = True
                        print(f"API connection failed: {raw_output.get('error')}")
                        break

                    # Transform output
                    if is_sam_model:
                        transformed_output = transform_model_output_sam(raw_output, model_metadata, file_info)
                    else:
                        transformed_output = transform_model_output(raw_output, model_metadata, file_info)
                    print(f"Transformed output: {transformed_output}")
                    output_rows.append(transformed_output)

                except Exception as e:
                    print(f"Error processing entry {idx + 1}: {e}")
                    # Check if it's a connection error
                    if "Connection" in str(e) or "timeout" in str(e).lower() or "refused" in str(e).lower():
                        api_connection_failed = True
                        print(f"Connection error detected: {e}")
                        break

                    # Add error entry
                    error_output = {
                        'file_path': file_info['file_path'],
                        'file_name': file_info['file_name'],
                        'model_id': model_metadata.id,
                        'model_name': model_metadata.name,
                        'processing_error': str(e),
                        'prediction_success': False
                    }
                    error_output.update(file_info['metadata'])
                    output_rows.append(error_output)

            # If API failed, check for output.csv fallback
            if api_connection_failed:
                print(f"🔍 API connection failed, checking for output.csv fallback...")
                if output_csv_path.exists():
                    print(f"✅ Found output.csv fallback at: {output_csv_path}")
                    try:
                        output_df = pd.read_csv(output_csv_path)
                        print(f"📊 Loaded fallback output with {len(output_df)} rows")
                    except Exception as e:
                        print(f"❌ Error loading output.csv: {e}")
                        return {
                            "success": False,
                            "error": "api_connection_failed",
                            "message": "Results will be calculated later. API connection failed and output.csv could not be loaded.",
                            "evaluation_result": {
                                "error": "Results will be calculated later",
                                "status": "pending",
                                "details": "The model API is not accessible. Please ensure the API is running or upload a valid output.csv file."
                            }
                        }
                else:
                    print(f"❌ No output.csv found as fallback")
                    return {
                        "success": False,
                        "error": "api_connection_failed",
                        "message": "Results will be calculated later. API connection failed and no output.csv file was found.",
                        "evaluation_result": {
                            "error": "Results will be calculated later",
                            "status": "pending",
                            "details": "The model API is not accessible. Please ensure the API is running or upload an output.csv file with pre-computed results."
                        }
                    }
            else:
                # Create output DataFrame from successful inference
                output_df = pd.DataFrame(output_rows)

        # Save output data
        print(f"Saving output data to: {output_location}")
        actual_output_path = save_output_data(
            output_df, 
            output_location, 
            storage_manager,
            f"{model_name}_evaluation"
        )
        
        # Run evaluation if we have required columns
        evaluation_result = None
        if metric_name:
            try:
                print(f"Running evaluation with metric function: {metric_name}")
                print(f"Specific MetricsValues ID: {metric_value_id}")

                # If metric_value_id is provided, only evaluate underlying features for that specific record
                if metric_value_id:
                    # Get underlying features for the specific MetricsValues record
                    metric_values = session.exec(
                        select(MetricsValues, MetricsUnderlyingFeatures, UnderlyingFeatures)
                        .join(MetricsUnderlyingFeatures, MetricsValues.id == MetricsUnderlyingFeatures.metric_values_id)
                        .join(UnderlyingFeatures, MetricsUnderlyingFeatures.feature_id == UnderlyingFeatures.id)
                        .where(MetricsValues.id == metric_value_id)
                    ).all()

                    print(f"Found {len(metric_values)} underlying features for MetricsValues.id={metric_value_id}")
                else:
                    # Fallback: Find metric by matching target feature function_name
                    metric_with_target = session.exec(
                        select(Metrics, TargetFeatures)
                        .join(MetricsTargetFeatures, Metrics.id == MetricsTargetFeatures.metric_values_id)
                        .join(TargetFeatures, MetricsTargetFeatures.target_feature_id == TargetFeatures.id)
                        .where(TargetFeatures.function_name == metric_name)
                    ).first()

                    metric = None
                    if metric_with_target:
                        metric, target_feature = metric_with_target
                        print(f"Found metric via target feature:")
                        print(f"  - Metric: {metric.name} (ID: {metric.id})")
                        print(f"  - Target Feature: {target_feature.target_feature} (Function: {target_feature.function_name})")

                    if metric:
                        # Get metric values with underlying features
                        metric_values = session.exec(
                            select(MetricsValues, MetricsUnderlyingFeatures, UnderlyingFeatures)
                            .join(MetricsUnderlyingFeatures, MetricsValues.id == MetricsUnderlyingFeatures.metric_values_id)
                            .join(UnderlyingFeatures, MetricsUnderlyingFeatures.feature_id == UnderlyingFeatures.id)
                            .join(MetricsTargetFeatures, MetricsValues.id == MetricsTargetFeatures.metric_values_id)
                            .join(TargetFeatures, MetricsTargetFeatures.target_feature_id == TargetFeatures.id)
                            .where(TargetFeatures.function_name == metric_name)
                        ).all()
                    else:
                        print(f"No metric found with target feature function_name = '{metric_name}'")
                        metric_values = []

                if metric_values:
                    print(f"\n{'='*80}")
                    print(f"UNDERLYING FEATURES QUERY RESULTS:")
                    print(f"Total rows returned: {len(metric_values)}")
                    for idx, (mv, fm, feat) in enumerate(metric_values):
                        print(f"\nRow {idx + 1}:")
                        print(f"  - MetricsValues.id: {mv.id}")
                        print(f"  - UnderlyingFeatures.id: {feat.id}")
                        print(f"  - UnderlyingFeatures.feature_name: '{feat.feature_name}'")
                        print(f"  - MetricsUnderlyingFeatures.ranges: {fm.ranges}")
                    print(f"\nDataFrame columns available: {list(output_df.columns)}")
                    print(f"{'='*80}\n")

                    # First, collect all features and their configurations
                    features_config = []
                    for _, feature_mapping, feature in metric_values:
                        feature_name = feature.feature_name
                        ranges = feature_mapping.ranges or []
                        if not isinstance(ranges, list):
                            ranges = []

                        range_groups, expanded_ranges = parse_range_groups(ranges)
                        features_config.append({
                            'feature_name': feature_name,
                            'ranges': ranges,
                            'range_groups': range_groups,
                            'expanded_ranges': expanded_ranges
                        })

                    print(f"Features configuration: {features_config}")

                    # Determine if we should do cross-tabulation (multiple features with ranges)
                    features_with_ranges = [f for f in features_config if len(f['ranges']) > 0]
                    use_cross_tabulation = len(features_with_ranges) > 1
                    print(f"Cross-tabulation mode: {use_cross_tabulation} ({len(features_with_ranges)} features with ranges)")

                    # Structure results by underlying features
                    underlying_features_results = {}

                    # If cross-tabulation is needed, use specialized function
                    if use_cross_tabulation:
                        print("Using cross-tabulation for multiple features")

                        # Detect column names for keyword accuracy
                        expected_col = None
                        predicted_col = None
                        if metric_name in ['keyword_accuracy', 'batch_keyword_accuracy']:
                            for col in output_df.columns:
                                if col == 'expected_subjects' or col.startswith('expected_subjects_'):
                                    expected_col = col
                                if col == 'predicted_subjects' or col.startswith('predicted_subjects_'):
                                    predicted_col = col

                        # Prepare base eval_kwargs
                        eval_kwargs_base = {}
                        if metric_name in ['keyword_accuracy', 'batch_keyword_accuracy']:
                            if expected_col and predicted_col:
                                eval_kwargs_base['y_true'] = output_df[expected_col].fillna('').values
                                eval_kwargs_base['y_pred'] = output_df[predicted_col].fillna('').values
                        else:
                            if 'y_pred' in output_df.columns:
                                eval_kwargs_base['y_pred'] = output_df['y_pred'].dropna().values
                            if 'y_true' in output_df.columns:
                                eval_kwargs_base['y_true'] = output_df['y_true'].dropna().values
                            if 'y_pred_proba' in output_df.columns:
                                eval_kwargs_base['y_pred_proba'] = output_df['y_pred_proba'].dropna().values

                        # Create cross-tabulated results
                        cross_tab_results = create_cross_tabulation_results(
                            output_df=output_df,
                            features_config=features_with_ranges,
                            metric_name=metric_name,
                            eval_kwargs_base=eval_kwargs_base,
                            expected_col=expected_col,
                            predicted_col=predicted_col
                        )

                        # Store cross-tab results directly (not nested by feature name)
                        underlying_features_results = cross_tab_results

                    # Otherwise, process each feature independently (original behavior)
                    else:
                        for _, feature_mapping, feature in metric_values:
                            feature_name = feature.feature_name
                            ranges = feature_mapping.ranges or []

                        # Ensure ranges is a list
                        if not isinstance(ranges, list):
                            ranges = []

                        if feature_name not in underlying_features_results:
                            underlying_features_results[feature_name] = {}

                        # Parse ranges to handle grouped values (e.g., "P1-P2" -> ["P1", "P2"])
                        range_groups, expanded_ranges = parse_range_groups(ranges)
                        print(f"  Range groups: {range_groups}")
                        print(f"  Expanded ranges: {expanded_ranges}")

                        # Calculate metric with the underlying feature as sensitive attribute
                        eval_kwargs = {}

                        # Detect column names for keyword accuracy (needed for both initial setup and filtering)
                        expected_col = None
                        predicted_col = None
                        if metric_name in ['keyword_accuracy', 'batch_keyword_accuracy']:
                            for col in output_df.columns:
                                if col == 'expected_subjects' or col.startswith('expected_subjects_'):
                                    expected_col = col
                                if col == 'predicted_subjects' or col.startswith('predicted_subjects_'):
                                    predicted_col = col

                        # Special handling for keyword accuracy (ANNIF models)
                        if metric_name in ['keyword_accuracy', 'batch_keyword_accuracy']:
                            if expected_col and predicted_col:
                                eval_kwargs['y_true'] = output_df[expected_col].fillna('').values
                                eval_kwargs['y_pred'] = output_df[predicted_col].fillna('').values
                        else:
                            # Standard metrics use y_pred and y_true
                            if 'y_pred' in output_df.columns:
                                eval_kwargs['y_pred'] = output_df['y_pred'].dropna().values
                            if 'y_true' in output_df.columns:
                                eval_kwargs['y_true'] = output_df['y_true'].dropna().values
                            if 'y_pred_proba' in output_df.columns:
                                eval_kwargs['y_pred_proba'] = output_df['y_pred_proba'].dropna().values

                        # Add the underlying feature as sensitive attribute
                        # Try exact match first, then case-insensitive match
                        sensitive_col = None
                        if feature_name in output_df.columns:
                            sensitive_col = feature_name
                        else:
                            # Try case-insensitive match
                            for col in output_df.columns:
                                if col.lower() == feature_name.lower():
                                    sensitive_col = col
                                    break

                        if sensitive_col:
                            # Filter data to only include rows where the sensitive attribute matches defined ranges (if any)
                            if ranges:
                                # Create mask for rows that match any of the EXPANDED individual values
                                mask = pd.Series([False] * len(output_df), index=output_df.index)
                                for individual_val in expanded_ranges:
                                    individual_val_str = str(individual_val).lower()
                                    col_mask = output_df[sensitive_col].astype(str).str.lower() == individual_val_str
                                    mask = mask | col_mask

                                # Apply mask to get only data within defined ranges
                                filtered_df = output_df[mask]
                                print(f"  Filtered to {len(filtered_df)} rows (from {len(output_df)}) matching expanded ranges: {expanded_ranges}")

                                # Check if filtered data is empty - means ranges don't match output data
                                if len(filtered_df) == 0:
                                    print(f"  WARNING: No data found matching defined ranges {expanded_ranges}")
                                    print(f"  Available values in output: {output_df[sensitive_col].unique().tolist()}")
                                    print(f"  Skipping evaluation for {feature_name} - ranges need to be updated to match output data")
                                    underlying_features_results[feature_name] = {
                                        'status': 'no_matching_data',
                                        'error': f'No data found matching defined ranges: {ranges}',
                                        'defined_ranges': ranges,
                                        'expanded_ranges': expanded_ranges,
                                        'available_values': output_df[sensitive_col].unique().tolist(),
                                        'message': 'Please update the ranges to match the available values in the output data, or leave ranges empty to evaluate all values.'
                                    }
                                      # Skip to next feature
                            else:
                                # No ranges defined, use all data
                                filtered_df = output_df
                                print(f"  No ranges defined, using all {len(filtered_df)} rows")

                            # Get non-null values from filtered data
                            valid_indices = filtered_df[sensitive_col].notna()
                            eval_kwargs['sensitive_attr'] = filtered_df.loc[valid_indices, sensitive_col].values

                            # Also filter other columns to match indices
                            # For keyword_accuracy, preserve the expected_subjects/predicted_subjects columns
                            if metric_name in ['keyword_accuracy', 'batch_keyword_accuracy']:
                                if expected_col and expected_col in filtered_df.columns:
                                    eval_kwargs['y_true'] = filtered_df.loc[valid_indices, expected_col].fillna('').values
                                if predicted_col and predicted_col in filtered_df.columns:
                                    eval_kwargs['y_pred'] = filtered_df.loc[valid_indices, predicted_col].fillna('').values
                            else:
                                # Standard metrics
                                if 'y_pred' in filtered_df.columns:
                                    eval_kwargs['y_pred'] = filtered_df.loc[valid_indices, 'y_pred'].dropna().values
                                if 'y_true' in filtered_df.columns:
                                    eval_kwargs['y_true'] = filtered_df.loc[valid_indices, 'y_true'].dropna().values
                                if 'y_pred_proba' in filtered_df.columns:
                                    eval_kwargs['y_pred_proba'] = filtered_df.loc[valid_indices, 'y_pred_proba'].dropna().values
                        else:
                            print(f"Warning: Feature '{feature_name}' not found in dataframe columns: {list(output_df.columns)}")

                        if len(eval_kwargs) >= 2 and 'sensitive_attr' in eval_kwargs:
                            try:
                                print(f"Evaluating {metric_name} for {feature_name} with {len(eval_kwargs['sensitive_attr'])} samples")
                                print(f"  Original ranges: {ranges}")
                                print(f"  Expanded ranges: {expanded_ranges}")

                                # Check unique values in the sensitive attribute
                                unique_values = set(eval_kwargs['sensitive_attr'])
                                print(f"  Unique values in data: {unique_values}")

                                # Check for mismatches between defined ranges and actual data
                                if ranges:
                                    expanded_ranges_lower = [str(r).lower() for r in expanded_ranges]
                                    unique_values_lower = [str(v).lower() for v in unique_values]

                                    # Check for unexpected values in data (not in defined ranges)
                                    unexpected_values = [v for v in unique_values if str(v).lower() not in expanded_ranges_lower]
                                    if unexpected_values:
                                        print(f"  WARNING: Data contains values not in defined ranges: {unexpected_values}")

                                    # Check for missing values (defined ranges not found in data)
                                    missing_values = [r for r in expanded_ranges if str(r).lower() not in unique_values_lower]
                                    if missing_values:
                                        print(f"  WARNING: Some defined ranges not found in data: {missing_values}")
                                        print(f"  Note: Results will only include data for values that exist: {list(unique_values)}")

                                result = evaluate_function(metric_name, **eval_kwargs)

                                # Check if metric calculation failed
                                if isinstance(result, dict) and result.get("status") == "cannot be calculated":
                                    underlying_features_results[feature_name] = result
                                # The detailed metrics return results grouped by feature values
                                # Some metrics return {'groups': {...}}, others return direct dict of groups
                                elif isinstance(result, dict):
                                    # Determine if this is a grouped result
                                    if 'groups' in result:
                                        all_groups = result['groups']
                                    else:
                                        # Check if result is a dict of group results (each value is a dict with metrics)
                                        # by checking if keys match sensitive_attr values and values are dicts
                                        unique_values_str = set(str(v) for v in eval_kwargs.get('sensitive_attr', []))
                                        result_keys_str = set(str(k) for k in result.keys())

                                        # If result keys overlap with sensitive attr values, it's grouped results
                                        if result_keys_str & unique_values_str:
                                            all_groups = result
                                        else:
                                            # Single result, not grouped
                                            underlying_features_results[feature_name] = {'overall': result}
                                            all_groups = None

                                    # Process ranges: combine groups if needed based on range_groups
                                    if all_groups is not None:
                                        if ranges:
                                            processed_groups = {}

                                            for original_range, individual_values in range_groups.items():
                                                if len(individual_values) > 1:
                                                    # This is a grouped range (e.g., "P1-P2" or "P2-P4")
                                                    # Combine results from all individual values using confusion matrix combination
                                                    combined_result = combine_classification_results(all_groups, individual_values)
                                                    if combined_result is not None:
                                                        processed_groups[original_range] = combined_result
                                                    else:
                                                        # Fallback to simple combination
                                                        combined_result = combine_group_results(all_groups, individual_values)
                                                        if combined_result is not None:
                                                            processed_groups[original_range] = combined_result
                                                else:
                                                    # Single value range - keep as is
                                                    for group_key, group_result in all_groups.items():
                                                        if str(group_key).lower() == str(original_range).lower():
                                                            processed_groups[original_range] = group_result
                                                            break

                                            underlying_features_results[feature_name] = processed_groups
                                        else:
                                            # No ranges defined, use all groups
                                            underlying_features_results[feature_name] = all_groups
                                else:
                                    # Non-dict result
                                    underlying_features_results[feature_name] = {'overall': result}
                            except Exception as e:
                                error_msg = f"Error evaluating {metric_name} for {feature_name}: {str(e)}"
                                print(error_msg)
                                import traceback
                                traceback.print_exc()

                                # Include more details in the error
                                underlying_features_results[feature_name] = {
                                    'error': str(e),
                                    'error_type': type(e).__name__,
                                    'feature_name': feature_name,
                                    'defined_ranges': ranges if ranges else [],
                                    'data_sample_count': len(eval_kwargs.get('sensitive_attr', [])),
                                    'unique_values_in_data': list(set(eval_kwargs.get('sensitive_attr', []))) if 'sensitive_attr' in eval_kwargs else []
                                }
                        else:
                            print(f"Insufficient data for {feature_name}: eval_kwargs keys = {list(eval_kwargs.keys())}")

                    # Convert numpy types to JSON serializable types (including dict keys)
                    import numpy as np
                    def convert_numpy(obj):
                        if isinstance(obj, np.ndarray):
                            return obj.tolist()
                        elif isinstance(obj, dict):
                            # Convert both keys and values
                            converted_dict = {}
                            for k, v in obj.items():
                                # Convert numpy keys to native Python types
                                if isinstance(k, (np.int64, np.int32, np.int16, np.int8)):
                                    new_key = int(k)
                                elif isinstance(k, (np.float64, np.float32, np.float16)):
                                    new_key = float(k)
                                elif isinstance(k, np.str_):
                                    new_key = str(k)
                                else:
                                    new_key = k
                                converted_dict[new_key] = convert_numpy(v)
                            return converted_dict
                        elif isinstance(obj, list):
                            return [convert_numpy(item) for item in obj]
                        elif isinstance(obj, (np.int64, np.int32, np.int16, np.int8)):
                            return int(obj)
                        elif isinstance(obj, (np.float64, np.float32, np.float16)):
                            return float(obj)
                        elif isinstance(obj, np.str_):
                            return str(obj)
                        else:
                            return obj

                    evaluation_result = {"underlying_features": convert_numpy(underlying_features_results)}
                    print(f"Evaluation completed with underlying features structure: {evaluation_result}")
                else:
                    # Fallback if metric not found in database
                    eval_kwargs = {}

                    # Special handling for keyword accuracy (ANNIF models)
                    if metric_name in ['keyword_accuracy', 'batch_keyword_accuracy']:
                        # Handle column names with potential _x, _y suffixes from joins
                        expected_col = None
                        predicted_col = None

                        for col in output_df.columns:
                            if col == 'expected_subjects' or col.startswith('expected_subjects_'):
                                expected_col = col
                            if col == 'predicted_subjects' or col.startswith('predicted_subjects_'):
                                predicted_col = col

                        if expected_col and predicted_col:
                            eval_kwargs['y_true'] = output_df[expected_col].fillna('').values
                            eval_kwargs['y_pred'] = output_df[predicted_col].fillna('').values
                        elif expected_col and not predicted_col:
                            # Have expected_subjects but no predicted_subjects - need to run output classification first
                            evaluation_result = {
                                "error": "Missing predicted_subjects column",
                                "message": "Please run output classification first (/results/{audit_id}/generate/output) to generate predictions before evaluating.",
                                "available_columns": list(output_df.columns),
                                "found_expected": expected_col,
                                "missing": "predicted_subjects"
                            }
                            print(f"❌ Cannot evaluate keyword_accuracy: found {expected_col} but missing predicted_subjects column")
                            print(f"   Run output classification endpoint first to generate ANNIF predictions")
                            return evaluation_result
                    else:
                        # Standard metrics
                        if 'y_pred' in output_df.columns:
                            eval_kwargs['y_pred'] = output_df['y_pred'].dropna().values
                        if 'y_true' in output_df.columns:
                            eval_kwargs['y_true'] = output_df['y_true'].dropna().values

                    print(f"🔍 eval_kwargs keys: {list(eval_kwargs.keys())}, len={len(eval_kwargs)}")
                    if 'y_true' in eval_kwargs:
                        print(f"   y_true samples: {len(eval_kwargs['y_true'])}")
                    if 'y_pred' in eval_kwargs:
                        print(f"   y_pred samples: {len(eval_kwargs['y_pred'])}")

                    if len(eval_kwargs) >= 2:
                        print(f"✅ Running evaluation with {metric_name}")
                        result = evaluate_function(metric_name, **eval_kwargs)
                        evaluation_result = {"underlying_features": {"all": {"all": result}}}
                    else:
                        print(f"❌ Insufficient data - need at least 2 kwargs, got {len(eval_kwargs)}")
                        evaluation_result = {"warning": "Insufficient data for evaluation", "available_columns": list(output_df.columns)}

            except Exception as e:
                print(f"Evaluation failed: {str(e)}")
                evaluation_result = {"error": str(e)}
        print(evaluation_result)
        return {
            "success": True,
            "model_id": model_metadata.id,
            "model_name": model_name,
            "model_type": "Generative AI" if model_metadata.model_type else "Predictive AI",
            "total_entries_processed": len(output_df),
            # "successful_predictions": len(output_df[output_df.get('prediction_success', True) != False]),
            "input_location": input_location,
            "output_location": actual_output_path,
            "evaluation_result": evaluation_result,
            "metric_name": metric_name,
            "output_columns": list(output_df.columns),
            "metadata_enhanced": metadata_manager is not None,
            "sample_metadata": {
                discovered_entries[0]['file_name']: {k: v for k, v in discovered_entries[0].items() if k.startswith('label_')}
            } if metadata_manager and discovered_entries else None
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "model_id": getattr(model_metadata, 'id', None),
            "model_name": getattr(model_metadata, 'name', 'unknown'),
            "output_location": None,
            "evaluation_result": None
        }