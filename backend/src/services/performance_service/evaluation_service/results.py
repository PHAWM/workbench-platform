"""Results retrieval service functions for evaluation"""
from typing import Any, Dict, List
from fastapi import HTTPException
from sqlmodel import Session, select, and_

from src.models import *
from src.core.enums import STATUS_TEXT_MAP, RECOMMENDATION_TEXT_MAP


def get_results_summary_comprehensive(
    audit_id: int,
    current_user_id: str,
    session: Session
) -> 'AuditEvaluationResponse':
    """
    Get comprehensive results summary for an audit with all event-metric pairs.

    This service function handles the entire business logic for retrieving results summary,
    including:
    - User audit access verification
    - Relevant user_audit_ids retrieval (current user + audit instigators)
    - Event-metric status retrieval with complex joins
    - Metric type detection (quantitative/qualitative/both)
    - Underlying features and scale points retrieval
    - Custom threshold handling
    - Model and dataset metadata retrieval
    - Response construction with evaluation status

    Args:
        audit_id: The ID of the audit
        current_user_id: The ID of the user requesting the summary
        session: Database session

    Returns:
        AuditEvaluationResponse with audit_criteria list and evaluation counts

    Raises:
        HTTPException: If user has no access to the audit
    """
    user_metric_check = session.exec(
        select(MappingAuditUser)
        .where(
            MappingAuditUser.audit_id == audit_id,
            MappingAuditUser.user_id == current_user_id
        )
    ).first()

    if not user_metric_check:
        raise HTTPException(status_code=401, detail="Access denied")

    # Get all relevant user_audit_ids (current user + audit instigators)
    relevant_user_audit_ids = session.exec(
        select(MappingAuditUser.id)
        .join(AuditRoles, MappingAuditUser.roles_id == AuditRoles.id)
        .where(
            MappingAuditUser.audit_id == audit_id,
            (MappingAuditUser.user_id == current_user_id) | (AuditRoles.id == 1)
        )
    ).all()

    # Get audit status with broader user_audit_id filtering
    base_status = session.exec(
        select(
            MappingEventsAuditStatus,
            Events,
            Metrics.name
        )
        .join(Events, MappingEventsAuditStatus.event_id == Events.id)
        .join(Metrics, MappingEventsAuditStatus.metric_id == Metrics.id)
        .where(
            MappingEventsAuditStatus.audit_id == audit_id,
            MappingEventsAuditStatus.user_audit_id.in_(relevant_user_audit_ids)
        )
        .order_by(Events.id)
    ).all()

    model_data = session.exec(
        select(
            Modelmetadata.id,
            DatasetMetadata.id
        )
        .join(MappingAuditModel, MappingAuditModel.model_id == Modelmetadata.id)
        .join(MappingAuditPipelineAudit, MappingAuditPipelineAudit.audit_id == MappingAuditModel.audit_id)
        .join(MappingModelDatasetAudit, MappingAuditPipelineAudit.audit_pipeline == MappingModelDatasetAudit.auditpipeline)
        .where(
            MappingAuditModel.audit_id == audit_id,
        )
    ).first()

    audit_criteria = []
    total_not_evaluated = 0

    for audit_status, event, metrics_name in base_status:
        # Check if metric is quantitative or qualitative
        quantitative_metric = session.exec(
            select(QuantitativeMetrics)
            .where(QuantitativeMetrics.metric_id == audit_status.metric_id)
        ).first()

        qualitative_metric = session.exec(
            select(QualitativeMetrics)
            .where(QualitativeMetrics.metric_id == audit_status.metric_id)
        ).first()

        metric_type = None
        if quantitative_metric and qualitative_metric:
            metric_type = "both"
        elif quantitative_metric:
            metric_type = "quantitative"
        elif qualitative_metric:
            metric_type = "qualitative"
        else:
            metric_type = "unclassified"

        # Updated values lookup to be more flexible
        values = session.exec(
            select(MetricsValues)
            .join(MappingMetricsEvents, MetricsValues.id == MappingMetricsEvents.values_id)
            .where(
                MappingMetricsEvents.metric_id == audit_status.metric_id,
                MappingMetricsEvents.event_id == audit_status.event_id,
                # Use broader user_audit_id filtering or remove this constraint
                MappingMetricsEvents.user_audit_id.in_(relevant_user_audit_ids)
            )
        ).all()

        for value in values:
            # Get underlying features for this metric value
            underlying_features_data = session.exec(
                select(MetricsUnderlyingFeatures, UnderlyingFeatures)
                .join(UnderlyingFeatures, MetricsUnderlyingFeatures.feature_id == UnderlyingFeatures.id)
                .where(MetricsUnderlyingFeatures.metric_values_id == value.id)
            ).all()

            underlying_features = [
                {
                    "id": feature.id,
                    "feature_name": feature.feature_name,
                    "ranges": mapping.ranges
                }
                for mapping, feature in underlying_features_data
            ]

            # Get target feature for this metric value
            target_feature = session.exec(
                select(TargetFeatures.target_feature)
                .join(MetricsTargetFeatures, TargetFeatures.id == MetricsTargetFeatures.target_feature_id)
                .where(MetricsTargetFeatures.metric_values_id == value.id)
            ).first()

            # Get scale points for this metric value
            scale_points_data = session.exec(
                select(MetricsScalePoints)
                .where(MetricsScalePoints.metric_values_id == value.id)
            ).first()

            scale_points = scale_points_data.scale_points if scale_points_data else None

            # Check for user-defined threshold
            custom_threshold_data = session.exec(
                select(UserMetricThresholds.custom_threshold)
                .where(
                    UserMetricThresholds.user_audit_id == user_metric_check.id,
                    UserMetricThresholds.metric_id == audit_status.metric_id,
                    UserMetricThresholds.event_id == audit_status.event_id,
                    UserMetricThresholds.values_id == value.id
                )
            ).first()

            # Use custom threshold if exists, otherwise use default from MetricsValues
            # If base threshold is "Not Set" (case-insensitive), check for any custom threshold
            base_threshold = value.threshold
            if custom_threshold_data is not None:
                effective_threshold = custom_threshold_data
            elif base_threshold and base_threshold.lower() == "not set":
                # Look for any custom threshold for this metric/event/values combination
                any_custom = session.exec(
                    select(UserMetricThresholds.custom_threshold).where(
                        UserMetricThresholds.metric_id == audit_status.metric_id,
                        UserMetricThresholds.event_id == audit_status.event_id,
                        UserMetricThresholds.values_id == value.id
                    )
                ).first()
                effective_threshold = any_custom if any_custom else base_threshold
            else:
                effective_threshold = base_threshold

            audit_criteria.append(
                AuditEvaluationStatus(
                    audit_criteria_id=audit_status.id,
                    event_id=audit_status.event_id,
                    event_name=event.name,
                    metric_id=audit_status.metric_id,
                    metric_name=metrics_name,
                    metric_type=metric_type,
                    threshold=effective_threshold,
                    output=value.output,
                    recommendation=audit_status.recommendation if audit_status.recommendation is not None else 0,
                    recommendation_text=RECOMMENDATION_TEXT_MAP.get(audit_status.recommendation, "Not Evaluated"),
                    status=audit_status.status if audit_status.status is not None else 0,
                    status_text=STATUS_TEXT_MAP.get(audit_status.status, "Not Started"),
                    notes=audit_status.notes,
                    underlying_features=underlying_features,
                    scale_points=scale_points,
                    target_feature=target_feature,
                )
            )

            if value.output == {} or value.output is None:
                total_not_evaluated += 1

    # Fetch output evaluation results for this audit
    output_evaluation_items = _get_output_evaluation_items(
        audit_id=audit_id,
        user_audit=user_metric_check,
        relevant_user_audit_ids=relevant_user_audit_ids,
        session=session
    )

    return AuditEvaluationResponse(
        audit_criteria=audit_criteria,
        total_criteria_evaluated=len(audit_criteria) - total_not_evaluated,
        total_criteria=len(audit_criteria),
        output_evaluation=output_evaluation_items,
        total_output_evaluated=len(output_evaluation_items),
    )


