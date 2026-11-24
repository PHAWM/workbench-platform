"""
Orchestration entry points for model evaluation pipelines.

All heavy logic lives in dedicated modules:
  - inference_engine.py   — input prep, API calls, output transformation
  - data_loading.py       — CSV loading, merging, output.csv validation
  - data_standardization.py — column mapping, label encoding
  - feature_evaluation.py — metric functions, range parsing, cross-tabulation
  - classification.py     — classification extraction, ANNIF post-processing
  - conversions.py        — numpy → JSON serialisable types
"""
import pandas as pd
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlmodel import Session

from src.models import Modelmetadata, InputDatasetMetadata, OutputDatasetMetadata, OutputEvaluationData

from src.services.utility_service.s3_storage_service import get_storage_manager, S3StorageManager
from src.services.utility_service.storage_service import (
    parse_storage_location,
    discover_input_data_with_metadata,
    save_output_data,
)

from src.services.performance_service.conversions import convert_numpy
from src.services.performance_service.data_loading import (
    load_and_merge_results,
    validate_output_csv,
    register_metadata_manager,
)
from src.services.performance_service.data_standardization import standardize_dataframe
from src.services.performance_service.feature_evaluation import (
    evaluate_features,
    fallback_evaluation,
    query_metric_features,
)
from src.services.performance_service.inference_engine import (
    run_model_inference,
    run_batch_model_inference,
    run_inference_loop,
    # Re-export for any callers that import from here
    prepare_model_input,
    prepare_model_input_sam,
    transform_model_output,
    transform_model_output_sam,
    transform_model_output_annif,
    is_mcp_model as _is_mcp_model,
    merge_mcp_output as _merge_mcp_output,
    run_mcp_tool_sync as _run_mcp_tool_sync,
)
from src.services.performance_service.classification import (
    extract_classifications,
    process_annif_results,
)

# Re-export small helpers still used by callers
from src.services.performance_service.feature_evaluation import (
    get_metric_function,
    evaluate_function,
    expand_numeric_range,
    parse_range_groups,
    combine_confusion_matrices,
    combine_classification_results,
    combine_group_results,
    create_cross_tabulation_results,
)


# ---------------------------------------------------------------------------
# run_evaluation
# ---------------------------------------------------------------------------

