import uuid
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import col, delete, func, select

from src.api.deps import (
    SessionDep, get_current_active_superuser, get_current_instigator_or_superuser,
)

from src.models import *
from src.services.audit_service import mappings_service

router = APIRouter(prefix="/mappings", tags=["Mappings"])

# USER-AUDIT MAPPINGS
@router.post("/user-audit/")
def add_user_audit_mapping(user_id: uuid.UUID, audit_id: int, session: SessionDep, current_user: User = Depends(get_current_instigator_or_superuser)):
    """Add a user-audit mapping (superuser only)"""
    try:
        message = mappings_service.add_user_audit_mapping(user_id=user_id, audit_id=audit_id, session=session)
        return message

    except HTTPException:
        session.rollback()
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=400, detail=f"Error creating user-audit mapping: {str(e)}")

@router.delete("/user-audit/")
def remove_user_audit_mapping(user_id: uuid.UUID, audit_id: int, session: SessionDep, current_user: User = Depends(get_current_instigator_or_superuser)):
    """Remove a user-audit mapping (superuser only)"""
    try:
        message = mappings_service.remove_user_audit_mapping(user_id=user_id, audit_id=audit_id, session=session)
        return message

    except HTTPException:
        session.rollback()
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=400, detail=f"Error deleting user-audit mapping: {str(e)}")

# USER-EVENT MAPPINGS
@router.post("/user-event/")
def add_user_event_mapping(user_audit_id: int, event_id: int, session: SessionDep, current_user: User = Depends(get_current_instigator_or_superuser)):
    """Add a user-event mapping (superuser only)"""
    try:
        message = mappings_service.add_user_event_mapping(user_audit_id=user_audit_id, event_id=event_id, session=session)
        return message

    except HTTPException:
        session.rollback()
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=400, detail=f"Error creating user-event mapping: {str(e)}")

@router.delete("/user-event/")
def remove_user_event_mapping(user_audit_id: int, event_id: int, session: SessionDep, current_user: User = Depends(get_current_instigator_or_superuser)):
    """Remove a user-event mapping (superuser only)"""
    try:
        message = mappings_service.remove_user_event_mapping(user_audit_id=user_audit_id, event_id=event_id, session=session)
        return message

    except HTTPException:
        session.rollback()
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=400, detail=f"Error deleting user-event mapping: {str(e)}")

# EVENT-ENTITY MAPPINGS
@router.post("/event-entity/")
def add_event_entity_mapping(
    event_id: int,
    entity_id: int,
    audit_id: Optional[int],
    user_audit_id: Optional[int],
    session: SessionDep,
    current_user: User = Depends(get_current_instigator_or_superuser)
):
    """Add an event-entity mapping (superuser only)"""
    try:
        message = mappings_service.add_event_entity_mapping(
            event_id=event_id,
            entity_id=entity_id,
            audit_id=audit_id,
            user_audit_id=user_audit_id,
            session=session
        )
        return message

    except HTTPException:
        session.rollback()
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=400, detail=f"Error creating event-entity mapping: {str(e)}")

@router.delete("/event-entity/")
def remove_event_entity_mapping(event_id: int, entity_id: int, session: SessionDep, current_user: User = Depends(get_current_instigator_or_superuser)):
    """Remove an event-entity mapping (superuser only)"""
    try:
        message = mappings_service.remove_event_entity_mapping(event_id=event_id, entity_id=entity_id, session=session)
        return message

    except HTTPException:
        session.rollback()
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=400, detail=f"Error deleting event-entity mapping: {str(e)}")

# METRIC-EVENT MAPPINGS
@router.post("/metric-event/")
def add_metric_event_mapping(
    metric_id: int,
    event_id: int,
    user_audit_id: Optional[int],
    values_id: Optional[int],
    session: SessionDep,
    current_user: User = Depends(get_current_instigator_or_superuser)
):
    """Add a metric-event mapping (superuser only)"""
    try:
        message = mappings_service.add_metric_event_mapping(
            metric_id=metric_id,
            event_id=event_id,
            user_audit_id=user_audit_id,
            values_id=values_id,
            session=session
        )
        return message

    except HTTPException:
        session.rollback()
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=400, detail=f"Error creating metric-event mapping: {str(e)}")

@router.delete("/metric-event/")
def remove_metric_event_mapping(metric_id: int, event_id: int, session: SessionDep, current_user: User = Depends(get_current_instigator_or_superuser)):
    """Remove a metric-event mapping (superuser only)"""
    try:
        message = mappings_service.remove_metric_event_mapping(metric_id=metric_id, event_id=event_id, session=session)
        return message

    except HTTPException:
        session.rollback()
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=400, detail=f"Error deleting metric-event mapping: {str(e)}")

