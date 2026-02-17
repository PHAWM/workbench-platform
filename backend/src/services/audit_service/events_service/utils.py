"""Event utility and helper functions"""
from typing import Dict, Tuple, List, Any, Optional
from sqlmodel import Session, select
from sqlalchemy import or_

from src.models import *


def get_effective_event_values(session: Session, user_audit_id: int, event_id: int) -> Tuple[Dict, bool]:
    """
    Get the effective event values and whether they're customised.

    Returns:
        Tuple of (values_dict, is_customised)
        - values_dict: Dictionary with likelihood, magnitude, valence
        - is_customised: Boolean indicating if values are customised for this user
    """
    # Get base event
    base_event = session.get(Events, event_id)
    if not base_event:
        return None, False

    # Check if user is the original creator of the event in this audit context
    event_creator_check = session.exec(
        select(EventType).where(
            EventType.event_id == event_id,
            EventType.created_by_user_id == user_audit_id
        )
    ).first()

    # If user is the creator in the same audit context, return base values (no customisation needed)
    if event_creator_check:
        return {
            'likelihood': base_event.likelihood,
            'magnitude': base_event.magnitude,
            'valence': base_event.valence
        }, False

    # Check for user customisations (different user or different audit)
    customisation = session.exec(
        select(UserEventCustomisations).where(
            UserEventCustomisations.user_audit_id == user_audit_id,
            UserEventCustomisations.event_id == event_id
        )
    ).first()

    if customisation:
        return {
            'likelihood': customisation.custom_likelihood if customisation.custom_likelihood is not None else base_event.likelihood,
            'magnitude': customisation.custom_magnitude if customisation.custom_magnitude is not None else base_event.magnitude,
            'valence': customisation.custom_valence if customisation.custom_valence is not None else base_event.valence
        }, True

    # No customisation, return base values
    return {
        'likelihood': base_event.likelihood,
        'magnitude': base_event.magnitude,
        'valence': base_event.valence
    }, False


def apply_filters_to_query(query, filters: Dict[str, Any]):
    """Apply filters to the events query - only audit_id and user_id"""

    if filters.get("audit_id"):
        query = query.join(MappingEventsAuditStatus).where(
            MappingEventsAuditStatus.audit_id == filters["audit_id"]
        )

    if filters.get("user_id"):
        query = query.join(MappingUserEvents).join(MappingAuditUser).where(
            MappingAuditUser.user_id == filters["user_id"]
        )

    return query


def determine_risk_level(likelihood: float, magnitude: float) -> str:
    """Determine risk level based on likelihood and magnitude"""
    risk_score = likelihood * magnitude
    if risk_score >= 0.7:
        return "high"
    elif risk_score >= 0.4:
        return "medium"
    else:
        return "low"


def determine_impact_type(valence: float) -> str:
    """Determine impact type based on valence"""
    if valence > 0.1:
        return "positive"
    elif valence < -0.1:
        return "negative"
    else:
        return "neutral"


def get_audit_status_text(status: int) -> str:
    """Convert audit status number to text"""
    return {0: "Not Started", 1: "In Progress", 2: "Finished"}.get(status, "Unknown")


def apply_sorting(query, sort_by, sort_order):
    """Apply sorting to the events query"""
    # Import the enums here to avoid circular imports
    from src.api.routes.events import SortBy, SortOrder

    if sort_by == SortBy.likelihood:
        order_column = Events.likelihood
    elif sort_by == SortBy.magnitude:
        order_column = Events.magnitude
    elif sort_by == SortBy.valence:
        order_column = Events.valence
    else:  # Default to likelihood
        order_column = Events.likelihood

    if sort_order == SortOrder.desc:
        query = query.order_by(order_column.desc())
    else:
        query = query.order_by(order_column.asc())

    return query


def get_user_audit_ids(session: Session, user_id: int) -> List[int]:
    """Get all audit IDs associated with the current user"""
    statement = select(MappingAuditUser.id).where(MappingAuditUser.user_id == user_id)
    audit_ids = session.exec(statement).all()
    return audit_ids