def _get_output_evaluation_items(
    audit_id: int,
    user_audit,
    relevant_user_audit_ids: list,
    session: Session
) -> list:
    """
    Fetch output evaluation items for an audit.
    Returns a list of dicts matching the OutputEvaluationItem shape.
    """
    # Get the audit instigator's user_audit_id (MappingEventsAuditStatus is created by instigator)
    audit_instigator = session.exec(
        select(MappingAuditUser.id)
        .join(AuditRoles, AuditRoles.id == MappingAuditUser.roles_id)
        .where(
            MappingAuditUser.audit_id == audit_id,
            AuditRoles.role == 'audit_instigator'
        )
    ).first()

    instigator_user_audit_id = audit_instigator if audit_instigator else user_audit.id
    print(user_audit)
    outcome_evaluations = session.exec(
        select(
            MappingOutcomeEvaluationValues,
            Events.name,
            Metrics.name,
            MappingEventsAuditStatus.id
        )
        .join(Events, MappingOutcomeEvaluationValues.event_id == Events.id)
        .join(Metrics, MappingOutcomeEvaluationValues.metric_id == Metrics.id)
        .join(MappingEventsAuditStatus, and_(
            MappingOutcomeEvaluationValues.event_id == MappingEventsAuditStatus.event_id,
            MappingOutcomeEvaluationValues.metric_id == MappingEventsAuditStatus.metric_id,
            MappingEventsAuditStatus.audit_id == audit_id,
            MappingEventsAuditStatus.user_audit_id == user_audit.id
        ))
        .where(
            MappingOutcomeEvaluationValues.audit_id == audit_id,
            MappingOutcomeEvaluationValues.user_audit_id == user_audit.id
        )
        .order_by(MappingOutcomeEvaluationValues.id)
    ).all()

    results = []
    for outcome_eval, event_name, metric_name, audit_criteria_id in outcome_evaluations:
        # Get target features for this metric
        target_feature = session.exec(
            select(TargetFeatures.target_feature)
            .join(MetricsTargetFeatures, TargetFeatures.id == MetricsTargetFeatures.target_feature_id)
            .join(MetricsValues, MetricsTargetFeatures.metric_values_id == MetricsValues.id)
            .join(MappingMetricsEvents, MetricsValues.id == MappingMetricsEvents.values_id)
            .where(
                MappingMetricsEvents.metric_id == outcome_eval.metric_id,
                MappingMetricsEvents.event_id == outcome_eval.event_id,
                MappingMetricsEvents.user_audit_id.in_(relevant_user_audit_ids)
            )
            .limit(1)
        ).first()

        # Get threshold (check for custom threshold first)
        custom_threshold = session.exec(
            select(UserMetricThresholds.custom_threshold)
            .where(
                UserMetricThresholds.user_audit_id == user_audit.id,
                UserMetricThresholds.metric_id == outcome_eval.metric_id,
                UserMetricThresholds.event_id == outcome_eval.event_id
            )
        ).first()

        if custom_threshold:
            threshold = custom_threshold
        else:
            default_threshold = session.exec(
                select(MetricsValues.threshold)
                .join(MappingMetricsEvents, MetricsValues.id == MappingMetricsEvents.values_id)
                .where(
                    MappingMetricsEvents.metric_id == outcome_eval.metric_id,
                    MappingMetricsEvents.event_id == outcome_eval.event_id,
                    MappingMetricsEvents.user_audit_id.in_(relevant_user_audit_ids)
                )
                .limit(1)
            ).first()

            if default_threshold and default_threshold.lower() == "not set":
                any_custom = session.exec(
                    select(UserMetricThresholds.custom_threshold).where(
                        UserMetricThresholds.metric_id == outcome_eval.metric_id,
                        UserMetricThresholds.event_id == outcome_eval.event_id
                    )
                ).first()
                threshold = any_custom if any_custom else default_threshold
            else:
                threshold = default_threshold if default_threshold else "N/A"

        # Get scale_points for qualitative metrics
        scale_points = session.exec(
            select(MetricsScalePoints.scale_points)
            .join(MetricsValues, MetricsScalePoints.metric_values_id == MetricsValues.id)
            .join(MappingMetricsEvents, MetricsValues.id == MappingMetricsEvents.values_id)
            .where(
                MappingMetricsEvents.metric_id == outcome_eval.metric_id,
                MappingMetricsEvents.event_id == outcome_eval.event_id,
                MappingMetricsEvents.user_audit_id.in_(relevant_user_audit_ids)
            )
            .limit(1)
        ).first()

        # Extract file information from output
        file_name = None
        file_index = None
        metadata = None

        if outcome_eval.output and isinstance(outcome_eval.output, dict):
            # Classification data is at top level (file_name, gender, age, id are direct keys)
            # The 'classification' key is a string value like "insecure", not a nested dict
            file_name = outcome_eval.output.get('file_name')
            metadata = {
                'gender': outcome_eval.output.get('gender'),
                'age': outcome_eval.output.get('age'),
                'id': outcome_eval.output.get('id'),
            }

            metadata = {k: v for k, v in metadata.items() if v is not None}
            if not metadata:
                metadata = None

            file_index = outcome_eval.output.get('file_index')

        results.append({
            "audit_criteria_id": audit_criteria_id,
            "output": outcome_eval.output if outcome_eval.output else {},
            "target_features": target_feature if target_feature else "N/A",
            "threshold": threshold,
            "requirements": outcome_eval.meet_requirement if outcome_eval.meet_requirement is not None else 0,
            "notes": outcome_eval.notes,
            "data_id": outcome_eval.data_id,
            "file_name": file_name,
            "file_index": file_index,
            "metadata": metadata,
            "scale_points": scale_points if scale_points else None,
        })

    return results


