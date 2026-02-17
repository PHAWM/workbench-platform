import uuid
from typing import Any
from fastapi import HTTPException
from sqlmodel import Session, select
from src.models import *

def add_user_audit_mapping(user_id: uuid.UUID, audit_id: int, session: Session):
    """Add mapping between user and audit via AuditUser table"""
    # Check if mapping already exists
    existing = session.exec(
        select(MappingAuditUser).where(
            MappingAuditUser.user_id == user_id,
            MappingAuditUser.audit_id == audit_id
        )
    ).first()
    
    if existing:
        return {"message": "Mapping already exists", "mapping": existing}
    
    db_mapping = MappingAuditUser(user_id=user_id, audit_id=audit_id)
    session.add(db_mapping)
    session.commit()
    session.refresh(db_mapping)
    
    return {"message": "Mapping created successfully", "mapping": db_mapping}

def add_user_event_mapping(user_audit_id: int, event_id: int, session: Session):
    """Add mapping between user (via AuditUser) and event"""
    # Check if mapping already exists
    existing = session.exec(
        select(MappingUserEvents).where(
            MappingUserEvents.user_audit_id == user_audit_id,
            MappingUserEvents.event_id == event_id
        )
    ).first()
    
    if existing:
        return {"message": "Mapping already exists", "mapping": existing}
    
    db_mapping = MappingUserEvents(user_audit_id=user_audit_id, event_id=event_id)
    session.add(db_mapping)
    session.commit()
    session.refresh(db_mapping)
    
    return {"message": "Mapping created successfully", "mapping": db_mapping}

def add_event_entity_mapping(event_id: int, entity_id: int, audit_id: int = None, user_audit_id: int = None, session: Session = None):
    """Add mapping between event and entity"""
    # Check if mapping already exists
    existing = session.exec(
        select(MappingEventsEntities).where(
            MappingEventsEntities.event_id == event_id,
            MappingEventsEntities.entity_id == entity_id
        )
    ).first()
    
    if existing:
        return {"message": "Mapping already exists", "mapping": existing}
    
    db_mapping = MappingEventsEntities(
        event_id=event_id, 
        entity_id=entity_id,
        audit_id=audit_id,
        user_audit_id=user_audit_id
    )
    session.add(db_mapping)
    session.commit()
    session.refresh(db_mapping)
    
    return {"message": "Mapping created successfully", "mapping": db_mapping}

def add_metric_event_mapping(metric_id: int, event_id: int, user_audit_id: int = None, values_id: int = None, session: Session = None):
    """Add mapping between metric and event"""
    # Check if mapping already exists
    existing = session.exec(
        select(MappingMetricsEvents).where(
            MappingMetricsEvents.metric_id == metric_id,
            MappingMetricsEvents.event_id == event_id
        )
    ).first()
    
    if existing:
        return {"message": "Mapping already exists", "mapping": existing}
    
    db_mapping = MappingMetricsEvents(
        metric_id=metric_id, 
        event_id=event_id,
        user_audit_id=user_audit_id,
        values_id=values_id
    )
    session.add(db_mapping)
    session.commit()
    session.refresh(db_mapping)
    
    return {"message": "Mapping created successfully", "mapping": db_mapping}

def add_event_category_mapping(event_id: int, category_id: int, session: Session):
    """Add mapping between event and category"""
    # Check if mapping already exists
    existing = session.exec(
        select(MappingEventsCategory).where(
            MappingEventsCategory.event_id == event_id,
            MappingEventsCategory.category_id == category_id
        )
    ).first()
    
    if existing:
        return {"message": "Mapping already exists", "mapping": existing}
    
    db_mapping = MappingEventsCategory(event_id=event_id, category_id=category_id)
    session.add(db_mapping)
    session.commit()
    session.refresh(db_mapping)
    
    return {"message": "Mapping created successfully", "mapping": db_mapping}

def add_event_audit_status_mapping(event_id: int, audit_id: int, user_audit_id: int = None, recommendation: str = None, status: int = None, session: Session = None):
    """Add mapping for event audit status"""
    # Check if mapping already exists
    existing = session.exec(
        select(MappingEventsAuditStatus).where(
            MappingEventsAuditStatus.event_id == event_id,
            MappingEventsAuditStatus.audit_id == audit_id
        )
    ).first()
    
    if existing:
        return {"message": "Mapping already exists", "mapping": existing}
    
    db_mapping = MappingEventsAuditStatus(
        event_id=event_id,
        audit_id=audit_id,
        user_audit_id=user_audit_id,
        recommendation=recommendation,
        status=status
    )
    session.add(db_mapping)
    session.commit()
    session.refresh(db_mapping)
    
    return {"message": "Mapping created successfully", "mapping": db_mapping}

def add_audit_model_mapping(model_id: int, audit_id: int, session: Session):
    """Add mapping between audit and model"""
    # Check if mapping already exists
    existing = session.exec(
        select(MappingAuditModel).where(
            MappingAuditModel.model_id == model_id,
            MappingAuditModel.audit_id == audit_id
        )
    ).first()
    
    if existing:
        return {"message": "Mapping already exists", "mapping": existing}
    
    db_mapping = MappingAuditModel(model_id=model_id, audit_id=audit_id)
    session.add(db_mapping)
    session.commit()
    session.refresh(db_mapping)
    
    return {"message": "Mapping created successfully", "mapping": db_mapping}

