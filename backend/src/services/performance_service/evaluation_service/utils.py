"""Utility functions for evaluation service"""
import math
import numpy as np
import pandas as pd


def convert_numpy_to_json_serializable(obj):
    """
    Convert numpy arrays and other non-serializable objects to JSON-serializable format.

    This function recursively converts numpy/pandas objects to native Python types
    that can be serialized to JSON, handling special cases like NaN, infinity, and
    various numpy data types.

    Args:
        obj: Any object that needs to be converted to JSON-serializable format

    Returns:
        JSON-serializable version of the input object
    """
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, dict):
        # Convert dict with proper key handling
        result = {}
        for key, value in obj.items():
            # Convert numpy keys to native Python types
            if isinstance(key, (np.int64, np.int32, np.int16, np.int8)):
                key = int(key)
            elif isinstance(key, (np.float64, np.float32, np.float16)):
                key = float(key)
            elif isinstance(key, np.str_):
                key = str(key)
            elif key is None:
                key = "null"  # JSON doesn't support None as dict key
            result[key] = convert_numpy_to_json_serializable(value)
        return result
    elif isinstance(obj, list):
        return [convert_numpy_to_json_serializable(item) for item in obj]
    elif isinstance(obj, tuple):
        return [convert_numpy_to_json_serializable(item) for item in obj]
    elif isinstance(obj, (np.int64, np.int32, np.int16, np.int8)):
        return int(obj)
    elif isinstance(obj, (np.float64, np.float32, np.float16)):
        # Check if it's NaN or infinite before converting
        if pd.isna(obj):
            return None
        if math.isinf(float(obj)):
            return None  # or return string "Infinity"/"-Infinity"
        return float(obj)
    elif isinstance(obj, np.bool_):
        return bool(obj)
    elif isinstance(obj, np.str_):
        return str(obj)
    elif isinstance(obj, pd.Timestamp):
        return obj.isoformat()
    elif pd.isna(obj):
        # Handle any other NaN values (np.nan, pd.NA, None, float('nan'))
        return None
    elif isinstance(obj, (pd.Series, pd.DataFrame)):
        # Convert pandas objects to native types
        return convert_numpy_to_json_serializable(obj.to_dict())
    else:
        return obj
