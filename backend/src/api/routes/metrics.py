from typing import List, Optional, Dict

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import delete, func, select, and_, or_

from src.api.deps import (
    SessionDep, get_current_user
)

from src.models import *
from src.services.audit_service import metrics_service

router = APIRouter(prefix="/metrics", tags=["Metrics"])

# Import helper functions from service layer
from src.services.audit_service.metrics_service import (
    get_user_audit_ids,
    create_metric_value_details,
    get_metric_value_details,
    get_effective_threshold,
    get_dataset_for_audit,
    validate_feature_ids,
    validate_target_feature_ids
)


@router.get("/dataset-features/{audit_id}")
def get_dataset_features_for_audit(
    audit_id: int,
    session: SessionDep,
    current_user = Depends(get_current_user)
):
    """
    Get all available underlying features for an audit's dataset.
    This helps the frontend know which features can be selected when creating metrics.
    """
    try:
        return metrics_service.get_dataset_features_for_audit_with_context(
            audit_id=audit_id,
            current_user_id=current_user.id,
            session=session
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to retrieve dataset features: {str(e)}")


@router.post("/quantitative/create", response_model=CompleteMetricResponse)
def create_quantitative_metric(
    metric: QuantitativeMetricCreate,
    session: SessionDep,
    current_user = Depends(get_current_user)
):
    """Create a complete quantitative metric with values and event mappings"""
    try:
        return metrics_service.create_quantitative_metric_comprehensive(
            metric=metric,
            current_user_id=current_user.id,
            session=session
        )
    except HTTPException:
        session.rollback()
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=400, detail=f"Failed to create quantitative metric: {str(e)}")

@router.post("/qualitative/create", response_model=CompleteMetricResponse)
def create_qualitative_metric(
    metric: QualitativeMetricCreate,
    session: SessionDep,
    current_user = Depends(get_current_user)
):
    """Create a complete qualitative metric with values and event mappings"""
    try:
        return metrics_service.create_qualitative_metric_comprehensive(
            metric=metric,
            current_user_id=current_user.id,
            session=session
        )
    except HTTPException:
        session.rollback()
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=400, detail=f"Failed to create qualitative metric: {str(e)}")

@router.get("/{metric_id}", response_model=SingleMetricDetailResponse)
def get_metric_detailed(
    metric_id: int,
    session: SessionDep,
    current_user = Depends(get_current_user)
):
    """Get detailed metric information with effective thresholds"""
    try:
        return metrics_service.get_metric_detailed_with_context(
            metric_id=metric_id,
            current_user_id=current_user.id,
            session=session
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to retrieve metric details: {str(e)}")

@router.get("/", response_model=List[Metrics])
def list_metrics(
    session: SessionDep, 
    skip: int = 0, 
    limit: int = 100,
    current_user = Depends(get_current_user),  # UPDATED: Remove type annotation
    audit_id: Optional[int] = None,
    event_id: Optional[int] = None
):
    """List all metrics with pagination - UPDATED access control like events"""
    base_statement = (
        select(Metrics)
        .join(MappingUserMetrics, Metrics.id == MappingUserMetrics.metric_id)
        .join(MappingAuditUser, MappingAuditUser.id == MappingUserMetrics.user_audit_id)
        .where(MappingAuditUser.user_id == current_user.id)
    )
    
    # UPDATED: Filter by audit_id if provided (using user_audit_id lookup)
    if audit_id is not None:
        # Get user_audit_id for this audit and user
        user_audit_mapping = session.exec(
            select(MappingAuditUser).where(
                MappingAuditUser.audit_id == audit_id,
                MappingAuditUser.user_id == current_user.id
            )
        ).first()
        
        if not user_audit_mapping:
            raise HTTPException(status_code=403, detail="Access denied to this audit")
        
        base_statement = base_statement.where(MappingUserMetrics.user_audit_id == user_audit_mapping.id)
    
    # Filter by event_id if provided
    if event_id is not None:
        base_statement = base_statement.join(
            MappingMetricsEvents, Metrics.id == MappingMetricsEvents.metric_id
        ).where(MappingMetricsEvents.event_id == event_id)
    
    statement = base_statement.distinct().offset(skip).limit(limit)
    metrics = session.exec(statement).all()
    return metrics

@router.put("/{metric_id}", response_model=Metrics)
def update_metric(
    metric_id: int, 
    metric_update: MetricsUpdate, 
    session: SessionDep,
    current_user = Depends(get_current_user)  # UPDATED: Remove type annotation
):
    """Update an existing metric - UPDATED access control"""
    try:
        # UPDATED: Verify user has access through user_audit_id relationship
        user_metric_check = session.exec(
            select(MappingUserMetrics)
            .join(MappingAuditUser, MappingAuditUser.id == MappingUserMetrics.user_audit_id)
            .where(
                MappingUserMetrics.metric_id == metric_id,
                MappingAuditUser.user_id == current_user.id
            )
        ).first()

        if not user_metric_check:
            raise HTTPException(status_code=404, detail="Metric not found or access denied")
        
        db_metric = metrics_service.update_metric(
            metric_id=metric_id, 
            metric_update=metric_update, 
            session=session
        )
        
        return db_metric
    except HTTPException:
        session.rollback()
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=400, detail=f"Error updating metric: {str(e)}")