def add_audit_application_mapping(audit_id: int, application_id: int, session: Session):
    """Add mapping between audit and application"""
    # Check if mapping already exists
    existing = session.exec(
        select(MappingAuditApplication).where(
            MappingAuditApplication.audit_id == audit_id,
            MappingAuditApplication.application_id == application_id
        )
    ).first()
    
    if existing:
        return {"message": "Mapping already exists", "mapping": existing}
    
    db_mapping = MappingAuditApplication(audit_id=audit_id, application_id=application_id)
    session.add(db_mapping)
    session.commit()
    session.refresh(db_mapping)
    
    return {"message": "Mapping created successfully", "mapping": db_mapping}

# DELETE FUNCTIONS

def remove_user_audit_mapping(user_id: uuid.UUID, audit_id: int, session: Session):
    """Remove mapping between user and audit"""
    mapping = session.exec(
        select(MappingAuditUser).where(
            MappingAuditUser.user_id == user_id,
            MappingAuditUser.audit_id == audit_id
        )
    ).first()
    
    if not mapping:
        raise HTTPException(status_code=404, detail="User-audit mapping not found")
    
    session.delete(mapping)
    session.commit()
    return {"message": "User-audit mapping deleted successfully"}

def remove_user_event_mapping(user_audit_id: int, event_id: int, session: Session):
    """Remove mapping between user and event"""
    mapping = session.exec(
        select(MappingUserEvents).where(
            MappingUserEvents.user_audit_id == user_audit_id,
            MappingUserEvents.event_id == event_id
        )
    ).first()
    
    if not mapping:
        raise HTTPException(status_code=404, detail="User-event mapping not found")
    
    session.delete(mapping)
    session.commit()
    return {"message": "User-event mapping deleted successfully"}

def remove_event_entity_mapping(event_id: int, entity_id: int, session: Session):
    """Remove mapping between event and entity"""
    mapping = session.exec(
        select(MappingEventsEntities).where(
            MappingEventsEntities.event_id == event_id,
            MappingEventsEntities.entity_id == entity_id
        )
    ).first()
    
    if not mapping:
        raise HTTPException(status_code=404, detail="Event-entity mapping not found")
    
    session.delete(mapping)
    session.commit()
    return {"message": "Event-entity mapping deleted successfully"}

def remove_metric_event_mapping(metric_id: int, event_id: int, session: Session):
    """Remove mapping between metric and event"""
    mapping = session.exec(
        select(MappingMetricsEvents).where(
            MappingMetricsEvents.metric_id == metric_id,
            MappingMetricsEvents.event_id == event_id
        )
    ).first()
    
    if not mapping:
        raise HTTPException(status_code=404, detail="Metric-event mapping not found")
    
    session.delete(mapping)
    session.commit()
    return {"message": "Metric-event mapping deleted successfully"}

def remove_event_category_mapping(event_id: int, category_id: int, session: Session):
    """Remove mapping between event and category"""
    mapping = session.exec(
        select(MappingEventsCategory).where(
            MappingEventsCategory.event_id == event_id,
            MappingEventsCategory.category_id == category_id
        )
    ).first()
    
    if not mapping:
        raise HTTPException(status_code=404, detail="Event-category mapping not found")
    
    session.delete(mapping)
    session.commit()
    return {"message": "Event-category mapping deleted successfully"}

def remove_event_audit_status_mapping(event_id: int, audit_id: int, session: Session):
    """Remove event audit status mapping"""
    mapping = session.exec(
        select(MappingEventsAuditStatus).where(
            MappingEventsAuditStatus.event_id == event_id,
            MappingEventsAuditStatus.audit_id == audit_id
        )
    ).first()
    
    if not mapping:
        raise HTTPException(status_code=404, detail="Event-audit status mapping not found")
    
    session.delete(mapping)
    session.commit()
    return {"message": "Event-audit status mapping deleted successfully"}

def remove_audit_model_mapping(model_id: int, audit_id: int, session: Session):
    """Remove mapping between audit and model"""
    mapping = session.exec(
        select(MappingAuditModel).where(
            MappingAuditModel.model_id == model_id,
            MappingAuditModel.audit_id == audit_id
        )
    ).first()
    
    if not mapping:
        raise HTTPException(status_code=404, detail="Audit-model mapping not found")
    
    session.delete(mapping)
    session.commit()
    return {"message": "Audit-model mapping deleted successfully"}

def remove_audit_application_mapping(audit_id: int, application_id: int, session: Session):
    """Remove mapping between audit and application"""
    mapping = session.exec(
        select(MappingAuditApplication).where(
            MappingAuditApplication.audit_id == audit_id,
            MappingAuditApplication.application_id == application_id
        )
    ).first()
    
    if not mapping:
        raise HTTPException(status_code=404, detail="Audit-application mapping not found")
    
    session.delete(mapping)
    session.commit()
    return {"message": "Audit-application mapping deleted successfully"}