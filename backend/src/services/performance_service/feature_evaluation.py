"""Feature evaluation — metric functions, range parsing, cross-tabulation, DB queries."""
import re
from itertools import product
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from sqlmodel import Session, select

from src.services.performance_service.functions import METRICS_REGISTRY


# ---------------------------------------------------------------------------
# Metric registry helpers
# ---------------------------------------------------------------------------

def get_metric_function(metric_name: str):
    if metric_name not in METRICS_REGISTRY:
        raise ValueError(f"Metric '{metric_name}' not found. Available: {list(METRICS_REGISTRY.keys())}")
    return METRICS_REGISTRY[metric_name]


def evaluate_function(metric_name: str, **kwargs):
    try:
        return get_metric_function(metric_name)(**kwargs)
    except Exception as e:
        return {"status": "cannot be calculated", "error": str(e), "error_type": type(e).__name__, "metric_name": metric_name}


# ---------------------------------------------------------------------------
# Range parsing
# ---------------------------------------------------------------------------

def expand_numeric_range(start: str, end: str) -> List[str]:
    """Expand 'P2'-'P4' → ['P2', 'P3', 'P4']."""
    sm = re.match(r'^([A-Za-z]*)(\d+)$', start.strip())
    em = re.match(r'^([A-Za-z]*)(\d+)$', end.strip())
    if sm and em:
        sp, sn = sm.groups()
        ep, en = em.groups()
        if sp == ep and int(sn) <= int(en):
            return [f"{sp}{i}" for i in range(int(sn), int(en) + 1)]
    return [start.strip(), end.strip()]


def parse_range_groups(ranges: List[str]) -> Tuple[Dict[str, List[str]], List[str]]:
    """
    Parse range specs into (range_groups, expanded_ranges).
    Supports: 'P1-P2' (numeric range), 'P1|P2|P3' (pipe list), 'P1, P2' (comma list).
    """
    range_groups: Dict[str, List[str]] = {}
    expanded: List[str] = []

    for r in ranges:
        rs = str(r)
        if '-' in rs and '|' not in rs and ',' not in rs:
            parts = rs.split('-')
            vals = expand_numeric_range(parts[0], parts[1]) if len(parts) == 2 else [v.strip() for v in parts if v.strip()]
        elif '|' in rs or ',' in rs:
            vals = [v.strip() for v in re.split(r'[|,]', rs) if v.strip()]
        else:
            vals = [rs.strip()]
        range_groups[rs] = vals
        expanded.extend(vals)

    return range_groups, expanded


# ---------------------------------------------------------------------------
# Result combination
# ---------------------------------------------------------------------------

def combine_confusion_matrices(matrices: List) -> Optional[List]:
    if not matrices:
        return None
    result = np.array(matrices[0])
    for m in matrices[1:]:
        result = result + np.array(m)
    return result.tolist()


def combine_classification_results(all_groups: Dict, group_keys: List[str]) -> Optional[Dict]:
    """Sum confusion matrices across groups and recalculate metrics."""
    groups_lower = {str(k).lower(): k for k in all_groups}
    matrices, total_samples = [], 0

    for key in group_keys:
        actual = key if key in all_groups else groups_lower.get(str(key).lower())
        if actual is None:
            continue
        g = all_groups[actual]
        if isinstance(g, dict) and 'confusion_matrix' in g:
            matrices.append(g['confusion_matrix'])
            total_samples += g.get('sample_size', g.get('count', 0))

    if not matrices:
        return combine_group_results(all_groups, group_keys)

    combined_cm = combine_confusion_matrices(matrices)
    if combined_cm is None:
        return None

    cm = np.array(combined_cm)
    if cm.shape == (2, 2):
        tn, fp, fn, tp = cm.ravel()
        denom = tp + tn + fp + fn
        return {
            'confusion_matrix': combined_cm,
            'true_positives': int(tp),
            'true_negatives': int(tn),
            'false_positives': int(fp),
            'false_negatives': int(fn),
            'accuracy': float((tp + tn) / denom) if denom else 0,
            'precision': float(tp / (tp + fp)) if (tp + fp) else 0,
            'recall': float(tp / (tp + fn)) if (tp + fn) else 0,
            'specificity': float(tn / (tn + fp)) if (tn + fp) else 0,
            'false_positive_rate': float(fp / (tn + fp)) if (tn + fp) else 0,
            'false_negative_rate': float(fn / (tp + fn)) if (tp + fn) else 0,
            'sample_size': total_samples if total_samples > 0 else int(denom),
        }
    return {'confusion_matrix': combined_cm, 'sample_size': total_samples}


