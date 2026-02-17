"""Metric update service functions"""
from typing import Any
from fastapi import HTTPException
from sqlmodel import Session, select, delete

from src.models import *


def update_metric(metric_id: int, metric_update: MetricsUpdate, session: Session):
    """Update an existing metric"""
    statement = select(Metrics).where(Metrics.id == metric_id)
    db_metric = session.exec(statement).first()

    if not db_metric:
        raise HTTPException(status_code=404, detail="Metric not found")

    update_data = metric_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_metric, field, value)

    session.add(db_metric)
    session.commit()
    session.refresh(db_metric)
    return db_metric


def update_qualitative_metric_comprehensive(
    metric_id: int,
    qual_update: 'QualitativeMetricUpdate',
    current_user_id: str,
    session: Session
) -> 'CompleteMetricUpdateResponse':
    """
    Update a complete qualitative metric including its values.

    This service function handles the entire business logic for updating a qualitative metric,
    including:
    - User access verification
    - Base metric updates (name, description, reason)
    - Qualitative details updates (definition)
    - Metric values updates (including features and scale points)
    - Creating new metric values if needed

    Args:
        metric_id: The ID of the metric to update
        qual_update: The qualitative metric update data
        current_user_id: The ID of the user making the update
        session: Database session

    Returns:
        CompleteMetricUpdateResponse with all updated data

    Raises:
        HTTPException: If metric not found or user has no access
    """
    # Import utility functions
    from .utils import create_metric_value_details, ensure_user_audit_feature_mappings, get_dataset_for_audit

    # Get the qualitative metric and verify user access
    qual_metric = session.exec(
        select(QualitativeMetrics).where(QualitativeMetrics.metric_id == metric_id)
    ).first()

    if not qual_metric:
        raise HTTPException(status_code=404, detail="Qualitative metric not found")

    # Verify user has access through user_audit_id relationship
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

    # Get user_audit mapping to retrieve audit_id for feature mapping
    user_audit_mapping = session.exec(
        select(MappingAuditUser).where(
            MappingAuditUser.id == user_metric_check.user_audit_id
        )
    ).first()

    # Get the dataset associated with this audit for feature validation
    dataset_id = get_dataset_for_audit(session, user_audit_mapping.audit_id) if user_audit_mapping else None

    # Update base metric if provided
    base_metric = session.get(Metrics, qual_metric.metric_id)
    if qual_update.description is not None:
        base_metric.description = qual_update.description
    if qual_update.name is not None:
        base_metric.name = qual_update.name
    if qual_update.reason is not None:
        base_metric.reason = qual_update.reason

    # Update qualitative details if provided
    if qual_update.definition is not None:
        qual_metric.definition = qual_update.definition

    session.add(base_metric)
    session.add(qual_metric)
    session.commit()
    session.refresh(base_metric)
    session.refresh(qual_metric)

    # Handle metric values updates
    updated_values = []
    created_values = []
    deleted_values = []

    if qual_update.metric_values is not None:
        for value_update in qual_update.metric_values:
            if value_update.id:
                # Update existing value
                existing_value = session.get(MetricsValues, value_update.id)
            else:
                # Find existing value by event and audit
                existing_value_id = session.exec(
                    select(MappingMetricsEvents.values_id)
                    .join(MappingAuditUser, MappingAuditUser.id == MappingMetricsEvents.user_audit_id)
                    .where(
                        MappingMetricsEvents.metric_id == metric_id,
                        MappingMetricsEvents.event_id == value_update.event_id,
                        MappingAuditUser.user_id == current_user_id,
                        MappingAuditUser.audit_id == value_update.audit_id,
                    )
                ).first()

                existing_value = session.get(MetricsValues, existing_value_id)

            if existing_value:
                # Update existing value
                if value_update.output is not None:
                    existing_value.output = value_update.output
                if value_update.threshold is not None:
                    existing_value.threshold = value_update.threshold

                session.add(existing_value)
                session.commit()
                session.refresh(existing_value)

                # Update underlying features if provided
                if hasattr(value_update, 'underlying_features') and value_update.underlying_features is not None:
                    # Delete existing underlying_features
                    session.exec(
                        delete(MetricsUnderlyingFeatures)
                        .where(MetricsUnderlyingFeatures.metric_values_id == existing_value.id)
                    )
                    # Create new underlying_features
                    for feature_data in value_update.underlying_features:
                        feature_mapping = MetricsUnderlyingFeatures(
                            metric_values_id=existing_value.id,
                            feature_id=feature_data.feature_id,
                            ranges=feature_data.ranges if feature_data.ranges is not None else []
                        )
                        session.add(feature_mapping)

                # Update target features if provided
                if hasattr(value_update, 'target_features') and value_update.target_features is not None:
                    # Delete existing target_features
                    session.exec(
                        delete(MetricsTargetFeatures)
                        .where(MetricsTargetFeatures.metric_values_id == existing_value.id)
                    )
                    # Create new target_features
                    for feature_data in value_update.target_features:
                        target_mapping = MetricsTargetFeatures(
                            metric_values_id=existing_value.id,
                            target_feature_id=feature_data.get('feature_id')
                        )
                        session.add(target_mapping)

                # Ensure user audit feature mappings exist for features not in the dataset
                if user_audit_mapping and dataset_id:
                    ensure_user_audit_feature_mappings(
                        session,
                        user_audit_id=user_audit_mapping.id,
                        dataset_id=dataset_id,
                        underlying_features=value_update.underlying_features if hasattr(value_update, 'underlying_features') else None,
                        target_features=value_update.target_features if hasattr(value_update, 'target_features') else None
                    )

                # Update scale points if provided
                if hasattr(value_update, 'scale_points') and value_update.scale_points is not None:
                    # Delete existing scale points
                    session.exec(
                        delete(MetricsScalePoints)
                        .where(MetricsScalePoints.metric_values_id == existing_value.id)
                    )
                    # Create new scale points
                    scale_point_mapping = MetricsScalePoints(
                        metric_values_id=existing_value.id,
                        scale_points=value_update.scale_points
                    )
                    session.add(scale_point_mapping)

                session.commit()

                # Convert features to dicts for response
                underlying_features_dicts = None
                if hasattr(value_update, 'underlying_features') and value_update.underlying_features:
                    underlying_features_dicts = [
                        feature.model_dump() if hasattr(feature, 'model_dump') else dict(feature)
                        for feature in value_update.underlying_features
                    ]

                target_features_dicts = None
                if hasattr(value_update, 'target_features') and value_update.target_features:
                    target_features_dicts = [
                        feature.model_dump() if hasattr(feature, 'model_dump') else dict(feature)
                        for feature in value_update.target_features
                    ]

                updated_values.append(MetricValuesDetail(
                    id=existing_value.id,
                    output=existing_value.output,
                    threshold=str(existing_value.threshold),
                    underlying_features=underlying_features_dicts,
                    target_features=target_features_dicts,
                    scale_points=value_update.scale_points if value_update.scale_points is not None else {},
                ))
            else:
                # Create new value
                new_value = MetricsValues(
                    output=value_update.output,
                    threshold=str(value_update.threshold)
                )
                session.add(new_value)
                session.commit()
                session.refresh(new_value)

                # Create features and scale points for new value
                create_metric_value_details(
                    session,
                    new_value.id,
                    value_update.underlying_features,
                    value_update.target_features,
                    value_update.scale_points,
                )

                # Ensure user audit feature mappings exist for features not in the dataset
                if user_audit_mapping and dataset_id:
                    ensure_user_audit_feature_mappings(
                        session,
                        user_audit_id=user_audit_mapping.id,
                        dataset_id=dataset_id,
                        underlying_features=value_update.underlying_features,
                        target_features=value_update.target_features
                    )

                # Convert features to dictionaries for response
                underlying_features_dict = []
                if value_update.underlying_features:
                    underlying_features_dict = [
                        {
                            'feature_id': f.get('feature_id') if isinstance(f, dict) else f.feature_id,
                            'ranges': f.get('ranges', []) if isinstance(f, dict) else f.ranges
                        } for f in value_update.underlying_features
                    ]

                target_features_dict = []
                if value_update.target_features:
                    target_features_dict = [
                        {
                            'feature_id': f.get('feature_id') if isinstance(f, dict) else f.feature_id
                        } for f in value_update.target_features
                    ]

                created_values.append(MetricValuesDetail(
                    id=new_value.id,
                    output=new_value.output,
                    threshold=str(new_value.threshold),
                    underlying_features=underlying_features_dict,
                    target_features=target_features_dict,
                    scale_points=value_update.scale_points if value_update.scale_points is not None else {},
                ))

    # Prepare response
    qual_details = QualitativeMetricDetail(
        id=qual_metric.id,
        metric_id=qual_metric.metric_id,
        definition=qual_metric.definition
    )

    return CompleteMetricUpdateResponse(
        id=base_metric.id,
        description=base_metric.description,
        reason=base_metric.reason,
        metric_type="qualitative",
        quantitative_details=None,
        qualitative_details=qual_details,
        updated_values=updated_values,
        created_values=created_values,
        deleted_values=deleted_values,
        total_values_updated=len(updated_values),
        total_values_created=len(created_values),
        total_values_deleted=len(deleted_values)
    )


