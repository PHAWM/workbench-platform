import uuid
from typing import Any, List, Optional, Dict

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import col, delete, func, select

from src.api.deps import (
    SessionDep, get_current_user
)

from src.models import *
from src.services.audit_service import events_service
from enum import Enum
from src.api.routes.metrics import get_effective_threshold

router = APIRouter(prefix="/events", tags=["Events"])

class RiskLevel(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"

class ImpactType(str, Enum):
    positive = "positive"
    negative = "negative"
    neutral = "neutral"

class SortBy(str, Enum):
    likelihood = "likelihood"
    magnitude = "magnitude"
    valence = "valence"
    risk_level = "risk_level"
    created_date = "created_date"

class SortOrder(str, Enum):
    asc = "asc"
    desc = "desc"

@router.post("/")
def create_event(
    description: str, 
    reason: str, 
    cause:str,
    likelihood: float, 
    magnitude: float, 
    valence: float, 
    session: SessionDep,
    current_user = Depends(get_current_user),
    is_user_defined: bool = True,
    is_template: bool = False,
    category: Optional[str] = None
):
    """Create a new event with enhanced type tracking"""
    try:
        # Create the base event
        db_event = events_service.create_event(
            description=description, 
            reason=reason, 
            cause=cause,
            likelihood=likelihood, 
            magnitude=magnitude, 
            valence=valence, 
            session=session
        )
        
        # Create event type
        event_type = EventType(
            event_id=db_event.id,
            is_user_defined=is_user_defined,
            created_by_user_id=current_user.id,
            is_template=is_template,
            category=category
        )
        session.add(event_type)
        session.commit()
        session.refresh(event_type)
        
        return db_event
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=400, detail=f"Error creating event: {str(e)}")

@router.get("/categories")
def get_category(session: SessionDep):
    categories = session.exec(select(EventsCategory)).all()
    
    return categories

@router.get("/features/underlying/{audit_id}")
def get_underlying_features(
    audit_id: int,
    session: SessionDep,
    current_user = Depends(get_current_user)
):
    """
    Get underlying features available for a specific audit.
    Features come from the audit's DatasetMetadata (stored in storage/audits/audit_{audit_id}/input/),
    NOT from OutputEvaluationData (stored in storage/audits/audit_{audit_id}/users/{user_id}/output_evaluation/).
    """
    return events_service.get_underlying_features_for_audit(audit_id, current_user.id, session)

@router.get("/features/target")
def get_features(session: SessionDep):
    features = session.exec(select(TargetFeatures)).all()

    return features


@router.post("/features/user", response_model=UserFeatureResponse)
def create_user_feature(
    feature_data: UserFeatureCreate,
    session: SessionDep,
    current_user = Depends(get_current_user)
):
    """
    Create a new user-specific feature for an audit.
    This allows users to add custom features beyond what's in the dataset.
    The feature is mapped to the user's audit participation, not to the dataset.
    """
    result = events_service.create_user_feature(
        feature_data.feature_name,
        feature_data.audit_id,
        current_user.id,
        session
    )
    return UserFeatureResponse(**result)


@router.post("/features/user/target", response_model=UserTargetFeatureResponse)
def create_user_target_feature(
    feature_data: UserTargetFeatureCreate,
    session: SessionDep,
    current_user = Depends(get_current_user)
):
    """
    Create a new user-specific target feature for an audit.
    This allows users to add custom target features beyond what's in the dataset.
    The feature is mapped to the user's audit participation, not to the dataset.
    """
    result = events_service.create_user_target_feature(
        feature_data.target_feature,
        feature_data.audit_id,
        current_user.id,
        session
    )
    return UserTargetFeatureResponse(**result)


@router.post("/entities", response_model=UserEntityResponse)
def create_user_entity(
    entity_data: UserEntityCreate,
    session: SessionDep,
    current_user = Depends(get_current_user)
):
    """
    Create a new user-defined entity for an audit.
    This allows users to add custom entities (groups of affected individuals).
    The entity is mapped to the user's audit participation.
    Returns the entity_id of the created entity.
    """
    result = events_service.create_user_entity(
        entity_data.name,
        entity_data.num_individuals,
        entity_data.audit_id,
        current_user.id,
        session
    )
    return UserEntityResponse(**result)


