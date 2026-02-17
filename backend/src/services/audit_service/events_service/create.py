"""Event creation service functions"""
from typing import Any, Dict, Optional
from fastapi import HTTPException
from sqlmodel import Session, select

from src.models import *


def create_event(description: str, reason: str, cause: str, likelihood: float, magnitude: float, valence: float, session: Session):
    """Create a basic event record."""
    db_event = Events(
        description=description,
        reason=reason,
        cause=cause,
        likelihood=likelihood,
        magnitude=magnitude,
        valence=valence,
    )
    session.add(db_event)
    session.commit()
    session.refresh(db_event)

    return db_event


def create_user_feature(feature_name: str, audit_id: int, user_id: int, session: Session) -> Dict[str, Any]:
    """
    Create a new user-specific feature for an audit.
    This allows users to add custom features beyond what's in the dataset.
    """
    # Verify user has access to this audit
    user_audit = session.exec(
        select(MappingAuditUser).where(
            MappingAuditUser.audit_id == audit_id,
            MappingAuditUser.user_id == user_id
        )
    ).first()

    if not user_audit:
        raise HTTPException(
            status_code=403,
            detail="User does not have access to this audit"
        )

    # Check if feature already exists in UnderlyingFeatures
    existing_feature = session.exec(
        select(UnderlyingFeatures).where(
            UnderlyingFeatures.feature_name == feature_name
        )
    ).first()

    if existing_feature:
        feature_id = existing_feature.id
    else:
        # Create new feature
        new_feature = UnderlyingFeatures(feature_name=feature_name)
        session.add(new_feature)
        session.flush()
        feature_id = new_feature.id

    # Check if mapping already exists
    existing_mapping = session.exec(
        select(MappingUserAuditFeatures).where(
            MappingUserAuditFeatures.user_audit_id == user_audit.id,
            MappingUserAuditFeatures.underlying_feature_id == feature_id
        )
    ).first()

    if existing_mapping:
        raise HTTPException(
            status_code=400,
            detail=f"Feature '{feature_name}' already exists for this user in this audit"
        )

    # Create mapping
    user_feature_mapping = MappingUserAuditFeatures(
        user_audit_id=user_audit.id,
        underlying_feature_id=feature_id
    )
    session.add(user_feature_mapping)
    session.commit()

    return {
        "id": feature_id,
        "feature_name": feature_name,
        "audit_id": audit_id,
        "user_audit_id": user_audit.id,
        "message": f"Feature '{feature_name}' created and mapped to user's audit"
    }


def create_user_target_feature(target_feature: str, audit_id: int, user_id: int, session: Session) -> Dict[str, Any]:
    """
    Create a new user-specific target feature for an audit.
    This allows users to add custom target features beyond what's in the dataset.
    """
    # Verify user has access to this audit
    user_audit = session.exec(
        select(MappingAuditUser).where(
            MappingAuditUser.audit_id == audit_id,
            MappingAuditUser.user_id == user_id
        )
    ).first()

    if not user_audit:
        raise HTTPException(
            status_code=403,
            detail="User does not have access to this audit"
        )

    # Check if target feature already exists
    existing_feature = session.exec(
        select(TargetFeatures).where(
            TargetFeatures.target_feature == target_feature
        )
    ).first()

    if existing_feature:
        feature_id = existing_feature.id
    else:
        # Create new target feature
        new_feature = TargetFeatures(
            target_feature=target_feature,
            function_name=None
        )
        session.add(new_feature)
        session.flush()
        feature_id = new_feature.id

    # Check if mapping already exists
    existing_mapping = session.exec(
        select(MappingUserAuditTargetFeatures).where(
            MappingUserAuditTargetFeatures.user_audit_id == user_audit.id,
            MappingUserAuditTargetFeatures.target_feature_id == feature_id
        )
    ).first()

    if existing_mapping:
        raise HTTPException(
            status_code=400,
            detail=f"Target feature '{target_feature}' already exists for this user in this audit"
        )

    # Create mapping
    user_feature_mapping = MappingUserAuditTargetFeatures(
        user_audit_id=user_audit.id,
        target_feature_id=feature_id
    )
    session.add(user_feature_mapping)
    session.commit()

    return {
        "id": feature_id,
        "target_feature": target_feature,
        "function_name": None,
        "audit_id": audit_id,
        "user_audit_id": user_audit.id,
        "message": f"Target feature '{target_feature}' created and mapped to user's audit"
    }