def run_evaluation(
    session: Session,
    model_metadata: Modelmetadata,
    input_dataset_metadata: InputDatasetMetadata,
    output_dataset_metadata: OutputDatasetMetadata,
    metric_name: str,
    user_id: Optional[str] = None,
    storage_base_path: str = "storage",
    api_key=None,
    metric_value_id: Optional[int] = None,
    tenant_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Run model evaluation — uses existing results.csv or runs inference first."""
    storage_manager = get_storage_manager(tenant_id)
    is_s3 = isinstance(storage_manager, S3StorageManager)

    model_name = model_metadata.name
    model_location = model_metadata.location
    input_location = input_dataset_metadata.location
    output_location = output_dataset_metadata.location
    datatypes_info = input_dataset_metadata.datatypes or {}

    if model_location == "run_inference" and user_id and model_metadata.id:
        raise ValueError("No api key — contact the Audit Instigator")

    actual_input_path, _ = parse_storage_location(input_location, storage_manager)
    actual_output_path, _ = parse_storage_location(output_location, storage_manager)
    input_path = Path(actual_input_path)
    output_path = Path(actual_output_path)

    # ---- Resolve results.csv path (local or S3) ----
    if is_s3:
        from src.services.utility_service.storage_service import _local_path_to_s3_key
        output_s3_key = _local_path_to_s3_key(output_location)
        # output_s3_key may be a directory prefix — append results.csv if no extension
        if not output_s3_key.endswith(".csv"):
            output_s3_key = output_s3_key.rstrip("/") + "/results.csv"
        results_csv_s3_key = output_s3_key
        results_csv_exists = storage_manager.file_exists(results_csv_s3_key)
    else:
        results_csv_path = (output_path / "results.csv") if output_path.is_dir() else output_path
        metadata_csv_path = input_path / "metadata.csv"
        results_csv_exists = results_csv_path.exists()

    # ---- Use existing results.csv ----
    if results_csv_exists:
        if is_s3:
            print(f"Found existing results.csv at S3: {results_csv_s3_key}")
            results_df = storage_manager.read_csv(results_csv_s3_key)
            input_s3_key = _local_path_to_s3_key(input_location)
            metadata_s3_key = input_s3_key.rstrip("/") + "/metadata.csv"
            if storage_manager.file_exists(metadata_s3_key):
                print(f"Found metadata.csv at S3: {metadata_s3_key}")
                metadata_df = storage_manager.read_csv(metadata_s3_key)
                if 'id' in results_df.columns and 'id' in metadata_df.columns:
                    results_df = pd.merge(results_df, metadata_df, on='id', how='left')
                    print(f"Merged on 'id': {len(results_df)} rows")
                elif len(results_df) == len(metadata_df):
                    results_df = pd.concat([results_df, metadata_df], axis=1)
                    print("Merged by index position")
            output_df = standardize_dataframe(results_df)
            output_dataset_metadata.location = results_csv_s3_key
        else:
            print(f"Found existing results.csv at: {results_csv_path}")
            output_df = load_and_merge_results(results_csv_path, metadata_csv_path)
            output_df = standardize_dataframe(output_df)
            output_dataset_metadata.location = str(results_csv_path)

        evaluation_result = None
        if metric_name:
            try:
                metric_values = query_metric_features(session, metric_name, metric_value_id)
                if metric_values:
                    raw = evaluate_features(output_df, metric_name, metric_values)
                    evaluation_result = {"underlying_features": convert_numpy(raw)}
                else:
                    evaluation_result = fallback_evaluation(output_df, metric_name)
            except Exception as e:
                evaluation_result = {"error": str(e), "available_columns": list(output_df.columns)}

        _existing_output_loc = results_csv_s3_key if is_s3 else str(results_csv_path)
        result = {
            "success": True,
            "model_id": model_metadata.id,
            "model_name": model_name,
            "model_type": "Generative AI" if model_metadata.model_type else "Predictive AI",
            "total_entries_processed": len(output_df),
            "input_location": input_location,
            "output_location": _existing_output_loc,
            "evaluation_result": evaluation_result,
            "metric_name": metric_name,
            "output_columns": list(output_df.columns),
            "used_existing_results": True,
            "results_source": "existing_results_csv",
        }
        if metric_name is None and not output_df.empty:
            result["predictions"] = output_df.where(pd.notnull(output_df), None).to_dict('records')
        return result

    # ---- Run inference ----
    print("No results.csv found — running inference...")
    if is_s3:
        from src.services.utility_service.storage_service import InputFileMetadataManager
        metadata_manager = InputFileMetadataManager(storage_base_path)
    else:
        metadata_manager = register_metadata_manager(actual_input_path, storage_base_path)
    discovered_entries = discover_input_data_with_metadata(
        input_location, datatypes_info, storage_manager, metadata_manager
    )
    if not discovered_entries:
        raise ValueError(f"No valid input data found at: {input_location}")

    is_sam = any(t in model_name.lower() for t in ("sam", "attachment", "sentiment"))
    use_batch = (
        len(discovered_entries) > 10
        and not is_sam
        and all(e.get('file_type') == 'structured_data' for e in discovered_entries)
    )

    if use_batch:
        batch_inputs = []
        for fi in discovered_entries:
            try:
                batch_inputs.append(prepare_model_input(fi, model_metadata))
            except Exception:
                batch_inputs.append(None)

        valid = [i for i in batch_inputs if i is not None]
        raw_outputs = run_batch_model_inference(model_metadata, valid, api_key, tenant_id=tenant_id)
        output_rows, out_idx = [], 0
        for idx, fi in enumerate(discovered_entries):
            if batch_inputs[idx] is None:
                err = {'file_path': fi['file_path'], 'file_name': fi['file_name'],
                       'model_id': model_metadata.id, 'model_name': model_metadata.name,
                       'processing_error': 'Failed to prepare input', 'prediction_success': False}
                err.update(fi.get('metadata', {}))
                output_rows.append(err)
            else:
                ro = raw_outputs[out_idx]; out_idx += 1
                try:
                    t = _merge_mcp_output(ro, model_metadata, fi) if _is_mcp_model(model_metadata) else transform_model_output(ro, model_metadata, fi)
                    output_rows.append(t)
                except Exception as e:
                    err = {'file_path': fi['file_path'], 'file_name': fi['file_name'],
                           'model_id': model_metadata.id, 'model_name': model_metadata.name,
                           'processing_error': str(e), 'prediction_success': False}
                    err.update(fi.get('metadata', {}))
                    output_rows.append(err)
        output_df = pd.DataFrame(output_rows)
    else:
        output_rows = []
        for idx, fi in enumerate(discovered_entries):
            print(f"Processing {idx + 1}/{len(discovered_entries)} — {fi['file_name']}")
            try:
                mi = prepare_model_input_sam(fi, model_metadata) if is_sam else prepare_model_input(fi, model_metadata)
                ro = run_model_inference(model_metadata, mi, api_key, tenant_id=tenant_id)
                if _is_mcp_model(model_metadata):
                    t = _merge_mcp_output(ro, model_metadata, fi)
                elif is_sam:
                    t = transform_model_output_sam(ro, model_metadata, fi)
                else:
                    t = transform_model_output(ro, model_metadata, fi)
                output_rows.append(t)
            except Exception as e:
                err = {'file_path': fi['file_path'], 'file_name': fi['file_name'],
                       'model_id': model_metadata.id, 'model_name': model_metadata.name,
                       'processing_error': str(e), 'prediction_success': False}
                err.update(fi.get('metadata', {}))
                output_rows.append(err)
        output_df = pd.DataFrame(output_rows)

    if is_s3:
        storage_manager.write_csv(results_csv_s3_key, output_df)
        actual_results = results_csv_s3_key
    else:
        if output_path.suffix:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            actual_results = output_path
        else:
            output_path.mkdir(parents=True, exist_ok=True)
            actual_results = output_path / "results.csv"
        output_df.to_csv(actual_results, index=False)

    evaluation_result = None
    if metric_name:
        try:
            eval_kwargs: Dict = {}
            if metric_name in ('keyword_accuracy', 'batch_keyword_accuracy'):
                for col in output_df.columns:
                    if col == 'expected_subjects' or col.startswith('expected_subjects_'):
                        eval_kwargs['y_true'] = output_df[col].fillna('').values
                    if col == 'predicted_subjects' or col.startswith('predicted_subjects_'):
                        eval_kwargs['y_pred'] = output_df[col].fillna('').values
            else:
                for c, k in [('y_pred', 'y_pred'), ('y_true', 'y_true'), ('y_pred_proba', 'y_pred_proba')]:
                    if c in output_df.columns:
                        eval_kwargs[k] = output_df[c].dropna().values
                for col in output_df.columns:
                    if col.startswith('label_') and any(s in col.lower() for s in ('gender', 'age')):
                        eval_kwargs['sensitive_attr'] = output_df[col].dropna().values
                        break
            if len(eval_kwargs) >= 2:
                from src.services.performance_service.feature_evaluation import evaluate_function
                result = evaluate_function(metric_name, **eval_kwargs)
                evaluation_result = {"underlying_features": {"all": {"all": result}}}
            else:
                evaluation_result = {"warning": "Insufficient data for evaluation"}
        except Exception as e:
            evaluation_result = {"error": str(e)}

    successful = len(output_df)
    if 'prediction_success' in output_df.columns:
        successful = len(output_df[output_df['prediction_success'] != False])

    result = {
        "success": True,
        "model_id": model_metadata.id,
        "model_name": model_name,
        "model_type": "Generative AI" if model_metadata.model_type else "Predictive AI",
        "total_entries_processed": len(output_df),
        "successful_predictions": successful,
        "input_location": input_location,
        "output_location": str(actual_results),
        "evaluation_result": evaluation_result,
        "metric_name": metric_name,
        "output_columns": list(output_df.columns),
        "used_existing_results": False,
        "results_source": "new_inference",
    }
    if metric_name is None and not output_df.empty:
        result["predictions"] = output_df.where(pd.notnull(output_df), None).to_dict('records')
    return result


# ---------------------------------------------------------------------------
# run_output_classification
# ---------------------------------------------------------------------------

def run_output_classification(
    session: Session,
    model_metadata: Modelmetadata,
    input_dataset_metadata: OutputEvaluationData,
    user_id: Optional[str] = None,
    storage_base_path: str = "storage",
    api_key=None,
    *args,
    tenant_id: Optional[str] = None,
    **kwargs,
) -> Dict[str, Any]:
    """Run output-only classification — classify model output without computing metrics."""
    try:
        storage_manager = get_storage_manager(tenant_id)
        model_name = model_metadata.name
        model_location = model_metadata.location

        location_path = Path(input_dataset_metadata.location)
        input_location = str(location_path.parent) if location_path.suffix else input_dataset_metadata.location
        output_location = input_location.replace('/input', '/output')

        if model_location == "run_inference" and user_id and model_metadata.id:
            raise ValueError("No api key — contact the Audit Instigator")

        if isinstance(storage_manager, S3StorageManager):
            from src.services.utility_service.storage_service import InputFileMetadataManager
            metadata_manager = InputFileMetadataManager(storage_base_path)
        else:
            metadata_manager = register_metadata_manager(input_location, storage_base_path)
        discovered_entries = discover_input_data_with_metadata(input_location, {}, storage_manager, metadata_manager)

        if not discovered_entries:
            return {"success": False, "error": "no_input_data",
                    "message": "No input data found. Please upload input files first.", "classifications": []}

        can_run_inference = bool(model_location and model_location.strip())
        output_csv_path = Path(output_location) / "output.csv"
        input_file_names = {e['file_name'] for e in discovered_entries}
        existing_df = validate_output_csv(output_csv_path, input_file_names)

        if existing_df is not None:
            output_df = existing_df
        elif not can_run_inference:
            return {"success": False, "error": "no_inference_available",
                    "message": "No API connection available and no output.csv found.", "classifications": []}
        else:
            output_df, failed = run_inference_loop(discovered_entries, model_metadata, output_csv_path, api_key, tenant_id=tenant_id)
            if output_df is None:
                return {"success": False, "error": "api_connection_failed",
                        "message": "API connection failed and no output.csv fallback found.", "classifications": []}

        actual_output_path = save_output_data(output_df, output_location, storage_manager, f"{model_name}_classification")

        output_df.columns = output_df.columns.str.strip()
        classifications = extract_classifications(output_df, model_name)

        response: Dict[str, Any] = {
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

        if 'annif' in model_name.lower():
            annif = process_annif_results(output_df, classifications, output_location)
            if annif.get('results_csv_path'):
                response["results_csv_path"] = annif['results_csv_path']
            if annif.get('accuracy_metrics'):
                response["accuracy_metrics"] = annif['accuracy_metrics']

        return response

    except Exception as e:
        import traceback; traceback.print_exc()
        return {"success": False, "error": str(e),
                "model_id": getattr(model_metadata, 'id', None),
                "model_name": getattr(model_metadata, 'name', 'unknown'),
                "output_location": None, "classifications": []}


# ---------------------------------------------------------------------------
# run_output_evaluation
# ---------------------------------------------------------------------------

def run_output_evaluation(
    session: Session,
    model_metadata: Modelmetadata,
    input_dataset_metadata: OutputEvaluationData,
    metric_name: str,
    user_id: Optional[str] = None,
    storage_base_path: str = "storage",
    api_key=None,
    metric_value_id: Optional[int] = None,
    tenant_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Run output evaluation — inference + metric computation."""
    try:
        storage_manager = get_storage_manager(tenant_id)
        model_name = model_metadata.name
        model_location = model_metadata.location

        location_path = Path(input_dataset_metadata.location)
        input_location = str(location_path.parent) if location_path.suffix else input_dataset_metadata.location
        output_location = input_location.replace('/input', '/output')

        if model_location == "run_inference" and user_id and model_metadata.id:
            raise ValueError("No api key — contact the Audit Instigator")

        if isinstance(storage_manager, S3StorageManager):
            from src.services.utility_service.storage_service import InputFileMetadataManager
            metadata_manager = InputFileMetadataManager(storage_base_path)
        else:
            metadata_manager = register_metadata_manager(input_location, storage_base_path)
        discovered_entries = discover_input_data_with_metadata(input_location, {}, storage_manager, metadata_manager)

        if not discovered_entries:
            return {
                "success": False, "error": "no_input_data",
                "message": "No input data found. Please upload input files first.",
                "model_id": model_metadata.id, "model_name": model_name, "output_location": None,
                "evaluation_result": {"error": "No input data", "status": "pending"},
            }

        can_run_inference = bool(model_location and model_location.strip())
        output_csv_path = Path(output_location) / "output.csv"
        input_file_names = {e['file_name'] for e in discovered_entries}
        existing_df = validate_output_csv(output_csv_path, input_file_names)

        if existing_df is not None:
            output_df = existing_df
        elif not can_run_inference:
            return {
                "success": False, "error": "no_inference_available",
                "message": "No API connection and no output.csv found.",
                "evaluation_result": {"error": "Results will be calculated later", "status": "pending"},
            }
        else:
            output_df, failed = run_inference_loop(discovered_entries, model_metadata, output_csv_path, api_key, tenant_id=tenant_id)
            if output_df is None:
                return {
                    "success": False, "error": "api_connection_failed",
                    "message": "API failed and no output.csv fallback found.",
                    "evaluation_result": {"error": "Results will be calculated later", "status": "pending"},
                }

        actual_output_path = save_output_data(output_df, output_location, storage_manager, f"{model_name}_evaluation")

        evaluation_result = None
        if metric_name:
            try:
                metric_values = query_metric_features(session, metric_name, metric_value_id)
                if metric_values:
                    raw = evaluate_features(output_df, metric_name, metric_values)
                    evaluation_result = {"underlying_features": convert_numpy(raw)}
                else:
                    evaluation_result = fallback_evaluation(output_df, metric_name)
            except Exception as e:
                evaluation_result = {"error": str(e)}

        return {
            "success": True,
            "model_id": model_metadata.id,
            "model_name": model_name,
            "model_type": "Generative AI" if model_metadata.model_type else "Predictive AI",
            "total_entries_processed": len(output_df),
            "input_location": input_location,
            "output_location": actual_output_path,
            "evaluation_result": evaluation_result,
            "metric_name": metric_name,
            "output_columns": list(output_df.columns),
            "metadata_enhanced": metadata_manager is not None,
        }

    except Exception as e:
        return {
            "success": False, "error": str(e),
            "model_id": getattr(model_metadata, 'id', None),
            "model_name": getattr(model_metadata, 'name', 'unknown'),
            "output_location": None, "evaluation_result": None,
        }
