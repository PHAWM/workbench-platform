"""Metric read/retrieval service functions"""
from typing import List, Dict, Any, Optional
from fastapi import HTTPException
from sqlmodel import Session, select

from src.models import *


def get_metric_by_id(metric_id: int, session: Session):
    """Get a metric by ID"""
    metric = session.get(Metrics, metric_id)
    if not metric:
        raise HTTPException(status_code=404, detail="Metric not found")
    return metric


def list_metrics(session: Session, skip: int = 0, limit: int = 100) -> List[Metrics]:
    """List all metrics with pagination"""
    statement = select(Metrics).offset(skip).limit(limit)
    metrics = session.exec(statement).all()
    return metrics


def get_metrics_by_audit(audit_id: int, session: Session) -> List[Metrics]:
    """Get all metrics associated with a specific audit"""
    # Get metrics through event mappings
    statement = (
        select(Metrics)
        .join(MappingMetricsEvents, Metrics.id == MappingMetricsEvents.metric_id)
        .join(Events, MappingMetricsEvents.event_id == Events.id)
        .join(MappingEventsAuditStatus, Events.id == MappingEventsAuditStatus.event_id)
        .where(MappingEventsAuditStatus.audit_id == audit_id)
        .distinct()
    )
    metrics = session.exec(statement).all()
    return metrics


def get_metric_detailed_with_context(
    metric_id: int,
    current_user_id: str,
    session: Session
) -> 'SingleMetricDetailResponse':
    """
    Get detailed metric information with effective thresholds and full context.

    This service function handles the entire business logic for retrieving a metric's details,
    including:
    - User access verification
    - Metric type detection (quantitative/qualitative)
    - Associated events retrieval with user filtering
    - Metric values with effective threshold calculation
    - Feature data extraction (underlying, target, scale points)
    - Response construction with all details

    Args:
        metric_id: The ID of the metric to retrieve
        current_user_id: The ID of the user requesting the metric
        session: Database session

    Returns:
        SingleMetricDetailResponse with complete metric information

    Raises:
        HTTPException: If user has no access or metric not found
    """
    from .utils import get_effective_threshold, get_metric_value_details

    # Verify user access
    user_metric_check = session.exec(
        select(MappingUserMetrics)
        .join(MappingAuditUser, MappingAuditUser.id == MappingUserMetrics.user_audit_id)
        .where(
            MappingUserMetrics.metric_id == metric_id,
            MappingAuditUser.user_id == current_user_id
        )
    ).first()

    if not user_metric_check:
        raise HTTPException(status_code=404, detail="Metric not found or access denied")

    user_audit_id = user_metric_check.user_audit_id

    # Get metric with type details
    statement = (
        select(
            Metrics,
            QuantitativeMetrics.id.label("quant_id"),
            QuantitativeMetrics.formula,
            QualitativeMetrics.id.label("qual_id"),
            QualitativeMetrics.definition
        )
        .outerjoin(QuantitativeMetrics, Metrics.id == QuantitativeMetrics.metric_id)
        .outerjoin(QualitativeMetrics, Metrics.id == QualitativeMetrics.metric_id)
        .where(Metrics.id == metric_id)
    )

    result = session.exec(statement).first()
    if not result:
        raise HTTPException(status_code=404, detail=f"Metric with ID {metric_id} not found")

    metric, quant_id, formula, qual_id, definition = result

    # Get associated events
    events_statement = (
        select(Events)
        .join(MappingMetricsEvents, Events.id == MappingMetricsEvents.event_id)
        .join(MappingAuditUser, MappingAuditUser.id == MappingMetricsEvents.user_audit_id)
        .where(
            MappingMetricsEvents.metric_id == metric_id,
            MappingAuditUser.user_id == current_user_id
        )
    )
    events = session.exec(events_statement).all()

    associated_events = [
        MetricEventsDetail(
            event_id=event.id,
            event_description=event.description,
            event_cause=event.cause,
            event_reason=event.reason,
            event_name=event.name,
            likelihood=event.likelihood,
            magnitude=event.magnitude,
            valence=event.valence
        )
        for event in events
    ]

    # Get metric values with effective thresholds
    values_statement = (
        select(MetricsValues, MappingMetricsEvents)
        .join(MappingMetricsEvents, MetricsValues.id == MappingMetricsEvents.values_id)
        .join(MappingAuditUser, MappingAuditUser.id == MappingMetricsEvents.user_audit_id)
        .where(
            MappingMetricsEvents.metric_id == metric_id,
            MappingAuditUser.user_id == current_user_id
        )
    )
    values = session.exec(values_statement).all()

    metric_values = []
    for value, mapping in values:
        # Get effective threshold (custom or default)
        effective_threshold, is_customised = get_effective_threshold(
            session, user_audit_id, metric_id, mapping.event_id, value.id
        )

        underlying_features, target_features, scale_points = get_metric_value_details(session, value.id)

        underlying_features_list = []
        if underlying_features:
            underlying_features_list = [
                {
                    'feature_id': f.feature_id,
                    'ranges': f.ranges
                } for f in underlying_features
            ]

        target_features_list = []
        if target_features:
            target_features_list = [
                {
                    'feature_id': f.target_feature_id
                } for f in target_features
            ]

        scale_points_data = scale_points.scale_points if scale_points else None
        metric_values.append(MetricValuesDetail(
            id=value.id,
            event_id=mapping.event_id,
            output=value.output,
            threshold=effective_threshold,
            underlying_features=underlying_features_list,
            target_features=target_features_list,
            scale_points=scale_points_data,
            is_threshold_customised=is_customised
        ))

    # Determine metric type
    if quant_id:
        metric_type = "quantitative"
    elif qual_id:
        metric_type = "qualitative"
    else:
        metric_type = "unclassified"

    return SingleMetricDetailResponse(
        id=metric.id,
        name=getattr(metric, 'name', metric.description),
        description=metric.description,
        reason=metric.reason,
        metric_type=metric_type,
        is_quantitative=bool(quant_id),
        is_qualitative=bool(qual_id),
        quantitative_details=QuantitativeMetricDetail(
            id=quant_id,
            metric_id=metric_id,
            formula=formula
        ) if quant_id else None,
        qualitative_details=QualitativeMetricDetail(
            id=qual_id,
            metric_id=metric_id,
            definition=definition
        ) if qual_id else None,
        associated_events=associated_events,
        metric_values=metric_values,
        total_events=len(associated_events),
        total_values=len(metric_values)
    )


