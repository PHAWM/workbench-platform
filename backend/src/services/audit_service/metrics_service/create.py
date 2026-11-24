"""Metric creation service functions"""
from typing import Any, List
from fastapi import HTTPException
from sqlmodel import Session, select, and_

from src.models import *


def create_metric(description: str, threshold: float, session: Session):
    """Create a basic metric record"""
    db_metric = Metrics(
        description=description,
        threshold=threshold
    )
    session.add(db_metric)
    session.commit()
    session.refresh(db_metric)
    return db_metric


def create_qualitative_metric_comprehensive(
    metric: 'QualitativeMetricCreate',
    current_user_id: str,
    session: Session
) -> 'CompleteMetricResponse':
    """
    Create a complete qualitative metric with values and event mappings.

    This service function handles the entire business logic for creating a qualitative metric,
    including:
    - User audit validation
    - Dataset validation
    - Base metric creation
    - User-metric mapping
    - Qualitative details creation
    - Metric values creation with feature validation
    - Event mappings creation

    Args:
        metric: The qualitative metric creation data
        current_user_id: The ID of the user creating the metric
        session: Database session

    Returns:
        CompleteMetricResponse with all created data

    Raises:
        HTTPException: If user has no access or validation fails
    """
    # Import utility functions
    from .utils import (
        get_dataset_for_audit,
        validate_feature_ids,
        create_metric_value_details,
        ensure_user_audit_feature_mappings
    )

    # Get user audit ID for the specific audit
    user_audit_id = session.exec(
        select(MappingAuditUser).where(
            MappingAuditUser.audit_id == metric.audit_id,
            MappingAuditUser.user_id == current_user_id
        )
    ).first()

    if not user_audit_id:
        raise HTTPException(status_code=403, detail="User has no access to this audit")

    # Get the dataset associated with this audit
    dataset_id = get_dataset_for_audit(session, metric.audit_id)

    # Create base metric
    base_metric = Metrics(
        name=metric.name,
        description=metric.description,
        reason=metric.reason
    )
    session.add(base_metric)
    session.commit()
    session.refresh(base_metric)

    # Create user-metric mapping
    user_metric_mapping = MappingUserMetrics(
        user_audit_id=user_audit_id.id,
        metric_id=base_metric.id
    )
    session.add(user_metric_mapping)
    session.commit()

    # Create qualitative details
    qual_metric = QualitativeMetrics(
        metric_id=base_metric.id,
        definition=metric.definition
    )
    session.add(qual_metric)
    session.commit()
    session.refresh(qual_metric)

    # Create metric values with feature validation
    created_values = []
    feature_validation_warnings = []

    for value_data in metric.metric_values:
        # Validate both underlying and target features
        validation_result = validate_feature_ids(
            session,
            value_data.underlying_features,
            value_data.target_features,
            dataset_id=dataset_id,
            user_audit_id=user_audit_id.id
        )

        # Check if there are invalid features
        if not validation_result["valid"] and (validation_result['invalid_features'] == [] or validation_result['invalid_features'] == None):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid features: {validation_result['invalid_features']}. Features must be either in the dataset or user-specific features."
            )

        # Ensure user audit feature mappings exist for features not in the dataset
        ensure_user_audit_feature_mappings(
            session,
            user_audit_id=user_audit_id.id,
            dataset_id=dataset_id,
            underlying_features=value_data.underlying_features,
            target_features=value_data.target_features
        )

        # Warn about user-specific features (they won't be evaluated)
        warning_entry = {"metric_value_index": len(created_values)}
        has_warnings = False

        if validation_result["user_features"]:
            feature_names = session.exec(
                select(UnderlyingFeatures.feature_name).where(
                    UnderlyingFeatures.id.in_(validation_result["user_features"])
                )
            ).all()
            warning_entry["user_underlying_features"] = list(feature_names)
            has_warnings = True

        if validation_result["user_target_features"]:
            target_names = session.exec(
                select(TargetFeatures.target_feature).where(
                    TargetFeatures.id.in_(validation_result["user_target_features"])
                )
            ).all()
            warning_entry["user_target_features"] = list(target_names)
            has_warnings = True

        if has_warnings:
            warning_entry["warning"] = "These user-specific features will not be evaluated in automated evaluation"
            feature_validation_warnings.append(warning_entry)

        # Create metric value
        metric_value = MetricsValues(
            output=value_data.output,
            threshold=str(value_data.threshold)
        )
        session.add(metric_value)
        session.commit()
        session.refresh(metric_value)

        # Create underlying features if provided
        underlying_features = []
        if value_data.underlying_features:
            create_metric_value_details(
                session,
                metric_value.id,
                underlying_features=value_data.underlying_features,
            )
            session.commit()

            for feature in value_data.underlying_features:
                underlying_features.append(feature.model_dump())

        # Create scale points if provided
        if value_data.scale_points:
            create_metric_value_details(
                session,
                metric_value.id,
                scale_points=value_data.scale_points,
            )
            session.commit()

        # Add to created values — once per metric value, event_id filled in if mapped
        created_values.append(MetricValuesDetail(
            id=metric_value.id,
            event_id=metric.event_mappings[0].event_id if metric.event_mappings else None,
            output=metric_value.output,
            threshold=str(metric_value.threshold),
            underlying_features=underlying_features if value_data.underlying_features is not None else None,
            target_features=value_data.target_features if value_data.target_features is not None else [],
            scale_points=value_data.scale_points if value_data.scale_points is not None else {},
        ))

    # Create event mappings
    created_mappings = []
    for mapping_data in metric.event_mappings:
        for value_detail in created_values:
            mapping = MappingMetricsEvents(
                metric_id=base_metric.id,
                event_id=mapping_data.event_id,
                user_audit_id=user_audit_id.id,
                values_id=value_detail.id
            )
            session.add(mapping)
            session.commit()
            session.refresh(mapping)
            created_mappings.append(mapping.id)

    # Prepare response
    qual_details = QualitativeMetricDetail(
        id=qual_metric.id,
        metric_id=qual_metric.metric_id,
        definition=qual_metric.definition
    )

    return CompleteMetricResponse(
        id=base_metric.id,
        description=base_metric.description,
        reason=base_metric.reason,
        metric_type="qualitative",
        quantitative_details=None,
        qualitative_details=qual_details,
        created_values=created_values,
        created_mappings=created_mappings,
        total_values_created=len(created_values),
        total_mappings_created=len(created_mappings),
        feature_warnings=feature_validation_warnings if feature_validation_warnings else []
    )


