"""Event update service functions"""
from typing import Any, Dict, Optional
from fastapi import HTTPException
from sqlmodel import Session, select

from src.models import *


def update_event(event_id: int, event_update: EventsUpdate, session: Session):
    """Update an existing event."""
    statement = select(Events).where(Events.id == event_id)
    db_event = session.exec(statement).first()

    if not db_event:
        raise HTTPException(status_code=404, detail="Event not found")

    update_data = event_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_event, field, value)

    session.add(db_event)
    session.commit()
    session.refresh(db_event)

    return db_event


def update_event_values(
    event_id: int,
    audit_id: int,
    user_id: int,
    likelihood: Optional[float],
    magnitude: Optional[float],
    valence: Optional[float],
    session: Session
) -> Dict[str, Any]:
    """
    Update event values - directly if same user/audit, via customisation if different.
    """
    # Get user_audit_id for specific audit
    user_audit_mapping = session.exec(
        select(MappingAuditUser).where(
            MappingAuditUser.user_id == user_id,
            MappingAuditUser.audit_id == audit_id
        )
    ).first()

    if not user_audit_mapping:
        raise HTTPException(status_code=403, detail="User has no access to this audit")

    user_audit_id = user_audit_mapping.id

    # Check if user is the original creator of this event
    event_creator_check = session.exec(
        select(EventType).where(
            EventType.event_id == event_id,
            EventType.created_by_user_id == user_audit_id
        )
    ).first()

    # Check if this is the same audit where the event was created
    event_audit_origin = session.exec(
        select(MappingUserEvents).where(
            MappingUserEvents.event_id == event_id,
            MappingUserEvents.user_audit_id == user_audit_mapping.id
        )
    ).first()

    # If same user AND same audit, update the base event directly
    if event_creator_check and event_audit_origin:
        base_event = session.get(Events, event_id)
        if likelihood is not None:
            base_event.likelihood = likelihood
        if magnitude is not None:
            base_event.magnitude = magnitude
        if valence is not None:
            base_event.valence = valence

        session.add(base_event)
        session.commit()

        return {
            "message": "Event values updated directly",
            "event_id": event_id,
            "updated_directly": True,
            "likelihood": base_event.likelihood,
            "magnitude": base_event.magnitude,
            "valence": base_event.valence
        }

    # Different user or different audit - use customisation
    existing_customisation = session.exec(
        select(UserEventCustomisations).where(
            UserEventCustomisations.user_audit_id == user_audit_mapping.id,
            UserEventCustomisations.event_id == event_id
        )
    ).first()

    if existing_customisation:
        if likelihood is not None:
            existing_customisation.custom_likelihood = likelihood
        if magnitude is not None:
            existing_customisation.custom_magnitude = magnitude
        if valence is not None:
            existing_customisation.custom_valence = valence
        session.add(existing_customisation)
    else:
        new_customisation = UserEventCustomisations(
            user_audit_id=user_audit_mapping.id,
            event_id=event_id,
            custom_likelihood=likelihood,
            custom_magnitude=magnitude,
            custom_valence=valence
        )
        session.add(new_customisation)

    session.commit()

    # Import helper to get effective values
    from .utils import get_effective_event_values
    effective_values, is_customised = get_effective_event_values(session, user_audit_mapping.id, event_id)

    return {
        "message": "Event values updated via customisation",
        "event_id": event_id,
        "updated_directly": False,
        "is_customised": is_customised,
        "likelihood": effective_values['likelihood'],
        "magnitude": effective_values['magnitude'],
        "valence": effective_values['valence']
    }