def create_user_entity(name: str, num_individuals: int, audit_id: int, user_id: int, session: Session) -> Dict[str, Any]:
    """
    Create a new user-defined entity for an audit.
    This allows users to add custom entities (groups of affected individuals).
    """
    # Verify user has access to this audit
    user_audit = session.exec(
        select(MappingAuditUser).where(
            MappingAuditUser.audit_id == audit_id,
            MappingAuditUser.user_id == user_id
        )
    ).first()

    if not user_audit:
        raise HTTPException(
            status_code=403,
            detail="User does not have access to this audit"
        )

    # Check if entity already exists
    existing_entity = session.exec(
        select(Entities).where(
            Entities.name == name
        )
    ).first()

    if existing_entity:
        entity_id = existing_entity.id
    else:
        # Create new entity
        new_entity = Entities(
            name=name,
            num_individuals=num_individuals
        )
        session.add(new_entity)
        session.flush()
        entity_id = new_entity.id

    # Check if mapping already exists
    existing_mapping = session.exec(
        select(MappingUserEntities).where(
            MappingUserEntities.user_audit_id == user_audit.id,
            MappingUserEntities.entity_id == entity_id
        )
    ).first()

    if existing_mapping:
        raise HTTPException(
            status_code=400,
            detail=f"Entity '{name}' already exists for this user in this audit"
        )

    # Create mapping
    user_entity_mapping = MappingUserEntities(
        user_audit_id=user_audit.id,
        entity_id=entity_id
    )
    session.add(user_entity_mapping)
    session.commit()

    return {
        "entities_id": entity_id,
        "name": name,
        "num_individuals": num_individuals,
        "audit_id": audit_id,
        "user_audit_id": user_audit.id,
        "message": f"Entity '{name}' created and mapped to user's audit"
    }


def create_user_category(event_name: str, description: Optional[str], audit_id: int, user_id: int, session: Session) -> Dict[str, Any]:
    """
    Create a new user-defined category for an audit.
    This allows users to add custom categories for organizing events.
    """
    # Verify user has access to this audit
    user_audit = session.exec(
        select(MappingAuditUser).where(
            MappingAuditUser.audit_id == audit_id,
            MappingAuditUser.user_id == user_id
        )
    ).first()

    if not user_audit:
        raise HTTPException(
            status_code=403,
            detail="User does not have access to this audit"
        )

    # Check if category already exists
    existing_category = session.exec(
        select(EventsCategory).where(
            EventsCategory.event_name == event_name
        )
    ).first()

    if existing_category:
        category_id = existing_category.id
    else:
        # Create new category
        new_category = EventsCategory(
            event_name=event_name,
            description=description
        )
        session.add(new_category)
        session.flush()
        category_id = new_category.id

    # Check if mapping already exists
    existing_mapping = session.exec(
        select(MappingUserCategories).where(
            MappingUserCategories.user_audit_id == user_audit.id,
            MappingUserCategories.category_id == category_id
        )
    ).first()

    if existing_mapping:
        raise HTTPException(
            status_code=400,
            detail=f"Category '{event_name}' already exists for this user in this audit"
        )

    # Create mapping
    user_category_mapping = MappingUserCategories(
        user_audit_id=user_audit.id,
        category_id=category_id
    )
    session.add(user_category_mapping)
    session.commit()

    return {
        "category_id": category_id,
        "event_name": event_name,
        "description": description,
        "audit_id": audit_id,
        "user_audit_id": user_audit.id,
        "message": f"Category '{event_name}' created and mapped to user's audit"
    }