@router.delete("/{metric_id}")
def delete_metric(
    metric_id: int, 
    session: SessionDep,
    current_user = Depends(get_current_user)  # UPDATED: Remove type annotation
):
    """Delete a metric - UPDATED access control and new schema"""
    try:
        # UPDATED: Verify user has access through user_audit_id relationship
        user_metric_check = session.exec(
            select(MappingUserMetrics)
            .join(MappingAuditUser, MappingAuditUser.id == MappingUserMetrics.user_audit_id)
            .where(
                MappingUserMetrics.metric_id == metric_id,
                MappingAuditUser.user_id == current_user.id
            )
        ).first()

        if not user_metric_check:
            raise HTTPException(status_code=404, detail="Metric not found or access denied")
        
        # UPDATED: Delete underlying_features, target_features and scale points for associated metric values
        metric_values = session.exec(
            select(MetricsValues)
            .join(MappingMetricsEvents, MetricsValues.id == MappingMetricsEvents.values_id)
            .where(MappingMetricsEvents.metric_id == metric_id)
        ).all()
        
        for value in metric_values:
            # Delete underlying_features
            session.exec(
                delete(MetricsUnderlyingFeatures)
                .where(MetricsUnderlyingFeatures.metric_values_id == value.id)
            )
            # Delete target_features
            session.exec(
                delete(MetricsTargetFeatures)
                .where(MetricsTargetFeatures.metric_values_id == value.id)
            )
            # Delete scale points
            session.exec(
                delete(MetricsScalePoints)
                .where(MetricsScalePoints.metric_values_id == value.id)
            )
        
        message = metrics_service.delete_metric(metric_id=metric_id, session=session)
        
        return message
    except HTTPException:
        session.rollback()
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=400, detail=f"Error deleting metric: {str(e)}")

@router.put("/quantitative/{metric_id}", response_model=CompleteMetricUpdateResponse)
def update_quantitative_metric(
    metric_id: int,
    quant_update: QuantitativeMetricUpdate,
    session: SessionDep,
    current_user = Depends(get_current_user)
):
    """Update a complete quantitative metric including its values"""
    try:
        return metrics_service.update_quantitative_metric_comprehensive(
            metric_id=metric_id,
            quant_update=quant_update,
            current_user_id=current_user.id,
            session=session
        )
    except HTTPException:
        session.rollback()
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=400, detail=f"Error updating quantitative metric: {str(e)}")