def list_metrics_by_audit_detailed(
    audit_id: int,
    current_user_id: str,
    session: Session,
    skip: int = 0,
    limit: int = 100
) -> 'MetricListResponse':
    """
    Get all metrics for an audit with creator information and detailed metadata.

    This service function handles the entire business logic for listing metrics by audit,
    including:
    - User audit access verification
    - Complex aggregation queries (COUNT, GROUP BY)
    - Access control filtering (current user OR audit instigator)
    - Pagination logic
    - Role-based checks
    - Effective threshold calculation (user custom threshold or default)
    - Response transformation

    Args:
        audit_id: The ID of the audit
        current_user_id: The ID of the user requesting the list
        session: Database session
        skip: Number of records to skip for pagination
        limit: Maximum number of records to return

    Returns:
        MetricListResponse with paginated metric list

    Raises:
        HTTPException: If user has no access to the audit
    """
    from sqlalchemy import func, and_, or_
    from .utils import get_effective_threshold

    # Verify user has access to this audit
    user_audit_mapping = session.exec(
        select(MappingAuditUser).where(
            MappingAuditUser.audit_id == audit_id,
            MappingAuditUser.user_id == current_user_id
        )
    ).first()

    if not user_audit_mapping:
        raise HTTPException(status_code=403, detail="Access denied to this audit")

    # Main query with JOINs to get all needed data
    # CRITICAL: Use MappingUserMetrics to check who CREATED the metric
    # This ensures Auditor A doesn't see Auditor B's metrics
    statement = (
        select(
            Metrics,
            QuantitativeMetrics.formula,
            QualitativeMetrics.definition,
            func.count(MappingMetricsEvents.event_id.distinct()).label("total_events"),
            func.count(MappingMetricsEvents.values_id.distinct()).label("total_values"),
            AuditRoles.id.label("role_id")  # Include role to determine if audit instigator
        )
        .outerjoin(QuantitativeMetrics, Metrics.id == QuantitativeMetrics.metric_id)
        .outerjoin(QualitativeMetrics, Metrics.id == QualitativeMetrics.metric_id)
        .join(MappingUserMetrics, Metrics.id == MappingUserMetrics.metric_id)
        .join(MappingAuditUser, MappingUserMetrics.user_audit_id == MappingAuditUser.id)
        .join(AuditRoles, MappingAuditUser.roles_id == AuditRoles.id)
        .outerjoin(MappingMetricsEvents, Metrics.id == MappingMetricsEvents.metric_id)
        .where(
            and_(
                MappingAuditUser.audit_id == audit_id,
                # Show metrics created by current user OR by audit instigator (role_id 1)
                or_(
                    MappingAuditUser.user_id == current_user_id,
                    AuditRoles.id == 1  # audit_instigator role
                )
            )
        )
        .group_by(
            Metrics.id,
            QuantitativeMetrics.formula,
            QualitativeMetrics.definition,
            AuditRoles.id  # Include in GROUP BY
        )
        .offset(skip)
        .limit(limit)
    )

    results = session.exec(statement).all()

    # Get total count for pagination
    # CRITICAL: Use MappingUserMetrics for consistency with main query
    count_statement = (
        select(func.count(Metrics.id.distinct()))
        .join(MappingUserMetrics, Metrics.id == MappingUserMetrics.metric_id)
        .join(MappingAuditUser, MappingUserMetrics.user_audit_id == MappingAuditUser.id)
        .join(AuditRoles, MappingAuditUser.roles_id == AuditRoles.id)
        .where(
            and_(
                MappingAuditUser.audit_id == audit_id,
                or_(
                    MappingAuditUser.user_id == current_user_id,
                    AuditRoles.id == 1  # audit_instigator role
                )
            )
        )
    )
    total_count = session.exec(count_statement).first()

    # Transform results into response models
    metrics_detailed = []
    for result in results:
        metric, formula, definition, total_events, total_values, role_id = result

        # Determine metric type
        if formula:
            metric_type = "quantitative"
        elif definition:
            metric_type = "qualitative"
        else:
            metric_type = "unclassified"

        # Determine if user is audit instigator based on role_id from the query
        is_audit_instigator = (role_id == 1)

        # Handle created_at if it exists in Metrics model
        created_at_str = None
        if hasattr(metric, 'created_at') and metric.created_at:
            created_at_str = metric.created_at.isoformat()

        # Check if metric is user-defined for this specific user
        user_defined_check = session.exec(
            select(MappingUserMetrics)
            .where(
                MappingUserMetrics.metric_id == metric.id,
                MappingUserMetrics.user_audit_id == user_audit_mapping.id
            )
        ).first()

        is_user_defined = bool(user_defined_check)

        # Handle created_by_user_id if it exists in Metrics model
        created_by_user_id = None
        if hasattr(metric, 'created_by_user_id'):
            created_by_user_id = metric.created_by_user_id

        # Get effective threshold for this metric
        # Find metric-event mapping for this audit context
        # First try to find a mapping for the current user, then fall back to audit instigator
        metric_mapping = session.exec(
            select(MappingMetricsEvents)
            .join(MappingAuditUser, MappingMetricsEvents.user_audit_id == MappingAuditUser.id)
            .where(
                MappingMetricsEvents.metric_id == metric.id,
                MappingAuditUser.audit_id == audit_id
            )
        ).first()

        effective_threshold = None
        is_threshold_customised = False

        if metric_mapping and metric_mapping.values_id:
            # Get effective threshold (user's custom threshold if exists, otherwise default)
            effective_threshold, is_threshold_customised = get_effective_threshold(
                session,
                user_audit_mapping.id,
                metric.id,
                metric_mapping.event_id,
                metric_mapping.values_id
            )

        metrics_detailed.append(MetricDetailedListItem(
            id=metric.id,
            name=metric.name,
            description=metric.description,
            reason=metric.reason,
            metric_type=metric_type,
            is_user_defined=is_user_defined,
            is_audit_instigator=is_audit_instigator,
            created_by_user_id=created_by_user_id,
            created_by_username=None,
            created_at=created_at_str,
            formula=formula,
            definition=definition,
            threshold=effective_threshold,
            is_threshold_customised=is_threshold_customised,
            total_events=total_events or 0,
            total_values=total_values or 0
        ))

    # Pagination info
    page = (skip // limit) + 1
    has_next = total_count > skip + limit
    has_previous = skip > 0

    return MetricListResponse(
        metrics=metrics_detailed,
        total_count=total_count,
        page=page,
        page_size=limit,
        has_next=has_next,
        has_previous=has_previous
    )


def get_dataset_features_for_audit_with_context(
    audit_id: int,
    current_user_id: str,
    session: Session
) -> Dict[str, Any]:
    """
    Get all available underlying features for an audit's dataset.

    This service function handles the entire business logic for retrieving dataset features,
    including:
    - User audit access verification
    - Dataset ID retrieval for the audit
    - Feature mappings query
    - Feature details extraction
    - Dataset metadata retrieval
    - Response construction

    Args:
        audit_id: The ID of the audit
        current_user_id: The ID of the user requesting the features
        session: Database session

    Returns:
        Dictionary containing audit_id, dataset_id, dataset_purpose, available_features, and total_features

    Raises:
        HTTPException: If user has no access to the audit or no dataset found
    """
    from .utils import get_dataset_for_audit

    # Verify user has access to this audit
    user_audit = session.exec(
        select(MappingAuditUser).where(
            MappingAuditUser.audit_id == audit_id,
            MappingAuditUser.user_id == current_user_id
        )
    ).first()

    if not user_audit:
        raise HTTPException(status_code=403, detail="User has no access to this audit")

    # Get the dataset for this audit
    dataset_id = get_dataset_for_audit(session, audit_id)

    if not dataset_id:
        raise HTTPException(
            status_code=404,
            detail="No dataset found for this audit. Please configure the audit pipeline with a dataset."
        )

    # Get all features mapped to this dataset
    feature_mappings = session.exec(
        select(MappingDatasetFeatures).where(
            MappingDatasetFeatures.dataset_metadata_id == dataset_id
        )
    ).all()

    # Get the full feature details
    features = []
    for mapping in feature_mappings:
        feature = session.get(UnderlyingFeatures, mapping.underlying_feature_id)
        if feature:
            features.append({
                "id": feature.id,
                "feature_name": feature.feature_name
            })

    # Get dataset info
    dataset = session.get(DatasetMetadata, dataset_id)

    return {
        "audit_id": audit_id,
        "dataset_id": dataset_id,
        "dataset_purpose": dataset.purpose if dataset else None,
        "available_features": features,
        "total_features": len(features)
    }


def get_metric_value_underlying_features_with_context(
    value_id: int,
    current_user_id: str,
    session: Session
) -> List[Dict[str, Any]]:
    """
    Get underlying features for a specific metric value.

    This service function handles:
    - User access verification
    - Underlying features retrieval
    - Response construction

    Args:
        value_id: The ID of the metric value
        current_user_id: The ID of the user requesting the features
        session: Database session

    Returns:
        List of underlying features with id, feature_id, and ranges

    Raises:
        HTTPException: If user has no access to the metric value
    """
    # Verify user has access to this metric value
    user_metric_check = session.exec(
        select(MappingUserMetrics)
        .join(MappingAuditUser, MappingAuditUser.id == MappingUserMetrics.user_audit_id)
        .join(MappingMetricsEvents, MappingUserMetrics.metric_id == MappingMetricsEvents.metric_id)
        .where(
            MappingMetricsEvents.values_id == value_id,
            MappingAuditUser.user_id == current_user_id
        )
    ).first()

    if not user_metric_check:
        raise HTTPException(status_code=404, detail="Metric value not found or access denied")

    underlying_features = session.exec(
        select(MetricsUnderlyingFeatures)
        .where(MetricsUnderlyingFeatures.metric_values_id == value_id)
    ).all()

    return [
        {
            'id': f.id,
            'feature_id': f.feature_id,
            'ranges': f.ranges
        } for f in underlying_features
    ]


def get_metric_value_target_features_with_context(
    value_id: int,
    current_user_id: str,
    session: Session
) -> List[Dict[str, Any]]:
    """
    Get target features for a specific metric value.

    This service function handles:
    - User access verification
    - Target features retrieval
    - Response construction

    Args:
        value_id: The ID of the metric value
        current_user_id: The ID of the user requesting the features
        session: Database session

    Returns:
        List of target features with id and target_feature_id

    Raises:
        HTTPException: If user has no access to the metric value
    """
    # Verify user has access to this metric value
    user_metric_check = session.exec(
        select(MappingUserMetrics)
        .join(MappingAuditUser, MappingAuditUser.id == MappingUserMetrics.user_audit_id)
        .join(MappingMetricsEvents, MappingUserMetrics.metric_id == MappingMetricsEvents.metric_id)
        .where(
            MappingMetricsEvents.values_id == value_id,
            MappingAuditUser.user_id == current_user_id
        )
    ).first()

    if not user_metric_check:
        raise HTTPException(status_code=404, detail="Metric value not found or access denied")

    target_features = session.exec(
        select(MetricsTargetFeatures)
        .where(MetricsTargetFeatures.metric_values_id == value_id)
    ).all()

    return [
        {
            'id': f.id,
            'target_feature_id': f.target_feature_id
        } for f in target_features
    ]


def get_metric_value_scale_points_with_context(
    value_id: int,
    current_user_id: str,
    session: Session
) -> Dict[str, Any]:
    """
    Get scale points for a specific metric value.

    This service function handles:
    - User access verification
    - Scale points retrieval
    - Response construction

    Args:
        value_id: The ID of the metric value
        current_user_id: The ID of the user requesting the scale points
        session: Database session

    Returns:
        Dictionary with id and scale_points, or empty dict if no scale points

    Raises:
        HTTPException: If user has no access to the metric value
    """
    # Verify user has access to this metric value
    user_metric_check = session.exec(
        select(MappingUserMetrics)
        .join(MappingAuditUser, MappingAuditUser.id == MappingUserMetrics.user_audit_id)
        .join(MappingMetricsEvents, MappingUserMetrics.metric_id == MappingMetricsEvents.metric_id)
        .where(
            MappingMetricsEvents.values_id == value_id,
            MappingAuditUser.user_id == current_user_id
        )
    ).first()

    if not user_metric_check:
        raise HTTPException(status_code=404, detail="Metric value not found or access denied")

    scale_points = session.exec(
        select(MetricsScalePoints)
        .where(MetricsScalePoints.metric_values_id == value_id)
    ).first()

    if not scale_points:
        return {}

    return {
        'id': scale_points.id,
        'scale_points': scale_points.scale_points
    }


def get_metric_value_all_features_with_context(
    value_id: int,
    current_user_id: str,
    session: Session
) -> Dict[str, Any]:
    """
    Get all features (underlying, target, and scale points) for a specific metric value.

    This service function handles:
    - User access verification
    - All features retrieval (underlying, target, scale points)
    - Response construction

    Args:
        value_id: The ID of the metric value
        current_user_id: The ID of the user requesting the features
        session: Database session

    Returns:
        Dictionary with value_id, underlying_features, target_features, and scale_points

    Raises:
        HTTPException: If user has no access to the metric value
    """
    from .utils import get_metric_value_details

    # Verify user has access to this metric value
    user_metric_check = session.exec(
        select(MappingUserMetrics)
        .join(MappingAuditUser, MappingAuditUser.id == MappingUserMetrics.user_audit_id)
        .join(MappingMetricsEvents, MappingUserMetrics.metric_id == MappingMetricsEvents.metric_id)
        .where(
            MappingMetricsEvents.values_id == value_id,
            MappingAuditUser.user_id == current_user_id
        )
    ).first()

    if not user_metric_check:
        raise HTTPException(status_code=404, detail="Metric value not found or access denied")

    underlying_features, target_features, scale_points = get_metric_value_details(session, value_id)

    underlying_features_list = [
        {
            'id': f.id,
            'feature_id': f.feature_id,
            'ranges': f.ranges
        } for f in underlying_features
    ] if underlying_features else []

    target_features_list = [
        {
            'id': f.id,
            'target_feature_id': f.target_feature_id
        } for f in target_features
    ] if target_features else []

    scale_points_data = {
        'id': scale_points.id,
        'scale_points': scale_points.scale_points
    } if scale_points else {}

    return {
        'value_id': value_id,
        'underlying_features': underlying_features_list,
        'target_features': target_features_list,
        'scale_points': scale_points_data
    }


def get_effective_threshold_with_context(
    metric_id: int,
    event_id: int,
    current_user_id: str,
    session: Session
) -> Dict[str, Any]:
    """
    Get the effective threshold for a metric-event combination.

    This service function handles:
    - User audit access verification
    - Metric-event mapping retrieval
    - Effective threshold calculation (custom or default)
    - Response construction

    Args:
        metric_id: The ID of the metric
        event_id: The ID of the event
        current_user_id: The ID of the user requesting the threshold
        session: Database session

    Returns:
        Dictionary with metric_id, event_id, values_id, effective_threshold, is_customised, and user_audit_id

    Raises:
        HTTPException: If user has no access or mapping not found
    """
    from .utils import get_effective_threshold

    # Get user_audit_id for the current user
    user_audit_mapping = session.exec(
        select(MappingAuditUser).where(
            MappingAuditUser.user_id == current_user_id
        )
    ).first()

    if not user_audit_mapping:
        raise HTTPException(status_code=403, detail="User audit mapping not found")

    # Get the metric-event mapping to find values_id
    mapping = session.exec(
        select(MappingMetricsEvents).where(
            MappingMetricsEvents.event_id == event_id,
            MappingMetricsEvents.metric_id == metric_id,
            MappingMetricsEvents.user_audit_id == user_audit_mapping.id
        )
    ).first()

    if not mapping:
        raise HTTPException(status_code=404, detail="Metric-event mapping not found")

    # Get effective threshold
    effective_threshold, is_customised = get_effective_threshold(
        session, user_audit_mapping.id, metric_id, event_id, mapping.values_id
    )

    return {
        "metric_id": metric_id,
        "event_id": event_id,
        "values_id": mapping.values_id,
        "effective_threshold": effective_threshold,
        "is_customised": is_customised,
        "user_audit_id": user_audit_mapping.id
    }