@router.post("/categories", response_model=UserCategoryResponse)
def create_user_category(
    category_data: UserCategoryCreate,
    session: SessionDep,
    current_user = Depends(get_current_user)
):
    """
    Create a new user-defined category for an audit.
    This allows users to add custom categories for organizing events.
    The category is mapped to the user's audit participation.
    Returns the category_id of the created category.
    """
    result = events_service.create_user_category(
        category_data.event_name,
        category_data.description,
        category_data.audit_id,
        current_user.id,
        session
    )
    return UserCategoryResponse(**result)


@router.get("/categories/user/{audit_id}")
def get_user_categories(
    audit_id: int,
    session: SessionDep,
    current_user = Depends(get_current_user)
):
    """
    Get all categories available to a user for a specific audit.
    This includes both user-specific categories and system categories from events in this audit.
    """
    return events_service.get_user_categories_for_audit(audit_id, current_user.id, session)


@router.get("/entities/user/{audit_id}")
def get_user_entities(
    audit_id: int,
    session: SessionDep,
    current_user = Depends(get_current_user)
):
    """
    Get all entities available to a user for a specific audit.
    This includes both user-specific entities and entities from events in this audit.
    """
    return events_service.get_user_entities_for_audit(audit_id, current_user.id, session)


@router.get("/features/user/{audit_id}")
def get_user_features(
    audit_id: int,
    session: SessionDep,
    current_user = Depends(get_current_user)
):
    """
    Get all features available to a user for a specific audit.
    This includes both dataset features and user-specific features.
    """
    return events_service.get_user_features_for_audit(audit_id, current_user.id, session)

@router.post("/comprehensive", response_model=EnhancedEventDetailResponse)
def create_event_comprehensive(
    event_data: ComprehensiveEventCreate,
    session: SessionDep,
    current_user = Depends(get_current_user)
):
    """
    Create a new event with related entities in one call
    """
    new_event = events_service.create_comprehensive_event(event_data, current_user.id, session)

    # Return the created event with all details
    return get_event_detailed(new_event.id, session, current_user)

@router.get("/by-event/{event_id}", response_model=EnhancedEventDetailResponse)
def get_event_detailed(
    event_id: int,
    session: SessionDep,
    current_user = Depends(get_current_user),
    audit_id: Optional[int] = None
):
    """Get detailed event information with effective values

    NOTE: audit_id is strongly recommended to ensure proper data isolation.
    Without audit_id, some features may not work correctly.
    """
    return events_service.get_event_detailed_with_context(
        event_id=event_id,
        current_user_id=current_user.id,
        session=session,
        audit_id=audit_id
    )

@router.put("/{event_id}/values")
def update_event_values(
    event_id: int,
    audit_id: int,
    session: SessionDep,
    likelihood: Optional[float] = None,
    magnitude: Optional[float] = None,
    valence: Optional[float] = None,
    current_user = Depends(get_current_user)
):
    """Update event values - directly if same user/audit, via customisation if different"""
    try:
        return events_service.update_event_values(
            event_id, audit_id, current_user.id, likelihood, magnitude, valence, session
        )
    except HTTPException:
        session.rollback()
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=400, detail=f"Failed to update event values: {str(e)}")

@router.put("/{event_id}/comprehensive", response_model=EnhancedEventDetailResponse)
def update_event_comprehensive(
    event_id: int,
    event_update: ComprehensiveEventUpdate,
    session: SessionDep,
    current_user = Depends(get_current_user)
):
    """
    Comprehensive event update that handles all related entities in one call
    """
    try:
        events_service.update_event_comprehensive(event_id, event_update, current_user.id, session)
        return get_event_detailed(event_id, session, current_user)
    except HTTPException:
        session.rollback()
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=400, detail=f"Error updating event: {str(e)}")

# ============= AUDIT PIPELINE EVENTS MAPPING =============