def update_quantitative_metric_comprehensive(
    metric_id: int,
    quant_update: 'QuantitativeMetricUpdate',
    current_user_id: str,
    session: Session
) -> 'CompleteMetricUpdateResponse':
    """
    Update a complete quantitative metric including its values.

    This service function handles the entire business logic for updating a quantitative metric,
    including:
    - User access verification
    - Base metric updates (name, description, reason)
    - Quantitative details updates (formula)
    - Metric values updates (including underlying/target features)
    - Creating new metric values if needed

    Args:
        metric_id: The ID of the metric to update
        quant_update: The quantitative metric update data
        current_user_id: The ID of the user making the update
        session: Database session

    Returns:
        CompleteMetricUpdateResponse with all updated data

    Raises:
        HTTPException: If metric not found or user has no access
    """
    # Import utility functions
    from .utils import create_metric_value_details

    # Get the quantitative metric and verify user access
    quant_metric = session.exec(
        select(QuantitativeMetrics).where(QuantitativeMetrics.metric_id == metric_id)
    ).first()

    if not quant_metric:
        raise HTTPException(status_code=404, detail="Quantitative metric not found")

    # Verify user has access through user_audit_id relationship
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

    # Update base metric if provided
    base_metric = session.get(Metrics, quant_metric.metric_id)
    if quant_update.description is not None:
        base_metric.description = quant_update.description
    if quant_update.name is not None:
        base_metric.name = quant_update.name
    if quant_update.reason is not None:
        base_metric.reason = quant_update.reason

    # Update quantitative details if provided
    if quant_update.formula is not None:
        quant_metric.formula = quant_update.formula

    session.add(base_metric)
    session.add(quant_metric)
    session.commit()
    session.refresh(base_metric)
    session.refresh(quant_metric)

    # Handle metric values updates
    updated_values = []
    created_values = []
    deleted_values = []

    if quant_update.metric_values is not None:
        for value_update in quant_update.metric_values:
            if value_update.id:
                # Update existing value
                existing_value = session.get(MetricsValues, value_update.id)
            else:
                # Find existing value by event and audit
                existing_value_id = session.exec(
                    select(MappingMetricsEvents.values_id)
                    .join(MappingAuditUser, MappingAuditUser.id == MappingMetricsEvents.user_audit_id)
                    .where(
                        MappingMetricsEvents.metric_id == metric_id,
                        MappingMetricsEvents.event_id == value_update.event_id,
                        MappingAuditUser.user_id == current_user_id,
                        MappingAuditUser.audit_id == value_update.audit_id,
                    )
                ).first()

                existing_value = session.get(MetricsValues, existing_value_id)

            if existing_value:
                # Update existing value
                if value_update.output is not None:
                    existing_value.output = value_update.output
                if value_update.threshold is not None:
                    existing_value.threshold = value_update.threshold

                session.add(existing_value)
                session.commit()
                session.refresh(existing_value)

                # Update underlying features if provided
                if hasattr(value_update, 'underlying_features') and value_update.underlying_features is not None:
                    # Set output to {} when underlying_features are updated
                    existing_value.output = {}
                    # Delete existing underlying_features
                    session.exec(
                        delete(MetricsUnderlyingFeatures)
                        .where(MetricsUnderlyingFeatures.metric_values_id == existing_value.id)
                    )
                    # Create new underlying_features
                    for feature_data in value_update.underlying_features:
                        feature_mapping = MetricsUnderlyingFeatures(
                            metric_values_id=existing_value.id,
                            feature_id=feature_data.feature_id,
                            ranges=feature_data.ranges
                        )
                        session.add(feature_mapping)

                # Update target features if provided
                if hasattr(value_update, 'target_features') and value_update.target_features is not None:
                    # Set output to {} when target_features are updated
                    existing_value.output = {}
                    # Delete existing target_features
                    session.exec(
                        delete(MetricsTargetFeatures)
                        .where(MetricsTargetFeatures.metric_values_id == existing_value.id)
                    )
                    # Create new target_features
                    for feature_data in value_update.target_features:
                        target_mapping = MetricsTargetFeatures(
                            metric_values_id=existing_value.id,
                            target_feature_id=feature_data.feature_id,
                        )
                        session.add(target_mapping)

                # Update scale points if provided
                if hasattr(value_update, 'scale_points') and value_update.scale_points is not None:
                    # Delete existing scale points
                    session.exec(
                        delete(MetricsScalePoints)
                        .where(MetricsScalePoints.metric_values_id == existing_value.id)
                    )
                    # Create new scale points
                    scale_point_mapping = MetricsScalePoints(
                        metric_values_id=existing_value.id,
                        scale_points=value_update.scale_points
                    )
                    session.add(scale_point_mapping)

                # Convert features to dicts for response
                underlying_features_dict = []
                if value_update.underlying_features:
                    underlying_features_dict = [
                        {
                            'feature_id': f.feature_id,
                            'ranges': f.ranges
                        } for f in value_update.underlying_features
                    ]

                target_features_dict = []
                if value_update.target_features:
                    target_features_dict = [
                        {
                            'feature_id': f.feature_id
                        } for f in value_update.target_features
                    ]

                session.commit()

                updated_values.append(MetricValuesDetail(
                    id=existing_value.id,
                    event_id=None,
                    output=existing_value.output,
                    threshold=str(existing_value.threshold),
                    underlying_features=underlying_features_dict,
                    target_features=target_features_dict,
                    scale_points=value_update.scale_points if value_update.scale_points is not None else {},
                ))
            else:
                # Create new value
                new_value = MetricsValues(
                    output=value_update.output,
                    threshold=str(value_update.threshold)
                )
                session.add(new_value)
                session.commit()
                session.refresh(new_value)

                # Create features and scale points for new value
                create_metric_value_details(
                    session,
                    new_value.id,
                    value_update.underlying_features,
                    value_update.target_features,
                    value_update.scale_points
                )

                # Convert features to dicts for response
                underlying_features_dict = []
                if value_update.underlying_features:
                    underlying_features_dict = [
                        {
                            'feature_id': f.feature_id,
                            'ranges': f.ranges
                        } for f in value_update.underlying_features
                    ]

                target_features_dict = []
                if value_update.target_features:
                    target_features_dict = [
                        {
                            'feature_id': f.feature_id
                        } for f in value_update.target_features
                    ]

                session.commit()

                created_values.append(MetricValuesDetail(
                    id=new_value.id,
                    event_id=None,
                    output=new_value.output,
                    threshold=str(new_value.threshold),
                    underlying_features=underlying_features_dict,
                    target_features=target_features_dict,
                    scale_points=value_update.scale_points if value_update.scale_points is not None else {},
                ))

    # Prepare response
    quant_details = QuantitativeMetricDetail(
        id=quant_metric.id,
        metric_id=quant_metric.metric_id,
        formula=quant_metric.formula
    )

    return CompleteMetricUpdateResponse(
        id=base_metric.id,
        description=base_metric.description,
        reason=base_metric.reason,
        metric_type="quantitative",
        quantitative_details=quant_details,
        qualitative_details=None,
        updated_values=updated_values,
        created_values=created_values,
        deleted_values=deleted_values,
        total_values_updated=len(updated_values),
        total_values_created=len(created_values),
        total_values_deleted=len(deleted_values)
    )


