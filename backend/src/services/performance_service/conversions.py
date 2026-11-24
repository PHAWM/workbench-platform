"""Type conversion utilities — numpy → JSON-serialisable Python types."""
import numpy as np


def convert_numpy(obj):
    """Recursively convert numpy types to native Python types for JSON serialisation."""
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, dict):
        result = {}
        for k, v in obj.items():
            if isinstance(k, (np.int64, np.int32, np.int16, np.int8)):
                k = int(k)
            elif isinstance(k, (np.float64, np.float32, np.float16)):
                k = float(k)
            elif isinstance(k, np.str_):
                k = str(k)
            result[k] = convert_numpy(v)
        return result
    if isinstance(obj, list):
        return [convert_numpy(item) for item in obj]
    if isinstance(obj, (np.int64, np.int32, np.int16, np.int8)):
        return int(obj)
    if isinstance(obj, (np.float64, np.float32, np.float16)):
        return float(obj)
    if isinstance(obj, np.str_):
        return str(obj)
    return obj