def create_quantitative_metric_comprehensive(
    metric: 'QuantitativeMetricCreate',
    current_user_id: str,
    session: Session
) -> 'CompleteMetricResponse':
    """
    Create a complete quantitative metric with values and event mappings.

    This service function handles the entire business logic for creating a quantitative metric,
    including:
    - User audit validation
    - Dataset validation
    - Base metric creation
    - User-metric mapping
    - Quantitative details creation
    - Metric values creation with feature validation (underlying and target)
    - Event mappings creation

    Args:
        metric: The quantitative metric creation data
        current_user_id: The ID of the user creating the metric
        session: Database session

    Returns:
        CompleteMetricResponse with all created data

    Raises:
        HTTPException: If user has no access or validation fails
    """
    # Import utility functions
    from .utils import (
        get_dataset_for_audit,
        validate_feature_ids,
        create_metric_value_details
    )

    # Get user audit ID for the specific audit
    user_audit_id = session.exec(
        select(MappingAuditUser).where(
            MappingAuditUser.audit_id == metric.audit_id,
            MappingAuditUser.user_id == current_user_id
        )
    ).first()

    if not user_audit_id:
        raise HTTPException(status_code=403, detail="User has no access to this audit")

    # Get the dataset associated with this audit
    dataset_id = get_dataset_for_audit(session, metric.audit_id)

    # Create base metric
    base_metric = Metrics(
        name=metric.name,
        description=metric.description,
        reason=metric.reason
    )
    session.add(base_metric)
    session.commit()
    session.refresh(base_metric)

    # Create user-metric mapping
    user_metric_mapping = MappingUserMetrics(
        user_audit_id=user_audit_id.id,
        metric_id=base_metric.id
    )
    session.add(user_metric_mapping)
    session.commit()

    # Create quantitative details
    quant_metric = QuantitativeMetrics(
        metric_id=base_metric.id,
        formula=metric.formula
    )
    session.add(quant_metric)
    session.commit()
    session.refresh(quant_metric)

    # Create metric values with feature validation
    created_values = []
    feature_validation_warnings = []

    for value_data in metric.metric_values:
        # Validate both underlying and target features against dataset and user features
        validation_result = validate_feature_ids(
            session,
            value_data.underlying_features,
            value_data.target_features,
            dataset_id=dataset_id,
            user_audit_id=user_audit_id.id
        )

        # Check if there are invalid features
        if not validation_result['invalid_features'] == []:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid features: {validation_result['invalid_features']}. Features must be either in the dataset or user-specific features."
            )

        # Warn about user-specific features (they won't be evaluated)
        warning_entry = {"metric_value_index": len(created_values)}
        has_warnings = False

        if validation_result["user_features"]:
            feature_names = session.exec(
                select(UnderlyingFeatures.feature_name).where(
                    UnderlyingFeatures.id.in_(validation_result["user_features"])
                )
            ).all()
            warning_entry["user_underlying_features"] = list(feature_names)
            has_warnings = True

        if validation_result["user_target_features"]:
            target_names = session.exec(
                select(TargetFeatures.target_feature).where(
                    TargetFeatures.id.in_(validation_result["user_target_features"])
                )
            ).all()
            warning_entry["user_target_features"] = list(target_names)
            has_warnings = True

        if has_warnings:
            warning_entry["warning"] = "These user-specific features will not be evaluated in automated evaluation"
            feature_validation_warnings.append(warning_entry)

        # Create metric value
        metric_value = MetricsValues(
            output=value_data.output,
            threshold=str(value_data.threshold)
        )
        session.add(metric_value)
        session.commit()
        session.refresh(metric_value)

        underlying_features = []
        target_features = []

        # Create features with proper feature_ids - includes both underlying and target
        if value_data.underlying_features:
            create_metric_value_details(
                session,
                metric_value.id,
                underlying_features=value_data.underlying_features,
            )
            session.commit()
            underlying_features = [f.model_dump() for f in value_data.underlying_features]

        # Create target features if provided
        if value_data.target_features:
            create_metric_value_details(
                session,
                metric_value.id,
                target_features=value_data.target_features,
            )
            session.commit()
            target_features = [f.model_dump() for f in value_data.target_features]

        # Add to created values — once per metric value, event_id filled in later if mapped
        created_values.append(MetricValuesDetail(
            id=metric_value.id,
            event_id=metric.event_mappings[0].event_id if metric.event_mappings else None,
            output=metric_value.output,
            threshold=str(metric_value.threshold),
            underlying_features=underlying_features,
            target_features=target_features,
            scale_points=value_data.scale_points if value_data.scale_points is not None else {},
        ))

    # Create event mappings
    created_mappings = []
    for mapping_data in metric.event_mappings:
        for value_detail in created_values:
            mapping = MappingMetricsEvents(
                metric_id=base_metric.id,
                event_id=mapping_data.event_id,
                user_audit_id=user_audit_id.id,
                values_id=value_detail.id
            )
            session.add(mapping)
            session.commit()
            session.refresh(mapping)
            created_mappings.append(mapping.id)

    # Prepare response
    quant_details = QuantitativeMetricDetail(
        id=quant_metric.id,
        metric_id=quant_metric.metric_id,
        formula=quant_metric.formula
    )

    return CompleteMetricResponse(
        id=base_metric.id,
        description=base_metric.description,
        reason=base_metric.reason,
        metric_type="quantitative",
        quantitative_details=quant_details,
        qualitative_details=None,
        created_values=created_values,
        created_mappings=created_mappings,
        total_values_created=len(created_values),
        total_mappings_created=len(created_mappings),
        feature_warnings=feature_validation_warnings if feature_validation_warnings else []
    )


