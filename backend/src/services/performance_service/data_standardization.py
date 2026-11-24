"""DataFrame column mapping and type standardisation for evaluation."""
import json
import pandas as pd
from typing import Dict, Any


_SECURE_VALUES = {'secure', 'safe', 'positive', '1', 'true', 'yes'}
_INSECURE_VALUES = {'insecure', 'unsafe', 'negative', '0', 'false', 'no'}


def _map_label(val):
    """Map a string prediction/label to 1/0, or attempt numeric conversion."""
    if pd.isna(val):
        return val
    v = str(val).lower().strip()
    if v in _SECURE_VALUES:
        return 1
    if v in _INSECURE_VALUES:
        return 0
    try:
        return float(v)
    except ValueError:
        return val


def _resolve_y_pred(df: pd.DataFrame) -> pd.DataFrame:
    """Map 'output' → 'y_pred', parsing JSON output if needed."""
    if 'output' not in df.columns:
        return df

    if df['output'].dtype == 'object':
        try:
            parsed = df['output'].apply(lambda x: json.loads(x) if isinstance(x, str) else x)
            first = parsed.iloc[0]
            if first and isinstance(first, dict):
                if 'prediction' in first:
                    df['y_pred'] = parsed.apply(lambda x: x.get('prediction') if isinstance(x, dict) else x)
                elif 'output' in first:
                    df['y_pred'] = parsed.apply(lambda x: x.get('output') if isinstance(x, dict) else x)
                else:
                    df['y_pred'] = df['output']
            else:
                df['y_pred'] = df['output']
        except Exception:
            df['y_pred'] = df['output']
    else:
        df['y_pred'] = df['output']

    return df


def standardize_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Standardise a results DataFrame for evaluation:
    - Strip column whitespace
    - Map output → y_pred (with JSON parsing)
    - Map true_value → y_true
    - Encode string labels to 0/1
    - Add label_{attr} columns for sensitive attributes
    """
    df = df.copy()
    df.columns = df.columns.str.strip()

    df = _resolve_y_pred(df)

    if 'true_value' in df.columns:
        df['y_true'] = df['true_value']

    if 'y_pred' in df.columns and df['y_pred'].dtype == 'object':
        df['y_pred'] = df['y_pred'].apply(_map_label)

    if 'y_true' in df.columns and df['y_true'].dtype == 'object':
        df['y_true'] = df['y_true'].apply(_map_label)

    for attr in ('gender', 'age'):
        if attr in df.columns:
            df[f'label_{attr}'] = df[attr]

    return df