@router.get("/by-audit/{audit_id}", response_model=List[Metrics])
def get_metrics_by_audit(
    audit_id: int,
    session: SessionDep,
    current_user = Depends(get_current_user),  # UPDATED: Remove type annotation
    skip: int = 0,
    limit: int = 100
):
    """Get all metrics associated with a specific audit ID - UPDATED to match events pattern"""
    # UPDATED: Get user_audit_id for this audit and user (like events)
    user_audit_mapping = session.exec(
        select(MappingAuditUser).where(
            MappingAuditUser.audit_id == audit_id,
            MappingAuditUser.user_id == current_user.id
        )
    ).first()
    
    if not user_audit_mapping:
        raise HTTPException(status_code=403, detail="Access denied to this audit")
    
    statement = (
        select(Metrics)
        .join(MappingMetricsEvents, Metrics.id == MappingMetricsEvents.metric_id)
        .where(MappingMetricsEvents.user_audit_id == user_audit_mapping.id)
        .distinct()
        .offset(skip)
        .limit(limit)
    )
    
    metrics = session.exec(statement).all()
    return metrics

@router.get("/by-event/{event_id}", response_model=List[Metrics])
def get_metrics_by_event(
    event_id: int,
    session: SessionDep,
    current_user = Depends(get_current_user),  # UPDATED: Remove type annotation
    skip: int = 0,
    limit: int = 100
):
    """Get all metrics associated with a specific event ID - UPDATED access control"""
    statement = (
        select(Metrics)
        .join(MappingMetricsEvents, Metrics.id == MappingMetricsEvents.metric_id)
        .join(MappingAuditUser, MappingAuditUser.id == MappingMetricsEvents.user_audit_id)
        .where(
            MappingMetricsEvents.event_id == event_id,
            MappingAuditUser.user_id == current_user.id
        )
        .distinct()
        .offset(skip)
        .limit(limit)
    )
    
    metrics = session.exec(statement).all()
    return metrics

@router.get("/by-audit/{audit_id}/detailed", response_model=MetricListResponse)
def get_metrics_by_audit_detailed(
    audit_id: int,
    session: SessionDep,
    current_user = Depends(get_current_user),
    skip: int = 0,
    limit: int = 100
):
    """Get all metrics for an audit with creator information and detailed metadata"""
    try:
        return metrics_service.list_metrics_by_audit_detailed(
            audit_id=audit_id,
            current_user_id=current_user.id,
            session=session,
            skip=skip,
            limit=limit
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to retrieve metrics for audit: {str(e)}")

@router.put("/qualitative/{metric_id}", response_model=CompleteMetricUpdateResponse)
def update_qualitative_metric(
    metric_id: int,
    qual_update: QualitativeMetricUpdate,
    session: SessionDep,
    current_user = Depends(get_current_user)
):
    """Update a complete qualitative metric including its values"""
    try:
        return metrics_service.update_qualitative_metric_comprehensive(
            metric_id=metric_id,
            qual_update=qual_update,
            current_user_id=current_user.id,
            session=session
        )
    except HTTPException:
        session.rollback()
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=400, detail=f"Error updating qualitative metric: {str(e)}")