# EVENT-CATEGORY MAPPINGS
@router.post("/event-category/")
def add_event_category_mapping(event_id: int, category_id: int, session: SessionDep, current_user: User = Depends(get_current_instigator_or_superuser)):
    """Add an event-category mapping (superuser only)"""
    try:
        message = mappings_service.add_event_category_mapping(event_id=event_id, category_id=category_id, session=session)
        return message

    except HTTPException:
        session.rollback()
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=400, detail=f"Error creating event-category mapping: {str(e)}")

@router.delete("/event-category/")
def remove_event_category_mapping(event_id: int, category_id: int, session: SessionDep, current_user: User = Depends(get_current_instigator_or_superuser)):
    """Remove an event-category mapping (superuser only)"""
    try:
        message = mappings_service.remove_event_category_mapping(event_id=event_id, category_id=category_id, session=session)
        return message

    except HTTPException:
        session.rollback()
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=400, detail=f"Error deleting event-category mapping: {str(e)}")

# EVENT-AUDIT-STATUS MAPPINGS
@router.post("/event-audit-status/")
def add_event_audit_status_mapping(
    event_id: int,
    audit_id: int,
    user_audit_id: Optional[int],
    recommendation: Optional[str],
    status: Optional[int],
    session: SessionDep,
    current_user: User = Depends(get_current_instigator_or_superuser)
):
    """Add an event-audit-status mapping (superuser only)"""
    try:
        message = mappings_service.add_event_audit_status_mapping(
            event_id=event_id,
            audit_id=audit_id,
            user_audit_id=user_audit_id,
            recommendation=recommendation,
            status=status,
            session=session
        )
        return message

    except HTTPException:
        session.rollback()
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=400, detail=f"Error creating event-audit-status mapping: {str(e)}")

@router.delete("/event-audit-status/")
def remove_event_audit_status_mapping(event_id: int, audit_id: int, session: SessionDep, current_user: User = Depends(get_current_instigator_or_superuser)):
    """Remove an event-audit-status mapping (superuser only)"""
    try:
        message = mappings_service.remove_event_audit_status_mapping(event_id=event_id, audit_id=audit_id, session=session)
        return message

    except HTTPException:
        session.rollback()
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=400, detail=f"Error deleting event-audit-status mapping: {str(e)}")

# AUDIT-MODEL MAPPINGS
@router.post("/audit-model/")
def add_audit_model_mapping(model_id: int, audit_id: int, session: SessionDep, current_user: User = Depends(get_current_instigator_or_superuser)):
    """Add an audit-model mapping (superuser only)"""
    try:
        message = mappings_service.add_audit_model_mapping(model_id=model_id, audit_id=audit_id, session=session)
        return message

    except HTTPException:
        session.rollback()
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=400, detail=f"Error creating audit-model mapping: {str(e)}")

@router.delete("/audit-model/")
def remove_audit_model_mapping(model_id: int, audit_id: int, session: SessionDep, current_user: User = Depends(get_current_instigator_or_superuser)):
    """Remove an audit-model mapping (superuser only)"""
    try:
        message = mappings_service.remove_audit_model_mapping(model_id=model_id, audit_id=audit_id, session=session)
        return message

    except HTTPException:
        session.rollback()
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=400, detail=f"Error deleting audit-model mapping: {str(e)}")

# AUDIT-APPLICATION MAPPINGS
@router.post("/audit-application/")
def add_audit_application_mapping(audit_id: int, application_id: int, session: SessionDep, current_user: User = Depends(get_current_instigator_or_superuser)):
    """Add an audit-application mapping (superuser only)"""
    try:
        message = mappings_service.add_audit_application_mapping(audit_id=audit_id, application_id=application_id, session=session)
        return message

    except HTTPException:
        session.rollback()
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=400, detail=f"Error creating audit-application mapping: {str(e)}")

@router.delete("/audit-application/")
def remove_audit_application_mapping(audit_id: int, application_id: int, session: SessionDep, current_user: User = Depends(get_current_instigator_or_superuser)):
    """Remove an audit-application mapping (superuser only)"""
    try:
        message = mappings_service.remove_audit_application_mapping(audit_id=audit_id, application_id=application_id, session=session)
        return message

    except HTTPException:
        session.rollback()
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=400, detail=f"Error deleting audit-application mapping: {str(e)}")