@router.post("/audit-pipeline-mapping", response_model=Dict[str, Any])
def create_audit_pipeline_events_mapping(
    mapping_data: MappingAuditPipelineEventsCreate,
    session: SessionDep,
    current_user = Depends(get_current_user)
):
    """Create a single audit pipeline events mapping"""
    try:
        # Get user's audit ID
        audit_ids = events_service.get_user_audit_ids(session, current_user)
        if not audit_ids:
            raise HTTPException(status_code=403, detail="User has no audit associations")
        
        primary_audit_id = audit_ids[0]
        
        # Check if mapping already exists
        existing = session.exec(
            select(MappingAuditPipelineEvents).where(
                MappingAuditPipelineEvents.audit_pipeline == mapping_data.audit_pipeline,
                MappingAuditPipelineEvents.event_id == mapping_data.event_id,
                MappingAuditPipelineEvents.metric_id == mapping_data.metric_id,
                MappingAuditPipelineEvents.user_audit_id == primary_audit_id
            )
        ).first()
        
        if existing:
            raise HTTPException(status_code=400, detail="Mapping already exists")
        
        # Create new mapping
        new_mapping = MappingAuditPipelineEvents(
            audit_pipeline=mapping_data.audit_pipeline,
            event_id=mapping_data.event_id,
            metric_id=mapping_data.metric_id,
            user_audit_id=primary_audit_id
        )
        
        session.add(new_mapping)
        session.commit()
        session.refresh(new_mapping)
        
        return {
            "id": new_mapping.id,
            "audit_pipeline": new_mapping.audit_pipeline,
            "event_id": new_mapping.event_id,
            "metric_id": new_mapping.metric_id,
            "user_audit_id": new_mapping.user_audit_id,
            "message": "Audit pipeline events mapping created successfully"
        }
        
    except HTTPException:
        session.rollback()
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=400, detail=f"Error creating mapping: {str(e)}")