def combine_group_results(all_groups: Dict, individual_values: List[str]) -> Optional[Dict]:
    """Average numeric metrics across groups, weighted by count."""
    combined = None
    combined_count = 0

    for val in individual_values:
        for gk, gv in all_groups.items():
            if str(gk).lower() == str(val).lower():
                if combined is None:
                    combined = gv.copy() if isinstance(gv, dict) else gv
                    combined_count = gv.get('count', 0) if isinstance(gv, dict) else 0
                elif isinstance(gv, dict):
                    curr_count = gv.get('count', 1)
                    prev_count = combined.get('count', 1)
                    combined_count += curr_count
                    for k, v in gv.items():
                        if k == 'count':
                            continue
                        if isinstance(v, (int, float)) and k in combined:
                            total = prev_count + curr_count
                            combined[k] = (combined[k] * prev_count + v * curr_count) / total
                break

    if combined is not None and isinstance(combined, dict) and 'count' in combined:
        combined['count'] = combined_count
    return combined


# ---------------------------------------------------------------------------
# Cross-tabulation
# ---------------------------------------------------------------------------

def _build_eval_kwargs(df: pd.DataFrame, metric_name: str, expected_col=None, predicted_col=None) -> Dict:
    kwargs = {}
    if metric_name in ('keyword_accuracy', 'batch_keyword_accuracy'):
        if expected_col and expected_col in df.columns:
            kwargs['y_true'] = df[expected_col].fillna('').values
        if predicted_col and predicted_col in df.columns:
            kwargs['y_pred'] = df[predicted_col].fillna('').values
    else:
        for col, key in [('y_pred', 'y_pred'), ('y_true', 'y_true'), ('y_pred_proba', 'y_pred_proba')]:
            if col in df.columns:
                kwargs[key] = df[col].dropna().values
    return kwargs


def _evaluate_and_combine(df: pd.DataFrame, metric_name: str, expected_col=None, predicted_col=None) -> Any:
    kwargs = _build_eval_kwargs(df, metric_name, expected_col, predicted_col)
    result = evaluate_function(metric_name, **kwargs)
    if isinstance(result, dict) and 'groups' in result:
        groups = result['groups']
        combined = combine_classification_results(groups, list(groups.keys()))
        return combined if combined is not None else list(groups.values())[0]
    return result


def create_cross_tabulation_results(
    output_df: pd.DataFrame,
    features_config: List[Dict],
    metric_name: str,
    eval_kwargs_base: Dict,
    expected_col: Optional[str] = None,
    predicted_col: Optional[str] = None,
) -> Dict:
    """Cross-tabulate evaluation results for two (or more) underlying features."""
    # Map feature names → actual column names (case-insensitive)
    feature_cols = {}
    for fc in features_config:
        name = fc['feature_name']
        if name in output_df.columns:
            feature_cols[name] = name
        else:
            for col in output_df.columns:
                if col.lower() == name.lower():
                    feature_cols[name] = col
                    break

    missing = [f['feature_name'] for f in features_config if f['feature_name'] not in feature_cols]
    if missing:
        return {'error': 'Some features not found in dataframe', 'missing_features': missing}

    primary = features_config[0]
    secondary_features = features_config[1:]
    results = {}

    for p_range, p_values in primary['range_groups'].items():
        p_col = feature_cols[primary['feature_name']]
        p_mask = pd.Series(False, index=output_df.index)
        for v in p_values:
            p_mask |= output_df[p_col].astype(str).str.lower() == str(v).lower()
        p_df = output_df[p_mask]

        if len(p_df) == 0:
            results[p_range] = {'status': 'no_data', 'message': f'No data for {p_range}'}
            continue

        if secondary_features:
            results[p_range] = {}
            sec = secondary_features[0]
            s_col = feature_cols[sec['feature_name']]
            for s_range, s_values in sec['range_groups'].items():
                s_mask = pd.Series(False, index=p_df.index)
                for v in s_values:
                    s_mask |= p_df[s_col].astype(str).str.lower() == str(v).lower()
                combined_df = p_df[s_mask]
                if len(combined_df) == 0:
                    results[p_range][s_range] = {'status': 'no_data', 'message': f'No data for {p_range}+{s_range}'}
                    continue
                try:
                    results[p_range][s_range] = _evaluate_and_combine(combined_df, metric_name, expected_col, predicted_col)
                except Exception as e:
                    results[p_range][s_range] = {'error': str(e), 'sample_size': len(combined_df)}
        else:
            try:
                results[p_range] = _evaluate_and_combine(p_df, metric_name, expected_col, predicted_col)
            except Exception as e:
                results[p_range] = {'error': str(e), 'sample_size': len(p_df)}

    return results