def assign_metric_to_event_comprehensive(
    request: 'AssignMetricEventRequest',
    current_user_id: str,
    session: Session
) -> 'AssignMetricEventResponse':
    """
    Assign an existing metric to an event for a user_audit.

    This function will:
    1. Verify user has access to the audit
    2. Verify the metric and event exist
    3. Check if a MappingMetricsEvents already exists, if not create one
    4. Create a MetricsValues record if needed
    5. Create a MappingEventsAuditStatus record if needed

    Args:
        request: The assignment request containing audit_id, event_id, metric_id, threshold
        current_user_id: The ID of the user making the assignment
        session: Database session

    Returns:
        AssignMetricEventResponse with created/found mapping details

    Raises:
        HTTPException: If user has no access, or metric/event don't exist
    """
    # Get user_audit_id for this audit and user
    user_audit = session.exec(
        select(MappingAuditUser).where(
            MappingAuditUser.audit_id == request.audit_id,
            MappingAuditUser.user_id == current_user_id
        )
    ).first()

    if not user_audit:
        raise HTTPException(status_code=403, detail="User does not have access to this audit")

    # Verify metric exists
    metric = session.exec(
        select(Metrics).where(Metrics.id == request.metric_id)
    ).first()

    if not metric:
        raise HTTPException(status_code=404, detail=f"Metric with id {request.metric_id} not found")

    # Verify event exists
    event = session.exec(
        select(Events).where(Events.id == request.event_id)
    ).first()

    if not event:
        raise HTTPException(status_code=404, detail=f"Event with id {request.event_id} not found")

    # Check if MappingMetricsEvents already exists for this metric-event-user_audit combination
    existing_mapping = session.exec(
        select(MappingMetricsEvents).where(
            MappingMetricsEvents.metric_id == request.metric_id,
            MappingMetricsEvents.event_id == request.event_id,
            MappingMetricsEvents.user_audit_id == user_audit.id
        )
    ).first()

    if existing_mapping:
        # Mapping already exists, check if MappingEventsAuditStatus exists too
        existing_audit_status = session.exec(
            select(MappingEventsAuditStatus).where(
                MappingEventsAuditStatus.metric_id == request.metric_id,
                MappingEventsAuditStatus.event_id == request.event_id,
                MappingEventsAuditStatus.user_audit_id == user_audit.id,
                MappingEventsAuditStatus.audit_id == request.audit_id
            )
        ).first()

        audit_status_id = existing_audit_status.id if existing_audit_status else 0

        return AssignMetricEventResponse(
            mapping_id=existing_mapping.id,
            values_id=existing_mapping.values_id,
            metric_id=request.metric_id,
            event_id=request.event_id,
            user_audit_id=user_audit.id,
            audit_status_id=audit_status_id,
            message="Mapping already exists"
        )

    # Create MetricsValues record
    metric_value = MetricsValues(
        output={},
        threshold=request.threshold
    )
    session.add(metric_value)
    session.commit()
    session.refresh(metric_value)

    # Create MappingMetricsEvents record
    mapping = MappingMetricsEvents(
        metric_id=request.metric_id,
        event_id=request.event_id,
        user_audit_id=user_audit.id,
        values_id=metric_value.id
    )
    session.add(mapping)
    session.commit()
    session.refresh(mapping)

    # Create MappingEventsAuditStatus record
    audit_status = MappingEventsAuditStatus(
        event_id=request.event_id,
        audit_id=request.audit_id,
        metric_id=request.metric_id,
        user_audit_id=user_audit.id,
        recommendation=None,
        notes=None,
        status=0
    )
    session.add(audit_status)
    session.commit()
    session.refresh(audit_status)

    return AssignMetricEventResponse(
        mapping_id=mapping.id,
        values_id=metric_value.id,
        metric_id=request.metric_id,
        event_id=request.event_id,
        user_audit_id=user_audit.id,
        audit_status_id=audit_status.id,
        message="Metric successfully assigned to event"
    )
