"""
Regression metrics using sklearn.
"""

import numpy as np
from sklearn.metrics import (
    mean_squared_error,
    root_mean_squared_error,
    mean_absolute_error,
    mean_absolute_percentage_error,
    r2_score,
    explained_variance_score,
    max_error,
    median_absolute_error
)


def mse_metric(y_true, y_pred, **kwargs):
    """
    Calculate Mean Squared Error.

    Args:
        y_true: True values
        y_pred: Predicted values
        **kwargs: Additional sklearn arguments

    Returns:
        float: MSE value
    """
    return mean_squared_error(y_true, y_pred, **kwargs)


def rmse_metric(y_true, y_pred, **kwargs):
    """
    Calculate Root Mean Squared Error.

    Args:
        y_true: True values
        y_pred: Predicted values
        **kwargs: Additional sklearn arguments

    Returns:
        float: RMSE value
    """
    return root_mean_squared_error(y_true, y_pred, **kwargs)


def mae_metric(y_true, y_pred, **kwargs):
    """
    Calculate Mean Absolute Error.

    Args:
        y_true: True values
        y_pred: Predicted values
        **kwargs: Additional sklearn arguments

    Returns:
        float: MAE value
    """
    return mean_absolute_error(y_true, y_pred, **kwargs)


def mape_metric(y_true, y_pred, **kwargs):
    """
    Calculate Mean Absolute Percentage Error.

    Args:
        y_true: True values
        y_pred: Predicted values
        **kwargs: Additional sklearn arguments

    Returns:
        float: MAPE value (as percentage)
    """
    return mean_absolute_percentage_error(y_true, y_pred, **kwargs) * 100


def r2_metric(y_true, y_pred, **kwargs):
    """
    Calculate R² (coefficient of determination) score.

    Args:
        y_true: True values
        y_pred: Predicted values
        **kwargs: Additional sklearn arguments

    Returns:
        float: R² score
    """
    return r2_score(y_true, y_pred, **kwargs)


def explained_variance_metric(y_true, y_pred, **kwargs):
    """
    Calculate explained variance score.

    Args:
        y_true: True values
        y_pred: Predicted values
        **kwargs: Additional sklearn arguments

    Returns:
        float: Explained variance score
    """
    return explained_variance_score(y_true, y_pred, **kwargs)


def max_error_metric(y_true, y_pred, **kwargs):
    """
    Calculate maximum residual error.

    Args:
        y_true: True values
        y_pred: Predicted values
        **kwargs: Additional sklearn arguments

    Returns:
        float: Maximum error
    """
    return max_error(y_true, y_pred, **kwargs)


def median_absolute_error_metric(y_true, y_pred, **kwargs):
    """
    Calculate median absolute error.
    More robust to outliers than MAE.

    Args:
        y_true: True values
        y_pred: Predicted values
        **kwargs: Additional sklearn arguments

    Returns:
        float: Median absolute error
    """
    return median_absolute_error(y_true, y_pred, **kwargs)


def regression_summary_metric(y_true, y_pred, **kwargs):
    """
    Calculate comprehensive regression performance summary.

    Args:
        y_true: True values
        y_pred: Predicted values
        **kwargs: Additional arguments

    Returns:
        dict: Dictionary of multiple regression metric scores
    """
    return {
        'mse': mse_metric(y_true, y_pred),
        'rmse': rmse_metric(y_true, y_pred),
        'mae': mae_metric(y_true, y_pred),
        'r2': r2_metric(y_true, y_pred),
        'explained_variance': explained_variance_metric(y_true, y_pred),
        'max_error': max_error_metric(y_true, y_pred),
        'median_absolute_error': median_absolute_error_metric(y_true, y_pred)
    }
