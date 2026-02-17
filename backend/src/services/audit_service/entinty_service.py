import uuid
from typing import Any
from fastapi import HTTPException

from sqlmodel import Session, select

from src.models import *

def create_entity(name: str, num_individuals: int, session: Session):
    db_entity = Entities(
        name=name,
        num_individuals=num_individuals
    )
    session.add(db_entity)
    session.commit()
    session.refresh(db_entity)
    return db_entity

def update_entity(entity_id: int, entity_update: EntitiesUpdate, session: Session):
    statement = select(Entities).where(Entities.id == entity_id)
    db_entity = session.exec(statement).first()
    
    if not db_entity:
        raise HTTPException(status_code=404, detail="Entity not found")
    
    update_data = entity_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_entity, field, value)
    
    session.add(db_entity)
    session.commit()
    session.refresh(db_entity)
    
    return db_entity

def delete_entity(entity_id: int, session: Session):
    statement = select(Entities).where(Entities.id == entity_id)
    db_entity = session.exec(statement).first()
    
    if not db_entity:
        raise HTTPException(status_code=404, detail="Entity not found")
    
    # Set entity_id to null in dependent mappings
    entity_mappings = session.exec(select(MappingEventsEntities).where(MappingEventsEntities.entity_id == entity_id)).all()
    
    session.delete(entity_mappings)
    session.delete(db_entity)
    session.commit()
    
    if entity_mappings:
        return {"message": f"Entity deleted successfully. {len(entity_mappings)} mapping entries had their entity_id set to null."}
    return {"message": "Entity deleted successfully"}