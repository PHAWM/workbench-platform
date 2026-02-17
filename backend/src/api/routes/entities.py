import uuid
from typing import Any, List

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import col, delete, func, select

from src.api.deps import (
    SessionDep,get_current_user
)

from src.models import *
from src.services.audit_service import entinty_service

router = APIRouter(prefix="/entities", tags=["Entities"])

@router.post("/")
def create_entity(name: str, num_individuals: int, session: SessionDep):
    """Create a new entity"""
    try:
        db_entity = entinty_service.create_entity(name=name, num_individuals=num_individuals, session=session)
        
        return db_entity
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=400, detail=f"Error creating entity: {str(e)}")

@router.get("/{entity_id}", response_model=Entities)
def get_entity(entity_id: int, session: SessionDep):
    """Get an entity by ID"""
    statement = select(Entities).where(Entities.id == entity_id)
    entity = session.exec(statement).first()
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")
    return entity

@router.get("/by-audit/{audit_id}", response_model=List[Entities])
def list_entities(audit_id:int, session: SessionDep, skip: int = 0, limit: int = 100, current_user: User = Depends(get_current_user)):
    """
    List all entities for a specific audit.
    Returns entities from:
    1. Audit instigator (role_id = 1) for this audit
    2. Current auditor for this audit
    """
    try:
        # Verify user has access to this audit
        user_audit_mapping = session.exec(
            select(MappingAuditUser)
            .where(
                MappingAuditUser.audit_id == audit_id,
                MappingAuditUser.user_id == current_user.id
            )
        ).first()

        if not user_audit_mapping:
            raise HTTPException(status_code=403, detail="Access denied: User does not have access to this audit")

        # Get entities from MappingEventsEntities for:
        # 1. Current user's entities (user_audit_id = current user's audit mapping)
        # 2. Audit instigator's entities (role_id = 1)

        # First, get the audit instigator's user_audit_id for this specific audit
        audit_instigator_mapping = session.exec(
            select(MappingAuditUser.id)
            .join(AuditRoles, MappingAuditUser.roles_id == AuditRoles.id)
            .where(
                MappingAuditUser.audit_id == audit_id,
                AuditRoles.id == 1  # Audit instigator role
            )
        ).first()

        # Build the query to get entities
        # Include entities created by either the current user OR the audit instigator
        allowed_user_audit_ids = [user_audit_mapping.id]
        if audit_instigator_mapping:
            allowed_user_audit_ids.append(audit_instigator_mapping)

        entities = session.exec(
            select(Entities)
            .join(MappingEventsEntities, MappingEventsEntities.entity_id == Entities.id)
            .where(
                MappingEventsEntities.audit_id == audit_id,
                MappingEventsEntities.user_audit_id.in_(allowed_user_audit_ids)
            )
            .distinct()  # Avoid duplicates if entity appears multiple times
            .offset(skip)
            .limit(limit)
        ).all()

        return entities
    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=400, detail=f"Error retrieving entities: {str(e)}")
    

@router.put("/{entity_id}", response_model=Entities)
def update_entity(entity_id: int, entity_update: EntitiesUpdate, session: SessionDep):
    """Update an existing entity"""
    try:
        db_entity = entinty_service.update_entity(entity_id=entity_id, entity_update=entity_update, session=session)
        
        return db_entity
    except HTTPException:
        session.rollback()
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=400, detail=f"Error updating entity: {str(e)}")

@router.delete("/{entity_id}")
def delete_entity(entity_id: int, session: SessionDep):
    """Delete an entity and set entity_id to null in dependent mappings"""
    try:
        message = entinty_service.delete_entity(entity_id=entity_id, session=session)
        return message
    except HTTPException:
        session.rollback()
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=400, detail=f"Error deleting entity: {str(e)}")