def get_output_evaluation_summary_comprehensive(
    audit_id: int,
    current_user_id: str,
    session: Session
) -> 'OutputEvaluationResponse':
    """
    Get summary of output evaluation results for an audit.

    This service function handles the entire business logic for retrieving output evaluation summary,
    including:
    - User audit access verification
    - Relevant user_audit_ids retrieval
    - MappingOutcomeEvaluationValues retrieval with complex joins
    - Target features retrieval
    - Custom threshold handling
    - Scale points retrieval for qualitative metrics
    - File information and metadata extraction
    - Response construction

    Args:
        audit_id: The ID of the audit
        current_user_id: The ID of the user requesting the summary
        session: Database session

    Returns:
        OutputEvaluationResponse with audit_criteria list of OutputEvaluationItem

    Raises:
        HTTPException: If user has no access to the audit
    """
    user_metric_check = session.exec(
        select(MappingAuditUser)
        .where(
            MappingAuditUser.audit_id == audit_id,
            MappingAuditUser.user_id == current_user_id
        )
    ).first()

    if not user_metric_check:
        raise HTTPException(status_code=401, detail="Access denied")

    # Get all relevant user_audit_ids (current user + audit instigators)
    relevant_user_audit_ids = session.exec(
        select(MappingAuditUser.id)
        .join(AuditRoles, MappingAuditUser.roles_id == AuditRoles.id)
        .where(
            MappingAuditUser.audit_id == audit_id,
            MappingAuditUser.user_id == current_user_id
        )
    ).all()

    # Get all MappingOutcomeEvaluationValues with related data
    outcome_evaluations = session.exec(
        select(
            MappingOutcomeEvaluationValues,
            Events.name,
            Metrics.name,
            MappingEventsAuditStatus.id
        )
        .join(Events, MappingOutcomeEvaluationValues.event_id == Events.id)
        .join(Metrics, MappingOutcomeEvaluationValues.metric_id == Metrics.id)
        .join(MappingEventsAuditStatus, and_(
            MappingOutcomeEvaluationValues.event_id == MappingEventsAuditStatus.event_id,
            MappingOutcomeEvaluationValues.metric_id == MappingEventsAuditStatus.metric_id,
            MappingOutcomeEvaluationValues.user_audit_id == MappingEventsAuditStatus.user_audit_id
        ))
        .where(
            MappingOutcomeEvaluationValues.audit_id == audit_id,
            MappingOutcomeEvaluationValues.user_audit_id.in_(relevant_user_audit_ids)
        )
        .order_by(MappingOutcomeEvaluationValues.id)
    ).all()

    results = []
    for outcome_eval, event_name, metric_name, audit_criteria_id in outcome_evaluations:
        # Get target features for this metric
        target_feature = session.exec(
            select(TargetFeatures.target_feature)
            .join(MetricsTargetFeatures, TargetFeatures.id == MetricsTargetFeatures.target_feature_id)
            .join(MetricsValues, MetricsTargetFeatures.metric_values_id == MetricsValues.id)
            .join(MappingMetricsEvents, MetricsValues.id == MappingMetricsEvents.values_id)
            .where(
                MappingMetricsEvents.metric_id == outcome_eval.metric_id,
                MappingMetricsEvents.event_id == outcome_eval.event_id,
                MappingMetricsEvents.user_audit_id.in_(relevant_user_audit_ids)
            )
            .limit(1)
        ).first()

        # Get threshold (check for custom threshold first)
        custom_threshold = session.exec(
            select(UserMetricThresholds.custom_threshold)
            .where(
                UserMetricThresholds.user_audit_id == user_metric_check.id,
                UserMetricThresholds.metric_id == outcome_eval.metric_id,
                UserMetricThresholds.event_id == outcome_eval.event_id
            )
        ).first()

        if custom_threshold:
            threshold = custom_threshold
        else:
            # Get default threshold from MetricsValues
            default_threshold = session.exec(
                select(MetricsValues.threshold)
                .join(MappingMetricsEvents, MetricsValues.id == MappingMetricsEvents.values_id)
                .where(
                    MappingMetricsEvents.metric_id == outcome_eval.metric_id,
                    MappingMetricsEvents.event_id == outcome_eval.event_id,
                    MappingMetricsEvents.user_audit_id.in_(relevant_user_audit_ids)
                )
                .limit(1)
            ).first()

            # If base threshold is "Not Set" (case-insensitive), check for any custom threshold
            if default_threshold and default_threshold.lower() == "not set":
                any_custom = session.exec(
                    select(UserMetricThresholds.custom_threshold).where(
                        UserMetricThresholds.metric_id == outcome_eval.metric_id,
                        UserMetricThresholds.event_id == outcome_eval.event_id
                    )
                ).first()
                threshold = any_custom if any_custom else default_threshold
            else:
                threshold = default_threshold if default_threshold else "N/A"

        # Get scale_points for qualitative metrics
        scale_points = session.exec(
            select(MetricsScalePoints.scale_points)
            .join(MetricsValues, MetricsScalePoints.metric_values_id == MetricsValues.id)
            .join(MappingMetricsEvents, MetricsValues.id == MappingMetricsEvents.values_id)
            .where(
                MappingMetricsEvents.metric_id == outcome_eval.metric_id,
                MappingMetricsEvents.event_id == outcome_eval.event_id,
                MappingMetricsEvents.user_audit_id.in_(relevant_user_audit_ids)
            )
            .limit(1)
        ).first()

        # Extract file information from output
        file_name = None
        file_index = None
        metadata = None

        if outcome_eval.output and isinstance(outcome_eval.output, dict):
            # Classification data is at top level (file_name, gender, age, id are direct keys)
            # The 'classification' key is a string value like "insecure", not a nested dict
            file_name = outcome_eval.output.get('file_name')
            metadata = {
                'gender': outcome_eval.output.get('gender'),
                'age': outcome_eval.output.get('age'),
                'id': outcome_eval.output.get('id'),
            }

            # Remove None values
            metadata = {k: v for k, v in metadata.items() if v is not None}
            if not metadata:
                metadata = None

            file_index = outcome_eval.output.get('file_index')

        results.append(
            OutputEvaluationItem(
                audit_criteria_id=audit_criteria_id,
                output=outcome_eval.output if outcome_eval.output else {},
                target_features=target_feature if target_feature else "N/A",
                threshold=threshold,
                requirements=outcome_eval.meet_requirement if outcome_eval.meet_requirement is not None else 0,
                notes=outcome_eval.notes,
                data_id=outcome_eval.data_id,
                file_name=file_name,
                file_index=file_index,
                metadata=metadata,
                scale_points=scale_points if scale_points else None
            )
        )

    return OutputEvaluationResponse(
        audit_criteria=results
    )