@router.post("/audit-pipeline-mapping/batch", response_model=Dict[str, Any])
def create_audit_pipeline_events_mappings_batch(
    batch_data: MappingAuditPipelineEventsBatch,
    session: SessionDep,
    current_user = Depends(get_current_user)
):
    """Create multiple audit pipeline events mappings in batch and delete mappings not in the batch"""
    try:
        audit_id = batch_data.audit_id
        user_audit_id = session.exec(select(MappingAuditUser.id).where(MappingAuditUser.audit_id==audit_id, MappingAuditUser.user_id==current_user.id)).first()
        
        # Get audit pipeline ID
        audit_pipeline_id = session.exec(select(MappingAuditPipelineAudit.audit_pipeline).where(MappingAuditPipelineAudit.audit_id == audit_id)).first()
        
        created_mappings = []
        updated_mappings = []
        deleted_mappings = []
        errors = []
        
        # Create a set of incoming mappings for comparison
        incoming_mappings = set()
        for mapping_data in batch_data.mappings:
            incoming_mappings.add((mapping_data.event_id, mapping_data.metric_id))
        
        # Get all existing mappings for this audit pipeline and user
        existing_mappings = session.exec(
            select(MappingAuditPipelineEvents).where(
                MappingAuditPipelineEvents.audit_pipeline == int(audit_pipeline_id),
                MappingAuditPipelineEvents.user_audit_id == user_audit_id
            )
        ).all()
        
        # Find mappings to delete (exist in DB but not in incoming batch)
        existing_mappings_set = set()
        existing_mappings_dict = {}
        for existing in existing_mappings:
            key = (existing.event_id, existing.metric_id)
            existing_mappings_set.add(key)
            existing_mappings_dict[key] = existing
        
        mappings_to_delete = existing_mappings_set - incoming_mappings
        
        # Delete mappings not in the batch
        for event_id, metric_id in mappings_to_delete:
            try:
                mapping_to_delete = existing_mappings_dict[(event_id, metric_id)]
                session.delete(mapping_to_delete)
                deleted_mappings.append({
                    "id": mapping_to_delete.id,
                    "audit_pipeline": mapping_to_delete.audit_pipeline,
                    "event_id": mapping_to_delete.event_id,
                    "metric_id": mapping_to_delete.metric_id
                })

                existing_audit_outcome = session.exec(
                    select(MappingEventsAuditStatus)
                    .where(
                        MappingEventsAuditStatus.audit_id== audit_id,
                        MappingEventsAuditStatus.user_audit_id== user_audit_id,
                        MappingEventsAuditStatus.event_id== event_id,
                        MappingEventsAuditStatus.metric_id== metric_id,
                    )
                ).first()
                
                session.delete(existing_audit_outcome)
                
            except Exception as e:
                errors.append({
                    "mapping": {"event_id": event_id, "metric_id": metric_id},
                    "error": f"Error deleting mapping: {str(e)}"
                })
        
        # Process incoming mappings (create new ones)
        for mapping_data in batch_data.mappings:
            try:
                # Check if mapping already exists
                existing_key = (mapping_data.event_id, mapping_data.metric_id)
                if existing_key in existing_mappings_set:
                    # Mapping already exists, add to updated list
                    existing_mapping = existing_mappings_dict[existing_key]
                    updated_mappings.append({
                        "id": existing_mapping.id,
                        "audit_pipeline": existing_mapping.audit_pipeline,
                        "event_id": existing_mapping.event_id,
                        "metric_id": existing_mapping.metric_id
                    })
                else:
                    # Create new mapping
                    new_mapping = MappingAuditPipelineEvents(
                        audit_pipeline=int(audit_pipeline_id),
                        event_id=mapping_data.event_id,
                        metric_id=mapping_data.metric_id,
                        user_audit_id=user_audit_id
                    )
                    session.add(new_mapping)
                    session.flush()  # Flush to get the ID without committing
                    
                    created_mappings.append({
                        "id": new_mapping.id,
                        "audit_pipeline": new_mapping.audit_pipeline,
                        "event_id": new_mapping.event_id,
                        "metric_id": new_mapping.metric_id
                    })
                
                # Check for status
                audit_stastus_exists = session.exec(
                    select(MappingEventsAuditStatus)
                    .where(
                        MappingEventsAuditStatus.audit_id== audit_id,
                        MappingEventsAuditStatus.user_audit_id== user_audit_id,
                        MappingEventsAuditStatus.event_id== mapping_data.event_id,
                        MappingEventsAuditStatus.metric_id== mapping_data.metric_id,
                    )
                ).first()
                
                if not audit_stastus_exists:
                    audit_mapping = MappingEventsAuditStatus(
                        event_id=mapping_data.event_id,
                        audit_id=audit_id,
                        recommendation=None,
                        status=1,
                        metric_id=mapping_data.metric_id,
                        user_audit_id=user_audit_id
                    )
                    
                    session.add(audit_mapping)
                    
            except Exception as e:
                errors.append({
                    "mapping": mapping_data.dict(),
                    "error": str(e)
                })
        
        # Commit all changes at once
        session.commit()
        
        return {
            "created_mappings": created_mappings,
            "updated_mappings": updated_mappings,
            "deleted_mappings": deleted_mappings,
            "errors": errors,
            "total_processed": len(batch_data.mappings),
            "total_existing": len(existing_mappings),
            "successful_creates": len(created_mappings),
            "successful_updates": len(updated_mappings),
            "successful_deletes": len(deleted_mappings),
            "failed": len(errors),
            "message": f"Batch operation completed: {len(created_mappings)} created, {len(updated_mappings)} already existed, {len(deleted_mappings)} deleted, {len(errors)} failed"
        }
        
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=400, detail=f"Error in batch operation: {str(e)}")
@router.get("/audit-pipeline-mapping/{audit_pipeline_id}", response_model=List[Dict[str, Any]])
def get_audit_pipeline_events_mappings(
    audit_pipeline_id: int,
    session: SessionDep,
    current_user = Depends(get_current_user)
):
    """Get all events and metrics mapped to a specific audit pipeline"""
    try:
        # Get user's audit IDs
        audit_ids = events_service.get_user_audit_ids(session, current_user)
        
        # Get mappings with event and metric details
        mappings_query = (
            select(
                MappingAuditPipelineEvents,
                Events,
                Metrics
            )
            .join(Events, MappingAuditPipelineEvents.event_id == Events.id)
            .join(Metrics, MappingAuditPipelineEvents.metric_id == Metrics.id)
            .where(MappingAuditPipelineEvents.audit_pipeline == audit_pipeline_id)
        )
        
        if audit_ids:
            mappings_query = mappings_query.where(
                MappingAuditPipelineEvents.user_audit_id.in_(audit_ids)
            )
        
        mappings_results = session.exec(mappings_query).all()
        
        mappings = []
        for mapping, event, metric in mappings_results:
            mappings.append({
                "mapping_id": mapping.id,
                "audit_pipeline": mapping.audit_pipeline,
                "event": {
                    "id": event.id,
                    "description": event.description,
                    "cause": event.cause,
                    "reason": event.reason,
                    "likelihood": event.likelihood,
                    "magnitude": event.magnitude,
                    "valence": event.valence
                },
                "metric": {
                    "id": metric.id,
                    "description": metric.description,
                    "reason": metric.reason
                },
                "user_audit_id": mapping.user_audit_id
            })
        
        return mappings
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error fetching mappings: {str(e)}")