def get_event_metrics_with_values(
    event_id: int,
    session: Session,
    audit_id: Optional[int] = None,
    user_audit_id: Optional[int] = None,
    current_user_id: Optional[str] = None
) -> List[Any]:
    """
    Enhanced version that considers effective metric thresholds and event values.

    IMPORTANT: Filters metrics by audit context to ensure proper data isolation.
    Only shows metrics from audit instigator (role_id=1) and current user.
    """
    # Import here to avoid circular import
    from src.api.routes.metrics import get_effective_threshold
    from src.api.routes.events import EventMetricSummary

    # Get metrics mappings for this event
    # CRITICAL: Only show metrics from audit instigator (role_id=1) and current user
    metrics_mappings_query = select(
        MappingMetricsEvents,
        AuditRoles.id.label("role_id"),
        MappingAuditUser.user_id.label("metric_user_id")
    ).join(MappingAuditUser, MappingMetricsEvents.user_audit_id == MappingAuditUser.id
    ).join(AuditRoles, MappingAuditUser.roles_id == AuditRoles.id
    ).where(MappingMetricsEvents.event_id == event_id)

    # CRITICAL: Filter by audit_id to prevent cross-audit data leakage
    # Only include metrics from the specified audit
    if audit_id is not None:
        metrics_mappings_query = metrics_mappings_query.where(
            MappingAuditUser.audit_id == audit_id
        )

    # CRITICAL: Only show metrics from audit instigator OR current user
    # This prevents seeing metrics from other auditors
    if current_user_id is not None:
        metrics_mappings_query = metrics_mappings_query.where(
            or_(
                AuditRoles.id == 1,  # Audit instigator
                MappingAuditUser.user_id == current_user_id  # Current user
            )
        )

    metrics_mappings_results = session.exec(metrics_mappings_query).all()

    if not metrics_mappings_results:
        return []

    # Extract mappings and role information
    metrics_mappings = []
    audit_instigator_mappings = set()

    for mapping, role_id, metric_user_id in metrics_mappings_results:
        metrics_mappings.append(mapping)
        # Role id 1 is audit_instigator
        if role_id == 1:
            audit_instigator_mappings.add(mapping.metric_id)

    metric_ids = [m.metric_id for m in metrics_mappings]
    values_ids = [m.values_id for m in metrics_mappings if m.values_id]

    # Get user-defined metrics using MappingUserMetrics
    user_defined_mappings = set()
    if user_audit_id:
        user_defined_results = session.exec(
            select(MappingUserMetrics.metric_id)
            .where(MappingUserMetrics.user_audit_id == user_audit_id)
            .where(MappingUserMetrics.metric_id.in_(metric_ids))
        ).all()
        user_defined_mappings = set(user_defined_results)

    # Get metrics with their types
    metrics_with_types = session.exec(
        select(
            Metrics,
            QuantitativeMetrics.formula,
            QuantitativeMetrics.id.label("quant_id"),
            QualitativeMetrics.id.label("qual_id"),
            QualitativeMetrics.definition
        )
        .outerjoin(QuantitativeMetrics, Metrics.id == QuantitativeMetrics.metric_id)
        .outerjoin(QualitativeMetrics, Metrics.id == QualitativeMetrics.metric_id)
        .where(Metrics.id.in_(metric_ids))
    ).all()

    # Get metric values with base data
    metric_values = {}
    if values_ids:
        values_results = session.exec(
            select(
                MetricsValues,
                MetricsUnderlyingFeatures,
                MetricsTargetFeatures,
                MetricsScalePoints
            )
            .outerjoin(MetricsUnderlyingFeatures, MetricsValues.id == MetricsUnderlyingFeatures.metric_values_id)
            .outerjoin(MetricsTargetFeatures, MetricsValues.id == MetricsTargetFeatures.metric_values_id)
            .outerjoin(MetricsScalePoints, MetricsValues.id == MetricsScalePoints.metric_values_id)
            .where(MetricsValues.id.in_(values_ids))
        ).all()

        # Process the tuple results
        for metric_value, underlying_features, target_features, scale_point in values_results:
            if metric_value.id not in metric_values:
                metric_values[metric_value.id] = {
                    "metric_id": metric_value.id,
                    "base_threshold": metric_value.threshold,  # Store base threshold
                    "output": metric_value.output,
                    "underlying_features": [],
                    "target_features": [],
                    "scale_points": None
                }

            # Add features and scale points (same as before)
            if underlying_features is not None:
                underlying_dict = underlying_features.model_dump()
                if underlying_dict not in metric_values[metric_value.id]["underlying_features"]:
                    metric_values[metric_value.id]["underlying_features"].append(underlying_dict)

            if target_features is not None:
                target_dict = target_features.model_dump()
                if target_dict not in metric_values[metric_value.id]["target_features"]:
                    metric_values[metric_value.id]["target_features"].append(target_dict)

            if scale_point is not None:
                metric_values[metric_value.id]["scale_points"] = scale_point.model_dump()["scale_points"]

    # Create mapping from metric_id to values_id
    metric_to_values = {m.metric_id: m.values_id for m in metrics_mappings}

    associated_metrics = []
    for metric, formula, quant_id, qual_id, definition in metrics_with_types:
        # Determine metric type
        if quant_id and qual_id:
            metric_type = "both"
        elif quant_id:
            metric_type = "quantitative"
        elif qual_id:
            metric_type = "qualitative"
        else:
            metric_type = "unclassified"

        # Get associated value
        values_id = metric_to_values.get(metric.id)
        metric_value = metric_values.get(values_id) if values_id else None

        # **KEY FIX**: Get effective threshold using the helper function
        effective_threshold = None
        if metric_value and user_audit_id:
            effective_threshold, is_threshold_customized = get_effective_threshold(
                session, user_audit_id, metric.id, event_id, values_id
            )
        elif metric_value:
            effective_threshold = metric_value["base_threshold"]

        # Determine if this metric is user-defined
        is_user_defined = metric.id in user_defined_mappings

        # Determine if this metric was added by an audit instigator
        is_audit_instigator = metric.id in audit_instigator_mappings

        # Handle cases where metric_value might be None
        output = metric_value["output"] if metric_value else None
        underlying_features = metric_value["underlying_features"] if metric_value else []
        target_features = metric_value["target_features"] if metric_value else []
        scale_points = metric_value["scale_points"] if metric_value else None

        associated_metrics.append(EventMetricSummary(
            metric_id=metric.id,
            metric_description=metric.description,
            metric_type=metric_type,
            metric_name=metric.name,
            threshold=effective_threshold,  # Use effective threshold instead of base
            formula=formula if formula is not None else definition,
            reason= metric.reason,
            metric_value_output=output,
            underlying_features=underlying_features,
            target_features=target_features,
            scale_points=scale_points,
            is_user_defined=is_user_defined,
            is_audit_instigator=is_audit_instigator
        ))

    return associated_metrics