# ---------------------------------------------------------------------------
# DB query
# ---------------------------------------------------------------------------

def query_metric_features(session: Session, metric_name: str, metric_value_id: Optional[int]):
    """
    Query MetricsValues + UnderlyingFeatures from DB.
    Returns list of (MetricsValues, MetricsUnderlyingFeatures, UnderlyingFeatures) tuples.
    """
    from src.models import (
        MetricsValues, MetricsUnderlyingFeatures, UnderlyingFeatures,
        Metrics, MetricsTargetFeatures, TargetFeatures,
    )

    if metric_value_id:
        return session.exec(
            select(MetricsValues, MetricsUnderlyingFeatures, UnderlyingFeatures)
            .join(MetricsUnderlyingFeatures, MetricsValues.id == MetricsUnderlyingFeatures.metric_values_id)
            .join(UnderlyingFeatures, MetricsUnderlyingFeatures.feature_id == UnderlyingFeatures.id)
            .where(MetricsValues.id == metric_value_id)
        ).all()

    metric_with_target = session.exec(
        select(Metrics, TargetFeatures)
        .join(MetricsTargetFeatures, Metrics.id == MetricsTargetFeatures.metric_values_id)
        .join(TargetFeatures, MetricsTargetFeatures.target_feature_id == TargetFeatures.id)
        .where(TargetFeatures.function_name == metric_name)
    ).first()

    if not metric_with_target:
        return []

    return session.exec(
        select(MetricsValues, MetricsUnderlyingFeatures, UnderlyingFeatures)
        .join(MetricsUnderlyingFeatures, MetricsValues.id == MetricsUnderlyingFeatures.metric_values_id)
        .join(UnderlyingFeatures, MetricsUnderlyingFeatures.feature_id == UnderlyingFeatures.id)
        .join(MetricsTargetFeatures, MetricsValues.id == MetricsTargetFeatures.metric_values_id)
        .join(TargetFeatures, MetricsTargetFeatures.target_feature_id == TargetFeatures.id)
        .where(TargetFeatures.function_name == metric_name)
    ).all()


# ---------------------------------------------------------------------------
# Main evaluation loop
# ---------------------------------------------------------------------------

def _find_keyword_cols(df: pd.DataFrame):
    expected_col = predicted_col = None
    for col in df.columns:
        if col == 'expected_subjects' or col.startswith('expected_subjects_'):
            expected_col = col
        if col == 'predicted_subjects' or col.startswith('predicted_subjects_'):
            predicted_col = col
    return expected_col, predicted_col