@router.delete("/audit-pipeline-mapping/{mapping_id}")
def delete_audit_pipeline_events_mapping_by_id(
    mapping_id: int,
    session: SessionDep,
    current_user = Depends(get_current_user)
):
    """Delete a specific audit pipeline events mapping by ID"""
    try:
        # Get user's audit IDs for authorization
        audit_ids = events_service.get_user_audit_ids(session, current_user)

        # Find the mapping
        mapping = session.exec(
            select(MappingAuditPipelineEvents).where(
                MappingAuditPipelineEvents.id == mapping_id
            )
        ).first()

        if not mapping:
            raise HTTPException(status_code=404, detail="Mapping not found")

        # Check if user has permission (owns the mapping)
        if audit_ids and mapping.user_audit_id not in audit_ids:
            raise HTTPException(status_code=403, detail="Permission denied")

        # Delete the mapping
        session.delete(mapping)
        session.commit()

        return {"message": "Audit pipeline events mapping deleted successfully"}

    except HTTPException:
        session.rollback()
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=400, detail=f"Error deleting mapping: {str(e)}")

@router.delete("/audit-pipeline-mapping", response_model=Dict[str, Any])
def delete_audit_pipeline_events_mapping(
    mapping_data: MappingAuditPipelineEventsCreate,
    session: SessionDep,
    current_user = Depends(get_current_user)
):
    """Delete a specific audit pipeline events mapping using the same structure as create"""
    try:
        # Get user's audit ID
        user_audit_mapping = session.exec(
            select(MappingAuditUser).where(
                MappingAuditUser.audit_id == mapping_data.audit_id,
                MappingAuditUser.user_id == current_user.id
            )
        ).first()

        if not user_audit_mapping:
            raise HTTPException(status_code=403, detail="User has no access to this audit")

        user_audit_id = user_audit_mapping.id

        # Get audit pipeline ID
        audit_pipeline_id = session.exec(
            select(MappingAuditPipelineAudit.audit_pipeline).where(
                MappingAuditPipelineAudit.audit_id == mapping_data.audit_id
            )
        ).first()

        if not audit_pipeline_id:
            raise HTTPException(status_code=404, detail="Audit pipeline not found for this audit")

        # Find the mapping
        mapping = session.exec(
            select(MappingAuditPipelineEvents).where(
                MappingAuditPipelineEvents.audit_pipeline == int(audit_pipeline_id),
                MappingAuditPipelineEvents.event_id == mapping_data.event_id,
                MappingAuditPipelineEvents.metric_id == mapping_data.metric_id,
                MappingAuditPipelineEvents.user_audit_id == user_audit_id
            )
        ).first()

        if not mapping:
            raise HTTPException(status_code=404, detail="Mapping not found")

        # Delete the corresponding audit status entry if it exists
        audit_status = session.exec(
            select(MappingEventsAuditStatus).where(
                MappingEventsAuditStatus.audit_id == mapping_data.audit_id,
                MappingEventsAuditStatus.user_audit_id == user_audit_id,
                MappingEventsAuditStatus.event_id == mapping_data.event_id,
                MappingEventsAuditStatus.metric_id == mapping_data.metric_id
            )
        ).first()

        if audit_status:
            session.delete(audit_status)

        # Delete the mapping
        session.delete(mapping)
        session.commit()

        return {
            "id": mapping.id,
            "audit_pipeline": mapping.audit_pipeline,
            "event_id": mapping.event_id,
            "metric_id": mapping.metric_id,
            "user_audit_id": mapping.user_audit_id,
            "message": "Audit pipeline events mapping deleted successfully"
        }

    except HTTPException:
        session.rollback()
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=400, detail=f"Error deleting mapping: {str(e)}")


