"""
Probability calibration metrics.
"""

import numpy as np


def expected_calibration_error_metric(y_true, y_pred_proba, n_bins=10, **kwargs):
    """
    Calculate Expected Calibration Error (ECE).
    Measures how well predicted probabilities match actual frequencies.

    Args:
        y_true: True binary labels
        y_pred_proba: Predicted probabilities
        n_bins: Number of bins for calibration
        **kwargs: Additional arguments

    Returns:
        float: ECE value
    """
    y_true = np.array(y_true)
    y_pred_proba = np.array(y_pred_proba)

    # Create bins
    bin_boundaries = np.linspace(0, 1, n_bins + 1)
    bin_lowers = bin_boundaries[:-1]
    bin_uppers = bin_boundaries[1:]

    ece = 0.0
    for bin_lower, bin_upper in zip(bin_lowers, bin_uppers):
        # Find predictions in this bin
        in_bin = np.logical_and(y_pred_proba > bin_lower, y_pred_proba <= bin_upper)
        prop_in_bin = np.mean(in_bin)

        if prop_in_bin > 0:
            accuracy_in_bin = np.mean(y_true[in_bin])
            avg_confidence_in_bin = np.mean(y_pred_proba[in_bin])
            ece += np.abs(avg_confidence_in_bin - accuracy_in_bin) * prop_in_bin

    return ece
