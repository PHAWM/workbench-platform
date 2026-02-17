"""Event deletion service functions"""
from typing import Any, Dict
from fastapi import HTTPException
from sqlmodel import Session, select

from src.models import *


def delete_event(event_id: int, session: Session) -> Dict[str, Any]:
    """Delete an event and handle cascade to dependent mappings."""
    statement = select(Events).where(Events.id == event_id)
    db_event = session.exec(statement).first()

    if not db_event:
        raise HTTPException(status_code=404, detail="Event not found")

    # Set event_id to null in dependent mappings
    user_mappings = session.exec(select(MappingUserEvents).where(MappingUserEvents.event_id == event_id)).all()
    entity_mappings = session.exec(select(MappingEventsEntities).where(MappingEventsEntities.event_id == event_id)).all()
    metric_mappings = session.exec(select(MappingMetricsEvents).where(MappingMetricsEvents.event_id == event_id)).all()

    for mapping in user_mappings + entity_mappings + metric_mappings:
        mapping.event_id = None
        session.add(mapping)

    session.delete(db_event)
    session.commit()

    total_affected = len(user_mappings) + len(entity_mappings) + len(metric_mappings)
    if total_affected > 0:
        return {"message": f"Event deleted successfully. {total_affected} mapping entries had their event_id set to null."}
    return {"message": "Event deleted successfully"}