@router.get("/all", response_model=EventsDetailedListResponse)
def list_events(
    session: SessionDep,
    current_user = Depends(get_current_user),
    page: int = 1,
    page_size: int = 100,
    audit_id: Optional[int] = None,
    user_id: Optional[str] = None,
    sort_by: SortBy = Query(SortBy.likelihood, description="Sort by field"),
    sort_order: SortOrder = Query(SortOrder.desc, description="Sort order"),
    user_defined_only: Optional[bool] = None,
    templates_only: Optional[bool] = None,
    category: Optional[str] = None
):
    """
    Enhanced version of list_events with additional filtering.

    NOTE: audit_id is strongly recommended to ensure proper data isolation.
    Without audit_id, some features may not work correctly.
    """
    return events_service.list_events_with_details(
        current_user_id=current_user.id,
        session=session,
        page=page,
        page_size=page_size,
        audit_id=audit_id,
        user_id=user_id,
        sort_by=sort_by.value,
        sort_order=sort_order.value,
        user_defined_only=user_defined_only,
        templates_only=templates_only,
        category=category
    )

@router.put("/{event_id}", response_model=Events)
def update_event(
    event_id: int, 
    event_update: EventsUpdate, 
    session: SessionDep,
    current_user = Depends(get_current_user)
):
    """Legacy update endpoint - use comprehensive update for full functionality"""
    try:
        # Update the base event
        db_event = events_service.update_event(event_id=event_id, event_update=event_update, session=session)
        return db_event
    except HTTPException:
        session.rollback()
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=400, detail=f"Error updating event: {str(e)}")

@router.put("/{event_id}/customise", response_model=EventDetailWithCustomisations)
def customise_event_values(
    event_id: int,
    update_data: EventsCustomUpdate,
    session: SessionDep,
    current_user = Depends(get_current_user)
):
    """Update event values with user-specific customisations"""
    try:
        return events_service.customise_event_values_simple(
            event_id=event_id,
            user_id=current_user.id,
            update_data=update_data,
            session=session
        )
    except HTTPException:
        session.rollback()
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=400, detail=f"Failed to update event customisation: {str(e)}")

# Add endpoint for audit-specific event customisations
@router.put("/{event_id}/customise/{audit_id}", response_model=EventDetailWithCustomisations)
def customise_event_values_for_audit_endpoint(
    event_id: int,
    audit_id: int,
    update_data: EventsCustomUpdate,
    session: SessionDep,
    current_user = Depends(get_current_user)
):
    """Update event values with user-specific customisations for a specific audit"""
    try:
        return events_service.customise_event_values_for_audit(
            event_id=event_id,
            audit_id=audit_id,
            user_id=current_user.id,
            update_data=update_data,
            session=session
        )
    except HTTPException:
        session.rollback()
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=400, detail=f"Failed to update event customisation: {str(e)}")

@router.get("/", response_model=List[Events])
def list_events_simple(session: SessionDep, skip: int = 0, limit: int = 100):
    """List all events with pagination"""
    statement = select(Events).offset(skip).limit(limit)
    events = session.exec(statement).all()
    return events

@router.delete("/{event_id}")
def delete_event(event_id: int, session: SessionDep):
    """Delete an event and set event_id to null in dependent mappings"""
    try:
        message = events_service.delete_event(event_id=event_id, session=session)
        return message
        
    except HTTPException:
        session.rollback()
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=400, detail=f"Error deleting event: {str(e)}")

@router.get("/by-audit/{audit_id}", response_model=EventsListResponse)
def get_events_by_audit(
    audit_id: int,
    session: SessionDep,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100)
):
    """Get all events for a specific audit"""
    # Verify audit exists
    audit = session.get(Audit, audit_id)
    if not audit:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Audit with ID {audit_id} not found"
        )
    
    return list_events(
        session=session,
        page=page,
        page_size=page_size,
        audit_id=audit_id
    )

@router.get("/by-category/{category_id}", response_model=EventsListResponse)
def get_events_by_category(
    category_id: int,
    session: SessionDep,
    page: int = 0, 
    page_size: int = 100
):
    """Get all events for a specific category"""
    # Verify category exists
    category = session.get(EventsCategory, category_id)
    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Category with ID {category_id} not found"
        )
    
    return list_events(
        session=session,
        page=page,
        page_size=page_size,
        category_id=category_id
    )