def create_comprehensive_event(
    event_data: 'ComprehensiveEventCreate',
    user_id: int,
    session: Session
) -> Events:
    """
    Create a new event with related entities, categories, and metrics in one transaction.
    This is the main business logic for comprehensive event creation.
    """
    # Get user audit ID for related mappings
    user_audit_id = session.exec(
        select(MappingAuditUser)
        .where(
            MappingAuditUser.audit_id == event_data.audit_id,
            MappingAuditUser.user_id == user_id
        )
    ).first()

    if not user_audit_id:
        raise HTTPException(
            status_code=403,
            detail="User does not have access to this audit"
        )

    # Create the base event
    new_event = Events(
        name=event_data.name,
        description=event_data.description,
        cause=event_data.cause,
        reason=event_data.reason,
        likelihood=event_data.likelihood,
        magnitude=event_data.magnitude,
        valence=event_data.valence
    )
    session.add(new_event)
    session.commit()
    session.refresh(new_event)

    # Create event type (only ONE per event)
    category_name = "General"
    if event_data.categories and len(event_data.categories) > 0:
        first_category = session.exec(
            select(EventsCategory).where(EventsCategory.id == event_data.categories[0].category_id)
        ).first()
        if first_category:
            category_name = first_category.event_name

    event_type = EventType(
        event_id=new_event.id,
        is_user_defined=event_data.is_user_defined,
        created_by_user_id=user_audit_id.id,
        is_template=event_data.is_template,
        category=category_name
    )
    session.add(event_type)

    # Create entities associations
    if event_data.entities:
        for entity_data in event_data.entities:
            entity_mapping = MappingEventsEntities(
                audit_id=event_data.audit_id,
                event_id=new_event.id,
                entity_id=entity_data.entity_id,
                user_audit_id=user_audit_id.id
            )
            session.add(entity_mapping)

    # Create categories associations
    if event_data.categories:
        for category_data in event_data.categories:
            category_mapping = MappingEventsCategory(
                event_id=new_event.id,
                category_id=category_data.category_id
            )
            session.add(category_mapping)

    # Create metrics associations
    if event_data.metrics:
        for metric_data in event_data.metrics:
            if metric_data.values_id == None:
                is_user = session.exec(
                    select(MappingUserMetrics)
                    .where(MappingUserMetrics.user_audit_id == user_audit_id.id)
                    .where(MappingUserMetrics.metric_id == metric_data.metric_id)
                ).first()

                if is_user:
                    value = MetricsValues(
                        output=None,
                        threshold="Not Set"
                    )
                    session.add(value)
                    session.flush()
                    metric_data.values_id = value.id
                else:
                    # Get audit instigator's metric for THIS specific audit
                    user_metric = session.exec(
                        select(MappingUserMetrics)
                        .join(MappingAuditUser, MappingUserMetrics.user_audit_id == MappingAuditUser.id)
                        .join(AuditRoles, MappingAuditUser.roles_id == AuditRoles.id)
                        .where(MappingUserMetrics.metric_id == metric_data.metric_id)
                        .where(MappingAuditUser.audit_id == event_data.audit_id)
                        .where(AuditRoles.id == 1)
                    ).first()

                    if not user_metric:
                        # No audit instigator metric found, create default value
                        value = MetricsValues(
                            output=None,
                            threshold="Not Set"
                        )
                        session.add(value)
                        session.flush()
                        metric_data.values_id = value.id
                    else:
                        metric_value_id = session.exec(
                            select(MappingMetricsEvents.values_id)
                            .where(MappingMetricsEvents.user_audit_id == user_metric.user_audit_id)
                            .where(MappingMetricsEvents.metric_id == metric_data.metric_id)
                        ).first()
                        metric_data.values_id = metric_value_id

            metric_mapping = MappingMetricsEvents(
                event_id=new_event.id,
                metric_id=metric_data.metric_id,
                values_id=metric_data.values_id,
                user_audit_id=user_audit_id.id
            )
            session.add(metric_mapping)

    # Create user association
    user_mapping = MappingUserEvents(
        event_id=new_event.id,
        user_audit_id=user_audit_id.id
    )
    session.add(user_mapping)

    # Commit all associations
    session.commit()

    return new_event