def update_threshold_comprehensive(
    metric_id: int,
    update_data: 'MetricValueUpdate',
    current_user_id: str,
    session: Session
) -> dict:
    """
    Update threshold - directly if same user/audit, via customisation if different.

    This service function handles:
    - User audit access verification
    - Metric-event mapping retrieval
    - Creator verification (same user/audit)
    - Direct threshold update for creator
    - Custom threshold creation/update for other users
    - Response construction

    Args:
        metric_id: The ID of the metric
        update_data: The threshold update data
        current_user_id: The ID of the user updating the threshold
        session: Database session

    Returns:
        Dictionary with message, metric_id, event_id, updated_directly, and new_threshold

    Raises:
        HTTPException: If user has no access or mapping not found
    """
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
            MappingMetricsEvents.event_id == update_data.event_id,
            MappingMetricsEvents.metric_id == metric_id
        )
    ).first()

    if not mapping:
        raise HTTPException(status_code=404, detail="Metric-event mapping not found")

    # Check if user is the creator of this metric in this audit context
    metric_creator_check = session.exec(
        select(MappingUserMetrics).where(
            MappingUserMetrics.metric_id == metric_id,
            MappingUserMetrics.user_audit_id == user_audit_mapping.id
        )
    ).first()

    # If same user AND same audit, update the base MetricsValues directly
    if metric_creator_check:
        base_metric_value = session.get(MetricsValues, mapping.values_id)
        if update_data.threshold is not None:
            base_metric_value.threshold = update_data.threshold

        session.add(base_metric_value)
        session.commit()

        return {
            "message": "Threshold updated directly",
            "metric_id": metric_id,
            "event_id": update_data.event_id,
            "updated_directly": True,
            "new_threshold": base_metric_value.threshold
        }

    # Different user or different audit - use customisation
    existing_custom = session.exec(
        select(UserMetricThresholds).where(
            UserMetricThresholds.user_audit_id == user_audit_mapping.id,
            UserMetricThresholds.metric_id == metric_id,
            UserMetricThresholds.event_id == update_data.event_id,
            UserMetricThresholds.values_id == mapping.values_id
        )
    ).first()

    if existing_custom:
        # Update existing custom threshold
        existing_custom.custom_threshold = update_data.threshold
        session.add(existing_custom)
    else:
        # Create new custom threshold
        new_custom = UserMetricThresholds(
            user_audit_id=user_audit_mapping.id,
            metric_id=metric_id,
            event_id=update_data.event_id,
            values_id=mapping.values_id,
            custom_threshold=update_data.threshold
        )
        session.add(new_custom)

    session.commit()

    return {
        "message": "Threshold updated via customisation",
        "metric_id": metric_id,
        "event_id": update_data.event_id,
        "updated_directly": False,
        "is_custom": True,
        "new_threshold": update_data.threshold
    }