# ============= BATCH OPERATIONS =============

@router.post("/batch/delete")
def batch_delete_events(
    event_ids: List[int],
    session: SessionDep,
    current_user = Depends(get_current_user)
):
    """Delete multiple events at once"""
    try:
        deleted_count = 0
        errors = []
        
        for event_id in event_ids:
            try:
                message = events_service.delete_event(event_id=event_id, session=session)
                deleted_count += 1
            except Exception as e:
                errors.append({
                    "event_id": event_id,
                    "error": str(e)
                })
        
        return {
            "message": f"Batch deletion completed",
            "deleted_events": deleted_count,
            "errors": errors,
            "total_processed": len(event_ids),
            "successful": deleted_count,
            "failed": len(errors)
        }
        
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=400, detail=f"Error in batch deletion: {str(e)}")

# ============= STATISTICS AND ANALYTICS =============

@router.get("/statistics/summary", response_model=Dict[str, Any])
def get_events_statistics(
    session: SessionDep,
    current_user = Depends(get_current_user),
    audit_id: Optional[int] = None
):
    """Get statistics using effective event values"""
    try:
        # Get user_audit_id
        user_audit_id = None
        if audit_id:
            user_audit_mapping = session.exec(
                select(MappingAuditUser.id).where(
                    MappingAuditUser.audit_id == audit_id,
                    MappingAuditUser.user_id == current_user.id
                )
            ).first()
            user_audit_id = user_audit_mapping
        
        # Get events (keep your existing query logic)
        events_query = select(Events)
        if audit_id:
            events_query = events_query.join(MappingEventsAuditStatus).where(
                MappingEventsAuditStatus.audit_id == audit_id
            )
        
        events = session.exec(events_query).all()
        
        # Calculate statistics using effective values
        risk_distribution = {"low": 0, "medium": 0, "high": 0}
        impact_distribution = {"positive": 0, "negative": 0, "neutral": 0}
        
        total_likelihood = 0
        total_magnitude = 0  
        total_valence = 0
        
        for event in events:
            # Get effective values for this event
            if user_audit_id:
                effective_values, is_customised = events_service.get_effective_event_values(session, user_audit_id, event.id)
            else:
                effective_values = {
                    'likelihood': event.likelihood,
                    'magnitude': event.magnitude,
                    'valence': event.valence
                }
            
            # Use effective values for calculations
            likelihood = effective_values['likelihood']
            magnitude = effective_values['magnitude']
            valence = effective_values['valence']
            
            risk_level = events_service.determine_risk_level(likelihood, magnitude)
            impact_type = events_service.determine_impact_type(valence)
            
            risk_distribution[risk_level] += 1
            impact_distribution[impact_type] += 1
            
            total_likelihood += likelihood
            total_magnitude += magnitude
            total_valence += valence
        
        event_count = len(events)
        
        return {
            "total_events": event_count,
            "risk_distribution": risk_distribution,
            "impact_distribution": impact_distribution,
            "average_likelihood": total_likelihood / event_count if event_count > 0 else 0,
            "average_magnitude": total_magnitude / event_count if event_count > 0 else 0,
            "average_valence": total_valence / event_count if event_count > 0 else 0,
            "audit_id": audit_id
        }
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error getting statistics: {str(e)}")

# ============= MIGRATION HELPERS =============

@router.post("/migration/create-default-types")
def create_default_event_types(
    session: SessionDep,
    current_user = Depends(get_current_user)
):
    """Create EventType entries for existing events that don't have them"""
    try:
        # Find events without event types
        events_without_types = session.exec(
            select(Events)
            .outerjoin(EventType, Events.id == EventType.event_id)
            .where(EventType.id.is_(None))
        ).all()
        
        created_count = 0
        for event in events_without_types:
            event_type = EventType(
                event_id=event.id,
                is_user_defined=True,  # Default assumption
                created_by_user_id=current_user.id,
                is_template=False,
                category=None
            )
            session.add(event_type)
            created_count += 1
        
        session.commit()
        
        return {
            "message": f"Created EventType entries for {created_count} events",
            "created_count": created_count
        }
        
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=400, detail=f"Error in migration: {str(e)}")