def evaluate_features(
    output_df: pd.DataFrame,
    metric_name: str,
    metric_values: List,
) -> Dict:
    """
    Core feature evaluation loop shared by run_evaluation and run_output_evaluation.
    Returns underlying_features_results dict (before numpy conversion).
    """
    features_config = []
    for _, fm, feat in metric_values:
        ranges = fm.ranges or []
        if not isinstance(ranges, list):
            ranges = []
        rg, er = parse_range_groups(ranges)
        features_config.append({
            'feature_name': feat.feature_name,
            'ranges': ranges,
            'range_groups': rg,
            'expanded_ranges': er,
        })

    features_with_ranges = [f for f in features_config if f['ranges']]
    use_cross_tab = len(features_with_ranges) > 1

    if use_cross_tab:
        expected_col, predicted_col = _find_keyword_cols(output_df)
        eval_kwargs_base = _build_eval_kwargs(output_df, metric_name, expected_col, predicted_col)
        return create_cross_tabulation_results(
            output_df, features_with_ranges, metric_name, eval_kwargs_base, expected_col, predicted_col
        )

    # Single-feature path
    results = {}
    for _, fm, feat in metric_values:
        feature_name = feat.feature_name
        ranges = fm.ranges or []
        if not isinstance(ranges, list):
            ranges = []

        range_groups, expanded_ranges = parse_range_groups(ranges)

        if feature_name not in results:
            results[feature_name] = {}

        expected_col, predicted_col = _find_keyword_cols(output_df)

        # Locate the sensitive attribute column
        sensitive_col = next(
            (c for c in output_df.columns if c == feature_name or c.lower() == feature_name.lower()),
            None
        )
        if not sensitive_col:
            print(f"Warning: Feature '{feature_name}' not found in columns: {list(output_df.columns)}")
            continue

        # Filter to matching range values
        if ranges:
            mask = pd.Series(False, index=output_df.index)
            for v in expanded_ranges:
                mask |= output_df[sensitive_col].astype(str).str.lower() == str(v).lower()
            filtered_df = output_df[mask]
            if len(filtered_df) == 0:
                results[feature_name] = {
                    'status': 'no_matching_data',
                    'error': f'No data matching ranges: {ranges}',
                    'defined_ranges': ranges,
                    'expanded_ranges': expanded_ranges,
                    'available_values': output_df[sensitive_col].unique().tolist(),
                    'message': 'Update ranges to match available values, or leave empty to evaluate all.',
                }
                continue
        else:
            filtered_df = output_df

        valid = filtered_df[sensitive_col].notna()
        eval_kwargs: Dict = {'sensitive_attr': filtered_df.loc[valid, sensitive_col].values}

        if metric_name in ('keyword_accuracy', 'batch_keyword_accuracy'):
            if expected_col and expected_col in filtered_df.columns:
                eval_kwargs['y_true'] = filtered_df.loc[valid, expected_col].fillna('').values
            if predicted_col and predicted_col in filtered_df.columns:
                eval_kwargs['y_pred'] = filtered_df.loc[valid, predicted_col].fillna('').values
        else:
            for col, key in [('y_pred', 'y_pred'), ('y_true', 'y_true'), ('y_pred_proba', 'y_pred_proba')]:
                if col in filtered_df.columns:
                    eval_kwargs[key] = filtered_df.loc[valid, col].dropna().values

        if len(eval_kwargs) < 2 or 'sensitive_attr' not in eval_kwargs:
            print(f"Insufficient data for {feature_name}: keys={list(eval_kwargs.keys())}")
            continue

        try:
            result = evaluate_function(metric_name, **eval_kwargs)

            if isinstance(result, dict) and result.get("status") == "cannot be calculated":
                results[feature_name] = result
            elif isinstance(result, dict):
                if 'groups' in result:
                    all_groups = result['groups']
                else:
                    uv_str = {str(v) for v in eval_kwargs.get('sensitive_attr', [])}
                    rk_str = {str(k) for k in result.keys()}
                    all_groups = result if rk_str & uv_str else None
                    if all_groups is None:
                        results[feature_name] = {'overall': result}

                if all_groups is not None:
                    if ranges:
                        processed = {}
                        for orig, vals in range_groups.items():
                            if len(vals) > 1:
                                combined = combine_classification_results(all_groups, vals) or combine_group_results(all_groups, vals)
                                if combined is not None:
                                    processed[orig] = combined
                            else:
                                for gk, gv in all_groups.items():
                                    if str(gk).lower() == str(orig).lower():
                                        processed[orig] = gv
                                        break
                        results[feature_name] = processed
                    else:
                        results[feature_name] = all_groups
            else:
                results[feature_name] = {'overall': result}

        except Exception as e:
            import traceback
            traceback.print_exc()
            results[feature_name] = {
                'error': str(e),
                'error_type': type(e).__name__,
                'feature_name': feature_name,
                'defined_ranges': ranges,
                'data_sample_count': len(eval_kwargs.get('sensitive_attr', [])),
            }

    return results


def fallback_evaluation(output_df: pd.DataFrame, metric_name: str) -> Optional[Dict]:
    """
    Simple evaluation without underlying feature grouping (used when no DB metric found).
    Returns evaluation_result dict or None if insufficient data.
    """
    eval_kwargs: Dict = {}
    expected_col, predicted_col = _find_keyword_cols(output_df)

    if metric_name in ('keyword_accuracy', 'batch_keyword_accuracy'):
        if expected_col and predicted_col:
            eval_kwargs['y_true'] = output_df[expected_col].fillna('').values
            eval_kwargs['y_pred'] = output_df[predicted_col].fillna('').values
        elif expected_col:
            return {
                "error": "Missing predicted_subjects column",
                "message": "Run output classification first to generate predictions.",
                "available_columns": list(output_df.columns),
                "found_expected": expected_col,
                "missing": "predicted_subjects",
            }
    else:
        for col, key in [('y_pred', 'y_pred'), ('y_true', 'y_true')]:
            if col in output_df.columns:
                eval_kwargs[key] = output_df[col].dropna().values

    if len(eval_kwargs) < 2:
        return {"warning": "Insufficient data for evaluation", "available_columns": list(output_df.columns)}

    result = evaluate_function(metric_name, **eval_kwargs)
    return {"underlying_features": {"all": {"all": result}}}