def update_event_comprehensive(
    event_id: int,
    event_update: 'ComprehensiveEventUpdate',
    user_id: int,
    session: Session
) -> Events:
    """
    Comprehensive event update that handles all related entities in one call.
    """
    # Verify event exists
    event = session.get(Events, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    # Update basic event properties
    if event_update.description is not None:
        event.description = event_update.description
    if event_update.cause is not None:
        event.cause = event_update.cause
    if event_update.reason is not None:
        event.reason = event_update.reason
    if event_update.likelihood is not None:
        event.likelihood = event_update.likelihood
    if event_update.magnitude is not None:
        event.magnitude = event_update.magnitude
    if event_update.valence is not None:
        event.valence = event_update.valence

    session.add(event)

    # Get user audit ID
    user_audit_id = session.exec(
        select(MappingAuditUser).where(
            MappingAuditUser.audit_id == event_update.audit_id,
            MappingAuditUser.user_id == user_id
        )
    ).first()

    if not user_audit_id:
        raise HTTPException(status_code=403, detail="User has no access to this audit")

    # Handle entities updates
    if event_update.entities is not None:
        from sqlmodel import delete as sql_delete

        current_entities = session.exec(
            select(MappingEventsEntities).where(
                MappingEventsEntities.event_id == event_id,
                MappingEventsEntities.audit_id == event_update.audit_id,
                MappingEventsEntities.user_audit_id == user_audit_id.id
            )
        ).all()

        current_entity_ids = {e.entity_id for e in current_entities}
        new_entity_ids = {e.entity_id for e in event_update.entities}

        # Remove entities no longer in the list
        entities_to_remove = current_entity_ids - new_entity_ids
        for entity_id in entities_to_remove:
            session.exec(
                sql_delete(MappingEventsEntities).where(
                    MappingEventsEntities.event_id == event_id,
                    MappingEventsEntities.entity_id == entity_id,
                    MappingEventsEntities.audit_id == event_update.audit_id,
                    MappingEventsEntities.user_audit_id == user_audit_id.id
                )
            )

        # Add new entities
        entities_to_add = new_entity_ids - current_entity_ids
        for entity_id in entities_to_add:
            new_mapping = MappingEventsEntities(
                audit_id=event_update.audit_id,
                event_id=event_id,
                entity_id=entity_id,
                user_audit_id=user_audit_id.id
            )
            session.add(new_mapping)

    # Handle categories updates
    if event_update.categories is not None:
        from sqlmodel import delete as sql_delete

        current_categories = session.exec(
            select(MappingEventsCategory).where(MappingEventsCategory.event_id == event_id)
        ).all()

        current_category_ids = {c.category_id for c in current_categories}
        new_category_ids = {c.category_id for c in event_update.categories}

        categories_to_remove = current_category_ids - new_category_ids
        for category_id in categories_to_remove:
            session.exec(
                sql_delete(MappingEventsCategory).where(
                    MappingEventsCategory.event_id == event_id,
                    MappingEventsCategory.category_id == category_id
                )
            )

        categories_to_add = new_category_ids - current_category_ids
        for category_id in categories_to_add:
            new_mapping = MappingEventsCategory(
                event_id=event_id,
                category_id=category_id
            )
            session.add(new_mapping)

    # Handle users updates
    if event_update.users is not None:
        from sqlmodel import delete as sql_delete

        current_users = session.exec(
            select(MappingUserEvents).where(MappingUserEvents.event_id == event_id)
        ).all()

        current_user_audit_ids = {u.user_audit_id for u in current_users}
        new_user_audit_ids = {u.user_audit_id for u in event_update.users}

        users_to_remove = current_user_audit_ids - new_user_audit_ids
        for user_audit_id_to_remove in users_to_remove:
            session.exec(
                sql_delete(MappingUserEvents).where(
                    MappingUserEvents.event_id == event_id,
                    MappingUserEvents.user_audit_id == user_audit_id_to_remove
                )
            )

        users_to_add = new_user_audit_ids - current_user_audit_ids
        for user_audit_id_to_add in users_to_add:
            new_mapping = MappingUserEvents(
                event_id=event_id,
                user_audit_id=user_audit_id_to_add
            )
            session.add(new_mapping)

    # Commit all changes
    session.commit()

    return event


def customise_event_values_simple(
    event_id: int,
    user_id: int,
    update_data: 'EventsCustomUpdate',
    session: Session
) -> 'EventDetailWithCustomisations':
    """
    Update event values with user-specific customisations.
    Uses the first audit mapping found for the user (simple version).

    Args:
        event_id: The ID of the event to customise
        user_id: The ID of the user making the customisation
        update_data: The customisation values (likelihood, magnitude, valence)
        session: Database session

    Returns:
        EventDetailWithCustomisations with effective values and flags

    Raises:
        HTTPException: If user has no audit mapping or update fails
    """
    # Get user_audit_id - uses the first audit mapping found
    user_audit_mapping = session.exec(
        select(MappingAuditUser).where(
            MappingAuditUser.user_id == user_id
        )
    ).first()

    if not user_audit_mapping:
        raise HTTPException(status_code=403, detail="User audit mapping not found")

    # Check if customisation already exists
    existing_customisation = session.exec(
        select(UserEventCustomisations).where(
            UserEventCustomisations.user_audit_id == user_audit_mapping.id,
            UserEventCustomisations.event_id == event_id
        )
    ).first()

    if existing_customisation:
        # Update existing customisation
        if update_data.likelihood is not None:
            existing_customisation.custom_likelihood = update_data.likelihood
        if update_data.magnitude is not None:
            existing_customisation.custom_magnitude = update_data.magnitude
        if update_data.valence is not None:
            existing_customisation.custom_valence = update_data.valence
        session.add(existing_customisation)
    else:
        # Create new customisation
        new_customisation = UserEventCustomisations(
            user_audit_id=user_audit_mapping.id,
            event_id=event_id,
            custom_likelihood=update_data.likelihood,
            custom_magnitude=update_data.magnitude,
            custom_valence=update_data.valence
        )
        session.add(new_customisation)
        session.flush()

    session.commit()

    # Import helper to get effective values
    from .utils import get_effective_event_values
    effective_values, _ = get_effective_event_values(session, user_audit_mapping.id, event_id)

    # Get base event details
    event = session.get(Events, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    # Import model for return type
    from src.models import EventDetailWithCustomisations

    return EventDetailWithCustomisations(
        id=event_id,
        name=event.name,
        description=event.description,
        cause=event.cause,
        reason=event.reason,

        # Effective values (custom or default)
        likelihood=effective_values["likelihood"],
        magnitude=effective_values["magnitude"],
        valence=effective_values["valence"],

        # Customisation flags
        is_likelihood_customised=update_data.likelihood is not None,
        is_magnitude_customised=update_data.magnitude is not None,
        is_valence_customised=update_data.valence is not None,
    )


def customise_event_values_for_audit(
    event_id: int,
    audit_id: int,
    user_id: int,
    update_data: 'EventsCustomUpdate',
    session: Session
) -> 'EventDetailWithCustomisations':
    """
    Update event values with user-specific customisations for a specific audit.

    Args:
        event_id: The ID of the event to customise
        audit_id: The ID of the audit context
        user_id: The ID of the user making the customisation
        update_data: The customisation values (likelihood, magnitude, valence)
        session: Database session

    Returns:
        EventDetailWithCustomisations with effective values and flags

    Raises:
        HTTPException: If user has no access to audit or event not found
    """
    # Get user_audit_id for specific audit
    user_audit_mapping = session.exec(
        select(MappingAuditUser).where(
            MappingAuditUser.user_id == user_id,
            MappingAuditUser.audit_id == audit_id
        )
    ).first()

    if not user_audit_mapping:
        raise HTTPException(status_code=403, detail="User has no access to this audit")

    # Verify event exists and is associated with this audit
    event_audit_access = session.exec(
        select(MappingEventsAuditStatus).where(
            MappingEventsAuditStatus.event_id == event_id,
            MappingEventsAuditStatus.audit_id == audit_id,
            MappingEventsAuditStatus.user_audit_id == user_audit_mapping.id
        )
    ).first()

    if not event_audit_access:
        raise HTTPException(status_code=404, detail="Event not found in this audit or access denied")

    # Check if customisation already exists
    existing_customisation = session.exec(
        select(UserEventCustomisations).where(
            UserEventCustomisations.user_audit_id == user_audit_mapping.id,
            UserEventCustomisations.event_id == event_id
        )
    ).first()

    if existing_customisation:
        # Update existing customisation
        if update_data.likelihood is not None:
            existing_customisation.custom_likelihood = update_data.likelihood
        if update_data.magnitude is not None:
            existing_customisation.custom_magnitude = update_data.magnitude
        if update_data.valence is not None:
            existing_customisation.custom_valence = update_data.valence
        session.add(existing_customisation)
    else:
        # Create new customisation
        new_customisation = UserEventCustomisations(
            user_audit_id=user_audit_mapping.id,
            event_id=event_id,
            custom_likelihood=update_data.likelihood,
            custom_magnitude=update_data.magnitude,
            custom_valence=update_data.valence
        )
        session.add(new_customisation)
        session.flush()

    session.commit()

    # Import helper to get effective values
    from .utils import get_effective_event_values
    effective_values, _ = get_effective_event_values(session, user_audit_mapping.id, event_id)

    # Get base event details
    event = session.get(Events, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    # Import model for return type
    from src.models import EventDetailWithCustomisations

    return EventDetailWithCustomisations(
        id=event_id,
        name=event.name,
        description=event.description,
        cause=event.cause,
        reason=event.reason,

        # Effective values (custom or default)
        likelihood=effective_values["likelihood"],
        magnitude=effective_values["magnitude"],
        valence=effective_values["valence"],

        # Customisation flags
        is_likelihood_customised=update_data.likelihood is not None,
        is_magnitude_customised=update_data.magnitude is not None,
        is_valence_customised=update_data.valence is not None,
    )
