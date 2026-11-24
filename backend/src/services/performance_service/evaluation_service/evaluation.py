"""Main evaluation service functions"""
from typing import Any, Dict, List
from fastapi import HTTPException
from sqlmodel import Session, select, and_
import traceback

from src.models import *
from .utils import convert_numpy_to_json_serializable, should_skip_performance_pipeline
from src.services.performance_service.run_functions import run_evaluation


async def generate_results_comprehensive(
    audit_id: int,
    current_user_id: str,
    session: Session,
    tenant_id: str | None = None
) -> 'OutputEvaluationResponse':
    """
    Generate evaluation results by running inference and evaluation on datasets.

    This service function handles the entire business logic for generating evaluation results,
    including:
    - User audit access verification
    - Complex pipeline query with 10+ joins and aliases
    - Duplicate pipeline removal
    - Target feature validation
    - Qualitative vs quantitative metric detection
    - Evaluation execution via run_evaluation
    - MetricsValues output storage
    - Response construction with threshold handling

    Args:
        audit_id: The ID of the audit
        current_user_id: The ID of the user generating the results
        session: Database session

    Returns:
        OutputEvaluationResponse with audit_criteria list

    Raises:
        HTTPException: If user has no access or evaluation fails
    """
    # Verify user has access to this audit
    current_user_audit = session.exec(
        select(MappingAuditUser)
        .where(
            MappingAuditUser.audit_id == audit_id,
            MappingAuditUser.user_id == current_user_id
        )
    ).first()

    if not current_user_audit:
        raise HTTPException(status_code=403, detail="User does not have access to this audit")

    skip, reason = should_skip_performance_pipeline(audit_id, session)
    if skip:
        return {"skipped": True, "reason": reason, "audit_criteria": []}

    # Get the audit instigator's user_audit_id
    # MappingMetricsEvents and MappingEventsAuditStatus are created by the instigator
    audit_instigator = session.exec(
        select(MappingAuditUser)
        .join(AuditRoles, AuditRoles.id == MappingAuditUser.roles_id)
        .where(
            MappingAuditUser.audit_id == audit_id,
            AuditRoles.role == 'audit_instigator'
        )
    ).first()

    # Fallback to current user if no instigator found (shouldn't happen normally)
    instigator_user_audit_id = audit_instigator.id if audit_instigator else current_user_audit.id

    print(f"\nDebug: Querying pipelines for audit_id={audit_id}, current_user_audit.id={current_user_audit.id}, instigator_user_audit_id={instigator_user_audit_id}")

    # Check if there are any MappingAuditPipelineEvents for the instigator
    test_pipeline_events = session.exec(
        select(MappingAuditPipelineEvents)
        .where(MappingAuditPipelineEvents.user_audit_id == instigator_user_audit_id)
    ).all()
    print(f"Debug: Found {len(test_pipeline_events)} MappingAuditPipelineEvents for instigator_user_audit_id={instigator_user_audit_id}")

    # Get the pipelines - filter by current user's user_audit_id
    # Only show pipeline events assigned to this specific user
    # Refactored to avoid aliased by using subqueries for verification
    pipelines = session.exec(
        select(
            MappingAuditPipelineEvents.id,
            MappingAuditPipelineEvents.audit_pipeline,
            MappingAuditPipelineEvents.user_audit_id,
            MappingAuditPipelineEvents.event_id,
            MappingAuditPipelineEvents.metric_id,
            TargetFeatures.target_feature,
            DatasetMetadata.id.label('dataset_id'),
            Modelmetadata.id.label('model_id'),
            Modelmetadata.name.label('model_name'),
            MetricsValues.id.label('metric_value_id'),
            MetricsValues.threshold,
            Apikeymodel.model_api_key,
            MappingEventsAuditStatus.id.label('audit_criteria_id'),
            UserMetricThresholds.custom_threshold
        )
        .join(Events, MappingAuditPipelineEvents.event_id == Events.id)
        .join(Metrics, MappingAuditPipelineEvents.metric_id == Metrics.id)
        .join(MappingMetricsEvents, and_(
            MappingAuditPipelineEvents.metric_id == MappingMetricsEvents.metric_id,
            MappingAuditPipelineEvents.event_id == MappingMetricsEvents.event_id
        ))
        .join(MappingEventsAuditStatus, and_(
            MappingAuditPipelineEvents.metric_id == MappingEventsAuditStatus.metric_id,
            MappingAuditPipelineEvents.event_id == MappingEventsAuditStatus.event_id,
            MappingEventsAuditStatus.user_audit_id == current_user_audit.id
        ))
        .join(MetricsValues, MappingMetricsEvents.values_id == MetricsValues.id)
        .outerjoin(MetricsUnderlyingFeatures, MetricsValues.id == MetricsUnderlyingFeatures.metric_values_id)
        .outerjoin(UnderlyingFeatures, MetricsUnderlyingFeatures.feature_id == UnderlyingFeatures.id)
        .outerjoin(MetricsTargetFeatures, MetricsValues.id == MetricsTargetFeatures.metric_values_id)
        .outerjoin(TargetFeatures, MetricsTargetFeatures.target_feature_id == TargetFeatures.id)
        .join(MappingAuditPipelineAudit, and_(
            MappingAuditPipelineEvents.audit_pipeline == MappingAuditPipelineAudit.audit_pipeline,
            MappingAuditPipelineAudit.audit_id == audit_id
        ))
        .join(MappingAuditUser, MappingAuditPipelineEvents.user_audit_id == MappingAuditUser.id)
        .outerjoin(UserMetricThresholds, and_(
            UserMetricThresholds.user_audit_id == current_user_audit.id,
            UserMetricThresholds.metric_id == MappingAuditPipelineEvents.metric_id,
            UserMetricThresholds.event_id == MappingAuditPipelineEvents.event_id,
            UserMetricThresholds.values_id == MetricsValues.id
        ))
        .join(MappingModelDatasetAudit, MappingModelDatasetAudit.auditpipeline == MappingAuditPipelineAudit.audit_pipeline)
        .join(DatasetMetadata, MappingModelDatasetAudit.dataset_id == DatasetMetadata.id)
        .join(Modelmetadata, MappingModelDatasetAudit.model_id == Modelmetadata.id)
        .outerjoin(Apikeymodel, Apikeymodel.model_metadata_id == Modelmetadata.id)
        .where(
            MappingAuditPipelineAudit.audit_id == audit_id,
            MappingAuditPipelineEvents.user_audit_id == current_user_audit.id,
            MappingAuditUser.audit_id == audit_id
        )
    ).all()

    # The outer joins can create duplicates, so we deduplicate by pipeline event ID
    seen_ids = set()
    unique_pipelines = []
    for p in pipelines:
        if p.id not in seen_ids:
            seen_ids.add(p.id)
            unique_pipelines.append(p)
    pipelines = unique_pipelines

    print(f"\nFound {len(pipelines)} pipeline(s) for audit {audit_id}")

    results = []
    for pipeline_row in pipelines:
        # Fetch the actual objects we need
        dataset = session.get(DatasetMetadata, pipeline_row.dataset_id)
        model = session.get(Modelmetadata, pipeline_row.model_id)

        # If there is no API key, inference cannot run — but if a results.csv already
        # exists at the output location we don't need inference at all (gray-box / black-box
        # audits where the instigator pre-computed results).  Only raise an error when
        # inference is truly required (no results.csv present).
        if pipeline_row.model_api_key is None:
            output_meta = dataset.output_dataset_metadata[-1] if dataset and dataset.output_dataset_metadata else None
            results_csv_exists = False
            if output_meta and output_meta.location:
                from src.services.utility_service.s3_storage_service import get_storage_manager, S3StorageManager
                from src.services.utility_service.storage_service import parse_storage_location
                from pathlib import Path as _Path
                _sm = get_storage_manager(tenant_id)
                _out_path, _ = parse_storage_location(output_meta.location, _sm)
                if isinstance(_sm, S3StorageManager):
                    from src.services.utility_service.storage_service import _local_path_to_s3_key
                    _key = _local_path_to_s3_key(output_meta.location)
                    if not _key.endswith(".csv"):
                        _key = _key.rstrip("/") + "/results.csv"
                    results_csv_exists = _sm.file_exists(_key)
                else:
                    _p = _Path(_out_path)
                    _csv = (_p / "results.csv") if _p.is_dir() else _p
                    results_csv_exists = _csv.exists()

            if not results_csv_exists:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"No API key found for model '{model.name if model else pipeline_row.model_id}' "
                        f"and no results.csv found at the output location. "
                        f"Either upload a results.csv or add an API key via POST /api/v1/pipeline/api-keys/."
                    ),
                )

        # Fetch MetricValue to check output
        metric_value = session.exec(
            select(MetricsValues).where(MetricsValues.id == pipeline_row.metric_value_id)
        ).first()

        # Determine the effective threshold (custom if exists, otherwise default)
        # If base threshold is "Not Set" (case-insensitive), check for any custom threshold
        base_threshold = pipeline_row.threshold
        if pipeline_row.custom_threshold is not None:
            effective_threshold = pipeline_row.custom_threshold
        elif base_threshold and base_threshold.lower() == "not set":
            # Look for any custom threshold for this metric/event/values combination
            any_custom = session.exec(
                select(UserMetricThresholds.custom_threshold).where(
                    UserMetricThresholds.metric_id == pipeline_row.metric_id,
                    UserMetricThresholds.event_id == pipeline_row.event_id,
                    UserMetricThresholds.values_id == pipeline_row.metric_value_id
                )
            ).first()
            effective_threshold = any_custom if any_custom else base_threshold
        else:
            effective_threshold = base_threshold

        # Check if this is a qualitative metric
        has_scale_points = session.exec(
            select(MetricsScalePoints).where(MetricsScalePoints.metric_values_id == pipeline_row.metric_value_id)
        ).first()

        is_qualitative = has_scale_points is not None

        # Skip if no target features mapped AND not qualitative
        if pipeline_row.target_feature is None and not is_qualitative:
            print(f"Skipping metric value {pipeline_row.metric_value_id} - no target feature mapped and not qualitative")
            continue

        # For qualitative metrics, we still need to get model output even without evaluation
        if metric_value.output == {} or metric_value.output is None or "error" in metric_value.output.keys() :
            # Qualitative metrics: run inference without evaluation
            if is_qualitative and pipeline_row.target_feature is None:
                print(f"Metric value {metric_value.id} is qualitative - running inference only (no evaluation)")

                try:
                    # Run inference without evaluation by passing metric_name=None
                    output_data = run_evaluation(
                        session,
                        model,
                        dataset.input_dataset_metadata[-1],
                        dataset.output_dataset_metadata[-1],
                        metric_name=None,  # No evaluation for qualitative metrics
                        user_id=current_user_id,
                        storage_base_path="storage",
                        api_key=pipeline_row.model_api_key,
                        metric_value_id=metric_value.id,
                        tenant_id=tenant_id
                    )
                    print(f"Inference completed for qualitative metric value {metric_value.id}")

                    # Extract predictions from the output - just the raw keywords
                    predictions = output_data.get("predictions", [])

                    # Convert list to dict keyed by id for easier access
                    predictions_dict = {item.get('id', idx): item for idx, item in enumerate(predictions)}

                    # Store as dict instead of list
                    metric_value.output = convert_numpy_to_json_serializable(predictions_dict)

                    print(f"Stored {len(predictions_dict)} keyword predictions for qualitative metric")

                except Exception as e:
                    print(f"Inference failed for qualitative metric value {metric_value.id}: {str(e)}")
                    traceback.print_exc()
                    metric_value.output = convert_numpy_to_json_serializable({
                        "error": str(e)
                    })

                session.add(metric_value)
                session.flush()
                session.commit()

                results.append(OutputEvaluationItem(
                    audit_criteria_id=pipeline_row.audit_criteria_id,
                    output= metric_value.output,
                    target_features = "Qualitative Assessment",
                    threshold = effective_threshold,
                    requirements = 0
                ))
            # Quantitative metrics: run evaluation as normal
            else:
                # Get target feature object
                target_feature_obj = session.exec(
                    select(TargetFeatures).where(TargetFeatures.target_feature == pipeline_row.target_feature)
                ).first()

                try:
                    output_data = run_evaluation(
                        session,
                        model,
                        dataset.input_dataset_metadata[-1],
                        dataset.output_dataset_metadata[-1],
                        target_feature_obj.function_name if target_feature_obj else None,
                        current_user_id,
                        storage_base_path="storage",
                        api_key=pipeline_row.model_api_key,
                        metric_value_id=metric_value.id,
                        tenant_id=tenant_id
                    )
                    print(f"Evaluation completed for metric value {metric_value.id}")
                except Exception as e:
                    print(f"Evaluation failed for metric value {metric_value.id}: {str(e)}")
                    traceback.print_exc()
                    raise

                # Check if evaluation returned an error or actual results
                if "evaluation_result" in output_data:
                    metric_value.output = convert_numpy_to_json_serializable(output_data["evaluation_result"])
                elif "error" in output_data or "message" in output_data:
                    # Store error information
                    metric_value.output = convert_numpy_to_json_serializable(output_data)
                else:
                    # Fallback - store the entire output
                    metric_value.output = convert_numpy_to_json_serializable(output_data)

                session.add(metric_value)
                session.flush()
                session.commit()

                results.append(OutputEvaluationItem(
                    audit_criteria_id=pipeline_row.audit_criteria_id,
                    output= metric_value.output,
                    target_features = pipeline_row.target_feature,
                    threshold = effective_threshold,
                    requirements = 0
                ))

        else:
            # Already has output - return it
            results.append(OutputEvaluationItem(
                audit_criteria_id=pipeline_row.audit_criteria_id,
                output= metric_value.output,
                target_features = pipeline_row.target_feature if pipeline_row.target_feature else "Qualitative Assessment",
                threshold = effective_threshold,
                requirements = 0
            ))

    return OutputEvaluationResponse(
        audit_criteria=results
    )
