import numpy as np
from typing import Any, Dict, Union, Optional
import pandas as pd
from sklearn.metrics import accuracy_score
try:
    from fairlearn.metrics import demographic_parity_difference, equalized_odds_difference
    FAIRLEARN_AVAILABLE = True
except ImportError:
    FAIRLEARN_AVAILABLE = False

def demographic_parity_metric(y_pred, sensitive_attr, y_true=None, **kwargs):
    """
    Calculate demographic parity difference.
    Only requires predictions and sensitive attributes.
    
    Args:
        y_pred: Predicted labels (required)
        sensitive_attr: Sensitive attribute values (required)
        y_true: True labels (optional, not used for demographic parity)
        **kwargs: Additional arguments
    
    Returns:
        float: Demographic parity difference (0 = perfect parity)
    """
    if sensitive_attr is None:
        raise ValueError("sensitive_attr is required for demographic parity")
    
    # Convert to pandas for easier grouping
    df = pd.DataFrame({
        'y_pred': y_pred,
        'sensitive': sensitive_attr
    })
    
    # Calculate positive prediction rate for each group
    group_rates = df.groupby('sensitive')['y_pred'].mean()
    
    # Return max difference between groups
    return group_rates.max() - group_rates.min()

def demographic_parity_detailed(y_pred, sensitive_attr, y_true=None, **kwargs):
    """
    Detailed demographic parity analysis showing rates for each group.

    Args:
        y_pred: Predicted labels (required)
        sensitive_attr: Sensitive attribute values (required)
        y_true: True labels (optional, adds accuracy metrics if provided)
        **kwargs: Additional arguments

    Returns:
        dict: Contains group rates and parity metrics
    """
    if sensitive_attr is None:
        raise ValueError("sensitive_attr is required for demographic parity")

    # Create DataFrame with predictions and sensitive attributes
    df_data = {
        'y_pred': y_pred,
        'sensitive': sensitive_attr
    }

    # Add y_true if provided
    if y_true is not None:
        df_data['y_true'] = y_true

    df = pd.DataFrame(df_data)
    
    # Calculate metrics for each group
    group_stats = {}
    group_rates = df.groupby('sensitive')['y_pred'].agg(['mean', 'count']).reset_index()

    for _, row in group_rates.iterrows():
        group = row['sensitive']
        group_data = df[df['sensitive'] == group]

        group_stats[group] = {
            'positive_rate': row['mean'],
            'sample_size': row['count'],
            'positive_predictions': int(row['mean'] * row['count']),
            'negative_predictions': int((1 - row['mean']) * row['count'])
        }

        # Add accuracy if y_true is available
        if y_true is not None and 'y_true' in df.columns:
            group_y_true = group_data['y_true']
            group_y_pred = group_data['y_pred']
            # Only calculate accuracy if we have valid data
            valid_mask = (~pd.isna(group_y_true)) & (~pd.isna(group_y_pred))
            if valid_mask.sum() > 0:
                group_stats[group]['accuracy'] = accuracy_score(
                    group_y_true[valid_mask],
                    group_y_pred[valid_mask]
                )
    
    # Overall parity metrics
    rates = [stats['positive_rate'] for stats in group_stats.values()]

    result = {
        'group_statistics': group_stats,
        'parity_difference': max(rates) - min(rates),
        'parity_ratio': max(rates) / min(rates) if min(rates) > 0 else float('inf'),
        'overall_positive_rate': df['y_pred'].mean()
    }

    # Add overall accuracy if y_true is available
    if y_true is not None and 'y_true' in df.columns:
        valid_mask = (~pd.isna(df['y_true'])) & (~pd.isna(df['y_pred']))
        if valid_mask.sum() > 0:
            result['overall_accuracy'] = accuracy_score(
                df['y_true'][valid_mask],
                df['y_pred'][valid_mask]
            )

    # Add Fairlearn metrics if available
    if FAIRLEARN_AVAILABLE and y_true is not None and 'y_true' in df.columns:
        try:
            result['fairlearn_demographic_parity_difference'] = demographic_parity_difference(
                df['y_true'], df['y_pred'], sensitive_features=df['sensitive']
            )
            result['fairlearn_equalized_odds_difference'] = equalized_odds_difference(
                df['y_true'], df['y_pred'], sensitive_features=df['sensitive']
            )
        except Exception as e:
            result['fairlearn_error'] = str(e)

    return result