@router.get("/values/{value_id}/underlying_features", response_model=List[dict])
def get_metric_value_underlying_features(
    value_id: int,
    session: SessionDep,
    current_user = Depends(get_current_user)
):
    """Get underlying_features for a specific metric value"""
    try:
        return metrics_service.get_metric_value_underlying_features_with_context(
            value_id=value_id,
            current_user_id=current_user.id,
            session=session
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to retrieve underlying features: {str(e)}")

@router.get("/values/{value_id}/target_features", response_model=List[dict])
def get_metric_value_target_features(
    value_id: int,
    session: SessionDep,
    current_user = Depends(get_current_user)
):
    """Get target_features for a specific metric value"""
    try:
        return metrics_service.get_metric_value_target_features_with_context(
            value_id=value_id,
            current_user_id=current_user.id,
            session=session
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to retrieve target features: {str(e)}")

@router.get("/values/{value_id}/scale-points", response_model=dict)
def get_metric_value_scale_points(
    value_id: int,
    session: SessionDep,
    current_user = Depends(get_current_user)
):
    """Get scale points for a specific metric value"""
    try:
        return metrics_service.get_metric_value_scale_points_with_context(
            value_id=value_id,
            current_user_id=current_user.id,
            session=session
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to retrieve scale points: {str(e)}")
    
@router.put("/{metric_id}/threshold")
def update_threshold(
    metric_id: int,
    update_data: MetricValueUpdate,
    session: SessionDep,
    current_user = Depends(get_current_user)
):
    """Update threshold - directly if same user/audit, via customisation if different"""
    try:
        return metrics_service.update_threshold_comprehensive(
            metric_id=metric_id,
            update_data=update_data,
            current_user_id=current_user.id,
            session=session
        )
    except HTTPException:
        session.rollback()
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=400, detail=f"Failed to update threshold: {str(e)}")

# UPDATED: New endpoint to get all features for a metric value
@router.get("/values/{value_id}/all-features", response_model=dict)
def get_metric_value_all_features(
    value_id: int,
    session: SessionDep,
    current_user = Depends(get_current_user)
):
    """Get all features (underlying, target, and scale points) for a specific metric value"""
    try:
        return metrics_service.get_metric_value_all_features_with_context(
            value_id=value_id,
            current_user_id=current_user.id,
            session=session
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to retrieve all features: {str(e)}")

# UPDATED: New endpoint to update all features for a metric value
@router.put("/values/{value_id}/features")
def update_metric_value_features(
    value_id: int,
    features_update: dict,
    session: SessionDep,
    current_user = Depends(get_current_user)
):
    """Update underlying features, target features, and scale points for a metric value"""
    try:
        return metrics_service.update_metric_value_features_comprehensive(
            value_id=value_id,
            features_update=features_update,
            current_user_id=current_user.id,
            session=session
        )
    except HTTPException:
        session.rollback()
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=400, detail=f"Failed to update metric value features: {str(e)}")

# UPDATED: Helper function to validate target feature IDs separately
def validate_target_feature_ids(session: SessionDep, target_features: List[Dict]):
    """Validate that all target_feature_ids exist in the TargetFeatures table"""
    if not target_features:
        return True
    
    target_feature_ids = [f.get('feature_id') for f in target_features if f.get('feature_id')]
    if not target_feature_ids:
        return True
    
    # Check if all target_feature_ids exist in the database
    existing_target_features = session.exec(
        select(TargetFeatures.id).where(TargetFeatures.id.in_(target_feature_ids))
    ).all()
    
    if len(existing_target_features) != len(set(target_feature_ids)):
        missing_ids = set(target_feature_ids) - set(existing_target_features)
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid target feature_ids: {list(missing_ids)}"
        )
    
    return True

@router.get("/threshold/{metric_id}/{event_id}", response_model=dict)
def get_effective_threshold_endpoint(
    metric_id: int,
    event_id: int,
    session: SessionDep,
    current_user = Depends(get_current_user)
):
    """Get the effective threshold for a metric-event combination"""
    try:
        return metrics_service.get_effective_threshold_with_context(
            metric_id=metric_id,
            event_id=event_id,
            current_user_id=current_user.id,
            session=session
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to get effective threshold: {str(e)}")

@router.delete("/threshold/{metric_id}/{event_id}")
def reset_threshold_to_default(
    metric_id: int,
    event_id: int,
    session: SessionDep,
    current_user = Depends(get_current_user)
):
    """Reset a customised threshold back to default (delete custom threshold)"""
    try:
        return metrics_service.reset_threshold_to_default_comprehensive(
            metric_id=metric_id,
            event_id=event_id,
            current_user_id=current_user.id,
            session=session
        )
    except HTTPException:
        session.rollback()
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=400, detail=f"Failed to reset threshold: {str(e)}")


@router.post("/assign-event", response_model=AssignMetricEventResponse)
def assign_metric_to_event(
    request: AssignMetricEventRequest,
    session: SessionDep,
    current_user = Depends(get_current_user)
):
    """
    Assign an existing metric to an event for a user_audit.

    This will create a MetricsValues record if needed and map the metric to the event.
    Also creates the MappingEventsAuditStatus record for tracking audit status.
    """
    try:
        return metrics_service.assign_metric_to_event_comprehensive(
            request=request,
            current_user_id=current_user.id,
            session=session
        )
    except HTTPException:
        session.rollback()
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=400, detail=f"Failed to assign metric to event: {str(e)}")