def update_metric_value_features_comprehensive(
    value_id: int,
    features_update: dict,
    current_user_id: str,
    session: Session
) -> dict:
    """
    Update underlying features, target features, and scale points for a metric value.

    This service function handles:
    - User access verification
    - Deletion of existing features
    - Creation of new features
    - Response construction

    Args:
        value_id: The ID of the metric value
        features_update: Dictionary with underlying_features, target_features, and/or scale_points
        current_user_id: The ID of the user updating the features
        session: Database session

    Returns:
        Dictionary with message, value_id, and updated_features list

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

    # Update underlying features if provided
    if 'underlying_features' in features_update and features_update['underlying_features'] is not None:
        # Delete existing underlying features
        session.exec(
            delete(MetricsUnderlyingFeatures)
            .where(MetricsUnderlyingFeatures.metric_values_id == value_id)
        )

        # Create new underlying features
        for feature_data in features_update['underlying_features']:
            feature_mapping = MetricsUnderlyingFeatures(
                metric_values_id=value_id,
                feature_id=feature_data.get('feature_id'),
                ranges=feature_data.get('ranges', [])
            )
            session.add(feature_mapping)

    # Update target features if provided
    if 'target_features' in features_update and features_update['target_features'] is not None:
        # Delete existing target features
        session.exec(
            delete(MetricsTargetFeatures)
            .where(MetricsTargetFeatures.metric_values_id == value_id)
        )

        # Create new target features
        for feature_data in features_update['target_features']:
            target_mapping = MetricsTargetFeatures(
                metric_values_id=value_id,
                target_feature_id=feature_data.get('feature_id')
            )
            session.add(target_mapping)

    # Update scale points if provided
    if 'scale_points' in features_update and features_update['scale_points'] is not None:
        # Delete existing scale points
        session.exec(
            delete(MetricsScalePoints)
            .where(MetricsScalePoints.metric_values_id == value_id)
        )

        # Create new scale points
        if features_update['scale_points']:  # Only create if not empty
            scale_point_mapping = MetricsScalePoints(
                metric_values_id=value_id,
                scale_points=features_update['scale_points']
            )
            session.add(scale_point_mapping)

    session.commit()

    return {
        "message": "Metric value features updated successfully",
        "value_id": value_id,
        "updated_features": list(features_update.keys())
    }