def statistical_parity_metric(y_pred, sensitive_attr, y_true=None, **kwargs):
    """
    Calculate statistical parity (same as demographic parity).
    Alias for demographic_parity_metric for completeness.
    """
    return demographic_parity_metric(y_pred, sensitive_attr, y_true, **kwargs)

def statistical_parity_detailed(y_pred, sensitive_attr, y_true=None, **kwargs):
    """
    Detailed statistical parity analysis (same as demographic parity detailed).
    Alias for demographic_parity_detailed for completeness.
    """
    return demographic_parity_detailed(y_pred, sensitive_attr, y_true, **kwargs)

def disparate_impact_ratio(y_pred, sensitive_attr, y_true=None, protected_group=None, **kwargs):
    """
    Calculate disparate impact ratio.
    Ratio of positive prediction rates between protected and privileged groups.
    
    Args:
        y_pred: Predicted labels (required)
        sensitive_attr: Sensitive attribute values (required)
        y_true: True labels (optional, not used)
        protected_group: Which group to consider as protected (optional)
        **kwargs: Additional arguments
    
    Returns:
        float: Disparate impact ratio (1.0 = no disparity, <0.8 or >1.25 often considered problematic)
    """
    if sensitive_attr is None:
        raise ValueError("sensitive_attr is required for disparate impact")
    
    df = pd.DataFrame({
        'y_pred': y_pred,
        'sensitive': sensitive_attr
    })
    
    group_rates = df.groupby('sensitive')['y_pred'].mean()
    
    if protected_group is not None:
        if protected_group not in group_rates.index:
            raise ValueError(f"Protected group '{protected_group}' not found in sensitive_attr")
        
        protected_rate = group_rates[protected_group]
        other_rates = group_rates[group_rates.index != protected_group]
        privileged_rate = other_rates.max()  # Assume highest rate group is privileged
        
        return protected_rate / privileged_rate if privileged_rate > 0 else 0
    
    # If no protected group specified, return min/max ratio
    return group_rates.min() / group_rates.max() if group_rates.max() > 0 else 0

def calibration_metric(y_pred_proba, y_true, sensitive_attr, n_bins=10, **kwargs):
    """
    Calculate calibration difference across groups.
    Measures if predicted probabilities match actual outcomes across groups.
    
    Args:
        y_pred_proba: Predicted probabilities (required)
        y_true: True labels (required for calibration)
        sensitive_attr: Sensitive attribute values (required)
        n_bins: Number of probability bins for calibration analysis
        **kwargs: Additional arguments
    
    Returns:
        dict: Calibration metrics for each group
    """
    if sensitive_attr is None:
        raise ValueError("sensitive_attr is required for calibration")
    if y_true is None:
        raise ValueError("y_true is required for calibration metric")
    
    df = pd.DataFrame({
        'y_true': y_true,
        'y_pred_proba': y_pred_proba,
        'sensitive': sensitive_attr
    })
    
    group_calibration = {}
    
    for group in df['sensitive'].unique():
        group_data = df[df['sensitive'] == group]
        
        # Create probability bins
        group_data['prob_bin'] = pd.cut(group_data['y_pred_proba'], bins=n_bins, labels=False)
        
        bin_stats = []
        for bin_idx in range(n_bins):
            bin_data = group_data[group_data['prob_bin'] == bin_idx]
            if len(bin_data) > 0:
                mean_pred_prob = bin_data['y_pred_proba'].mean()
                actual_prob = bin_data['y_true'].mean()
                bin_stats.append({
                    'bin': bin_idx,
                    'mean_predicted_prob': mean_pred_prob,
                    'actual_positive_rate': actual_prob,
                    'calibration_error': abs(mean_pred_prob - actual_prob),
                    'sample_size': len(bin_data)
                })
        
        # Calculate overall calibration error for this group
        if bin_stats:
            weighted_error = sum(stat['calibration_error'] * stat['sample_size'] for stat in bin_stats)
            total_samples = sum(stat['sample_size'] for stat in bin_stats)
            avg_calibration_error = weighted_error / total_samples if total_samples > 0 else 0
        else:
            avg_calibration_error = 0
        
        group_calibration[group] = {
            'bin_statistics': bin_stats,
            'average_calibration_error': avg_calibration_error
        }
    
    return group_calibration