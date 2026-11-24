"""Event read/retrieval service functions"""
from typing import Any, Dict, List, Optional, Tuple, Set
from fastapi import HTTPException
from sqlmodel import Session, select
from sqlalchemy import or_

from src.models import *


def get_underlying_features_for_audit(audit_id: int, user_id: int, session: Session) -> Dict[str, Any]:
    """
    Get underlying features and target features available for a specific audit.
    Returns both underlying features (from DatasetMetadata) and target features.
    """
    # Verify user has access to this audit
    user_audit = session.exec(
        select(MappingAuditUser).where(
            MappingAuditUser.audit_id == audit_id,
            MappingAuditUser.user_id == user_id
        )
    ).first()

    if not user_audit:
        raise HTTPException(status_code=403, detail="User has no access to this audit")

    # Get the audit pipeline for this audit
    audit_pipeline_mapping = session.exec(
        select(MappingAuditPipelineAudit).where(
            MappingAuditPipelineAudit.audit_id == audit_id
        )
    ).first()

    underlying_features = []

    if audit_pipeline_mapping:
        # Get the DatasetMetadata from the audit
        dataset_mapping = session.exec(
            select(MappingModelDatasetAudit).where(
                MappingModelDatasetAudit.auditpipeline == audit_pipeline_mapping.audit_pipeline
            )
        ).first()

        if dataset_mapping:
            # Get the InputDatasetMetadata to access datatypes (which contains ranges)
            input_dataset_metadata = session.exec(
                select(InputDatasetMetadata).where(
                    InputDatasetMetadata.dataset_metadata_id == dataset_mapping.dataset_id
                )
            ).first()

            datatypes = {}
            if input_dataset_metadata and input_dataset_metadata.datatypes:
                datatypes = input_dataset_metadata.datatypes

            # Get features mapped to this DatasetMetadata
            feature_mappings = session.exec(
                select(MappingDatasetFeatures).where(
                    MappingDatasetFeatures.dataset_metadata_id == dataset_mapping.dataset_id
                )
            ).all()

            for mapping in feature_mappings:
                feature = session.get(UnderlyingFeatures, mapping.underlying_feature_id)
                if feature:
                    feature_dict = {
                        "id": feature.id,
                        "feature_name": feature.feature_name,
                    }
                    if feature.feature_name in datatypes:
                        feature_dict["range"] = datatypes[feature.feature_name]
                    underlying_features.append(feature_dict)

    # Get user-defined underlying features for this audit (created by auditors,
    # mapped to their audit participation via MappingUserAuditFeatures rather
    # than to the dataset via MappingDatasetFeatures).
    user_underlying_mappings = session.exec(
        select(MappingUserAuditFeatures, UnderlyingFeatures)
        .join(UnderlyingFeatures)
        .where(MappingUserAuditFeatures.user_audit_id == user_audit.id)
    ).all()

    user_underlying_features = [
        {
            "id": f.id,
            "feature_name": f.feature_name,
        }
        for _, f in user_underlying_mappings
    ]

    # Get all target features
    target_features = [
        {
            "id": t.id,
            "target_feature": t.target_feature,
            "function_name": t.function_name,
        }
        for t in session.exec(select(TargetFeatures)).all()
    ]

    # Get user-defined target features for this audit
    user_target_mappings = session.exec(
        select(MappingUserAuditTargetFeatures, TargetFeatures)
        .join(TargetFeatures)
        .where(MappingUserAuditTargetFeatures.user_audit_id == user_audit.id)
    ).all()

    user_target_features = [
        {
            "id": t.id,
            "target_feature": t.target_feature,
            "function_name": t.function_name,
        }
        for _, t in user_target_mappings
    ]

    return {
        "audit_id": audit_id,
        "underlying_features": {
            "dataset_features": underlying_features,
            "user_features": user_underlying_features,
            "total_dataset": len(underlying_features),
            "total_user": len(user_underlying_features),
            "total": len(underlying_features) + len(user_underlying_features),
        },
        "target_features": {
            "system_features": target_features,
            "user_features": user_target_features,
            "total_system": len(target_features),
            "total_user": len(user_target_features),
            "total": len(target_features) + len(user_target_features),
        },
    }


def get_user_categories_for_audit(audit_id: int, user_id: int, session: Session) -> Dict[str, Any]:
    """
    Get all categories available to a user for a specific audit.
    This includes both user-specific categories and system categories.
    """
    # Verify user has access to this audit
    user_audit = session.exec(
        select(MappingAuditUser).where(
            MappingAuditUser.audit_id == audit_id,
            MappingAuditUser.user_id == user_id
        )
    ).first()

    if not user_audit:
        raise HTTPException(status_code=403, detail="User has no access to this audit")

    # Get user-specific categories
    user_category_mappings = session.exec(
        select(MappingUserCategories, EventsCategory)
        .join(EventsCategory)
        .where(MappingUserCategories.user_audit_id == user_audit.id)
    ).all()

    user_categories = [
        {
            "id": category.id,
            "event_name": category.event_name,
            "description": category.description,
            "source": "user_specific"
        }
        for mapping, category in user_category_mappings
    ]

    # Get system categories.
    # Exclude any category that is mapped in MappingUserCategories (for any user),
    # so user-specific categories never leak into the system bucket.
    mapped_category_ids = set(
        session.exec(
            select(MappingUserCategories.category_id)
        ).all()
    )

    all_system_categories = session.exec(select(EventsCategory)).all()

    system_categories = [
        {
            "id": category.id,
            "event_name": category.event_name,
            "description": category.description,
            "source": "system"
        }
        for category in all_system_categories
        if category.id not in mapped_category_ids
    ]

    return {
        "audit_id": audit_id,
        "categories": {
            "user_categories": user_categories,
            "system_categories": system_categories,
            "total_user": len(user_categories),
            "total_system": len(system_categories),
            "total": len(user_categories) + len(system_categories)
        }
    }


def get_user_entities_for_audit(audit_id: int, user_id: int, session: Session) -> Dict[str, Any]:
    """
    Get all entities available to a user for a specific audit.
    This includes both user-specific entities and entities from events in this audit.
    """
    # Verify user has access to this audit
    user_audit = session.exec(
        select(MappingAuditUser).where(
            MappingAuditUser.audit_id == audit_id,
            MappingAuditUser.user_id == user_id
        )
    ).first()

    if not user_audit:
        raise HTTPException(status_code=403, detail="User has no access to this audit")

    # Get user-specific entities
    user_entity_mappings = session.exec(
        select(MappingUserEntities, Entities)
        .join(Entities)
        .where(MappingUserEntities.user_audit_id == user_audit.id)
    ).all()

    user_entities = [
        {
            "id": entity.id,
            "name": entity.name,
            "num_individuals": entity.num_individuals,
            "source": "user_specific"
        }
        for mapping, entity in user_entity_mappings
    ]

    # Get audit instigator's user_audit_id
    audit_instigator_mapping = session.exec(
        select(MappingAuditUser.id)
        .join(AuditRoles, MappingAuditUser.roles_id == AuditRoles.id)
        .where(
            MappingAuditUser.audit_id == audit_id,
            AuditRoles.id == 1
        )
    ).first()

    # Build allowed user_audit_ids
    allowed_user_audit_ids = [user_audit.id]
    if audit_instigator_mapping:
        allowed_user_audit_ids.append(audit_instigator_mapping)

    # Get entities from events
    event_entity_mappings = session.exec(
        select(Entities)
        .join(MappingEventsEntities, MappingEventsEntities.entity_id == Entities.id)
        .where(
            MappingEventsEntities.audit_id == audit_id,
            MappingEventsEntities.user_audit_id.in_(allowed_user_audit_ids)
        )
        .distinct()
    ).all()

    event_entities = [
        {
            "id": entity.id,
            "name": entity.name,
            "num_individuals": entity.num_individuals,
            "source": "event"
        }
        for entity in event_entity_mappings
    ]

    return {
        "audit_id": audit_id,
        "entities": {
            "user_entities": user_entities,
            "event_entities": event_entities,
            "total_user": len(user_entities),
            "total_event": len(event_entities),
            "total": len(user_entities) + len(event_entities)
        }
    }


def get_user_features_for_audit(audit_id: int, user_id: int, session: Session) -> Dict[str, Any]:
    """
    Get all features (underlying and target) available to a user for a specific audit.
    This includes both dataset features and user-specific features.
    """
    # Verify user has access to this audit
    user_audit = session.exec(
        select(MappingAuditUser).where(
            MappingAuditUser.audit_id == audit_id,
            MappingAuditUser.user_id == user_id
        )
    ).first()

    if not user_audit:
        raise HTTPException(status_code=403, detail="User has no access to this audit")

    # Get user-specific features
    user_feature_mappings = session.exec(
        select(MappingUserAuditFeatures, UnderlyingFeatures)
        .join(UnderlyingFeatures)
        .where(MappingUserAuditFeatures.user_audit_id == user_audit.id)
    ).all()

    user_features = [
        {
            "id": feature.id,
            "feature_name": feature.feature_name,
            "source": "user_specific"
        }
        for mapping, feature in user_feature_mappings
    ]

    # Get dataset features
    dataset_features = []
    datatypes = {}

    audit_pipeline_mapping = session.exec(
        select(MappingAuditPipelineAudit).where(
            MappingAuditPipelineAudit.audit_id == audit_id
        )
    ).first()

    if audit_pipeline_mapping:
        dataset_mapping = session.exec(
            select(MappingModelDatasetAudit).where(
                MappingModelDatasetAudit.auditpipeline == audit_pipeline_mapping.audit_pipeline
            )
        ).first()

        if dataset_mapping:
            # Get datatypes for range information
            input_dataset_metadata = session.exec(
                select(InputDatasetMetadata).where(
                    InputDatasetMetadata.dataset_metadata_id == dataset_mapping.dataset_id
                )
            ).first()

            if input_dataset_metadata and input_dataset_metadata.datatypes:
                datatypes = input_dataset_metadata.datatypes

            feature_mappings = session.exec(
                select(MappingDatasetFeatures, UnderlyingFeatures)
                .join(UnderlyingFeatures)
                .where(MappingDatasetFeatures.dataset_metadata_id == dataset_mapping.dataset_id)
            ).all()

            for mapping, feature in feature_mappings:
                feature_dict = {
                    "id": feature.id,
                    "feature_name": feature.feature_name,
                    "source": "dataset"
                }
                if feature.feature_name in datatypes:
                    feature_dict["range"] = datatypes[feature.feature_name]
                dataset_features.append(feature_dict)

    # Get user-specific target features
    user_target_mappings = session.exec(
        select(MappingUserAuditTargetFeatures, TargetFeatures)
        .join(TargetFeatures)
        .where(MappingUserAuditTargetFeatures.user_audit_id == user_audit.id)
    ).all()

    user_target_features = [
        {
            "id": target.id,
            "target_feature": target.target_feature,
            "function_name": target.function_name,
            "source": "user_specific"
        }
        for mapping, target in user_target_mappings
    ]

    # Get dataset target features
    target_mappings = session.exec(select(TargetFeatures)).all()
    dataset_target_features = [
        {
            "id": target.id,
            "target_feature": target.target_feature,
            "function_name": target.function_name,
            "source": "dataset"
        }
        for target in target_mappings
    ]

    return {
        "audit_id": audit_id,
        "underlying_features": {
            "user_features": user_features,
            "dataset_features": dataset_features,
            "total_user": len(user_features),
            "total_dataset": len(dataset_features),
            "total": len(user_features) + len(dataset_features)
        },
        "target_features": {
            "user_features": user_target_features,
            "dataset_features": dataset_target_features,
            "total_user": len(user_target_features),
            "total_dataset": len(dataset_target_features),
            "total": len(user_target_features) + len(dataset_target_features)
        }
    }


# ============= REUSABLE HELPER FUNCTIONS =============

def get_user_audit_mapping(
    user_id: str,
    audit_id: int,
    session: Session,
    require_access: bool = True
) -> Optional[MappingAuditUser]:
    """
    Get user's audit mapping for a specific audit.

    Args:
        user_id: The user's ID
        audit_id: The audit ID
        session: Database session
        require_access: If True, raises HTTPException when mapping not found

    Returns:
        MappingAuditUser or None

    Raises:
        HTTPException: If require_access=True and user has no access
    """
    user_audit_mapping = session.exec(
        select(MappingAuditUser).where(
            MappingAuditUser.user_id == user_id,
            MappingAuditUser.audit_id == audit_id
        )
    ).first()

    if not user_audit_mapping and require_access:
        raise HTTPException(status_code=403, detail="User does not have access to this audit")

    return user_audit_mapping


def get_accessible_event_ids(
    current_user_id: str,
    session: Session,
    audit_id: Optional[int] = None
) -> List[int]:
    """
    Get list of event IDs that the current user has access to.

    IMPORTANT: Implements critical access control logic:
    - Users can see their OWN events (events they created)
    - Users can see audit instigator's events (role_id = 1)
    - Users CANNOT see other auditors' events

    This is a reusable function that ensures consistent access control
    across all endpoints that need to filter events by user access.

    Args:
        current_user_id: The current user's ID
        session: Database session
        audit_id: Optional audit ID to restrict to specific audit

    Returns:
        List of event IDs the user can access
    """
    event_ids_query = select(Events.id.distinct()).join(
        MappingUserEvents, Events.id == MappingUserEvents.event_id
    ).join(
        MappingAuditUser, MappingUserEvents.user_audit_id == MappingAuditUser.id
    ).join(
        AuditRoles, MappingAuditUser.roles_id == AuditRoles.id
    )

    if audit_id:
        # Within this audit: current user's OWN events OR audit instigator events
        event_ids_query = event_ids_query.where(
            MappingAuditUser.audit_id == audit_id,
            or_(
                MappingAuditUser.user_id == current_user_id,
                AuditRoles.id == 1  # Audit instigator
            )
        )
    else:
        # All audits where user has access
        event_ids_query = event_ids_query.where(
            or_(
                MappingAuditUser.user_id == current_user_id,
                AuditRoles.id == 1  # Audit instigator
            )
        )

    event_ids = session.exec(event_ids_query).all()
    return list(event_ids)


def get_audit_instigator_user_audit_id(
    audit_id: int,
    session: Session
) -> Optional[int]:
    """
    Get the user_audit_id of the audit instigator for a specific audit.

    Reusable function to get the audit instigator's user_audit_id,
    commonly needed for access control checks.

    Args:
        audit_id: The audit ID
        session: Database session

    Returns:
        user_audit_id of audit instigator, or None if not found
    """
    audit_instigator_mapping = session.exec(
        select(MappingAuditUser.id)
        .join(AuditRoles, MappingAuditUser.roles_id == AuditRoles.id)
        .where(
            MappingAuditUser.audit_id == audit_id,
            AuditRoles.id == 1  # Audit instigator role
        )
    ).first()

    return audit_instigator_mapping


def get_allowed_user_audit_ids(
    user_audit_id: int,
    audit_id: int,
    session: Session
) -> List[int]:
    """
    Get list of allowed user_audit_ids for access control.

    Returns current user's user_audit_id + audit instigator's user_audit_id.
    Commonly used to filter entities, categories, and other audit-scoped data.

    Args:
        user_audit_id: The current user's user_audit_id
        audit_id: The audit ID
        session: Database session

    Returns:
        List of allowed user_audit_ids [current_user, audit_instigator]
    """
    allowed_ids = [user_audit_id]

    audit_instigator_id = get_audit_instigator_user_audit_id(audit_id, session)
    if audit_instigator_id and audit_instigator_id != user_audit_id:
        allowed_ids.append(audit_instigator_id)

    return allowed_ids


def get_event_entities(
    event_id: int,
    session: Session,
    audit_id: Optional[int] = None,
    user_audit_id: Optional[int] = None
) -> List[Entities]:
    """
    Get entities associated with an event, with proper access control.

    Reusable function that handles entity retrieval with optional
    audit-based filtering.

    Args:
        event_id: The event ID
        session: Database session
        audit_id: Optional audit ID for filtering
        user_audit_id: Optional user_audit_id for access control

    Returns:
        List of Entity objects
    """
    if audit_id and user_audit_id:
        # Get allowed user_audit_ids (current user + audit instigator)
        allowed_user_audit_ids = get_allowed_user_audit_ids(user_audit_id, audit_id, session)

        entities_query = select(Entities).join(
            MappingEventsEntities, Entities.id == MappingEventsEntities.entity_id
        ).where(
            MappingEventsEntities.event_id == event_id,
            MappingEventsEntities.audit_id == audit_id,
            MappingEventsEntities.user_audit_id.in_(allowed_user_audit_ids)
        )
    else:
        # Fallback: no access control filtering
        entities_query = select(Entities).join(
            MappingEventsEntities, Entities.id == MappingEventsEntities.entity_id
        ).where(MappingEventsEntities.event_id == event_id)

        if audit_id:
            entities_query = entities_query.where(MappingEventsEntities.audit_id == audit_id)

    return session.exec(entities_query).all()


def get_event_categories_with_access_control(
    event_id: int,
    session: Session,
    user_audit_id: Optional[int] = None
) -> List[EventsCategory]:
    """
    Get categories for an event with user-based access control.

    Filters categories to show only:
    1. User-specific categories (for current user_audit_id)
    2. System categories (not user-defined by anyone)

    Excludes categories created by other users.

    Args:
        event_id: The event ID
        session: Database session
        user_audit_id: Optional user_audit_id for filtering

    Returns:
        List of EventsCategory objects the user can see
    """
    # Get all categories for this event
    categories_results = session.exec(
        select(EventsCategory)
        .join(MappingEventsCategory, EventsCategory.id == MappingEventsCategory.category_id)
        .where(MappingEventsCategory.event_id == event_id)
    ).all()

    if not user_audit_id:
        return categories_results

    # Get user-specific category IDs for this user
    user_category_ids = set(
        session.exec(
            select(MappingUserCategories.category_id)
            .where(MappingUserCategories.user_audit_id == user_audit_id)
        ).all()
    )

    # Get ALL user-defined category IDs (categories that belong to ANY user)
    all_user_category_ids = set(
        session.exec(
            select(MappingUserCategories.category_id).distinct()
        ).all()
    )

    # Filter: include if it's a user-specific category OR a system category
    filtered_categories = [
        category for category in categories_results
        if category.id in user_category_ids or category.id not in all_user_category_ids
    ]

    return filtered_categories


def get_event_audits_with_details(
    event_id: int,
    session: Session
) -> List[Tuple[Audit, Application, MappingEventsAuditStatus]]:
    """
    Get audit details for an event with application information.

    Returns list of (Audit, Application, MappingEventsAuditStatus) tuples
    with automatic deduplication.

    Args:
        event_id: The event ID
        session: Database session

    Returns:
        List of tuples (Audit, Application, MappingEventsAuditStatus)
    """
    audit_results = session.exec(
        select(Audit, Application, MappingEventsAuditStatus)
        .join(MappingEventsAuditStatus, Audit.id == MappingEventsAuditStatus.audit_id)
        .join(MappingAuditApplication, Audit.id == MappingAuditApplication.audit_id)
        .join(Application, MappingAuditApplication.application_id == Application.id)
        .where(MappingEventsAuditStatus.event_id == event_id)
        .distinct()
    ).all()

    return audit_results


def check_event_is_audit_instigator(
    event_id: int,
    session: Session
) -> bool:
    """
    Check if an event was created by an audit instigator.

    Args:
        event_id: The event ID
        session: Database session

    Returns:
        True if event was created by audit instigator (role_id = 1 or 3)
    """
    event_type_result = session.exec(
        select(EventType, AuditRoles)
        .join(MappingAuditUser, EventType.created_by_user_id == MappingAuditUser.id)
        .join(AuditRoles, MappingAuditUser.roles_id == AuditRoles.id)
        .where(EventType.event_id == event_id)
    ).first()

    if not event_type_result:
        return False

    event_type, audit_role = event_type_result
    return audit_role.id == 1 or audit_role.id == 3


# ============= MAIN SERVICE FUNCTIONS =============

def get_event_detailed_with_context(
    event_id: int,
    current_user_id: str,
    session: Session,
    audit_id: Optional[int] = None
) -> 'EnhancedEventDetailResponse':
    """
    Get detailed event information with effective values and related data.

    This is the main service function for retrieving comprehensive event details
    with proper access control and audit context.

    Args:
        event_id: The event ID
        current_user_id: The current user's ID
        session: Database session
        audit_id: Optional audit ID for context (strongly recommended)

    Returns:
        EnhancedEventDetailResponse with all event details

    Raises:
        HTTPException: If event not found or user has no access
    """
    # Import models here to avoid circular imports
    from src.models import (
        EnhancedEventDetailResponse,
        EventEntityDetail,
        EventCategoryDetail,
        EventUserDetail,
        EventAuditDetail
    )
    from .utils import (
        get_effective_event_values,
        determine_risk_level,
        determine_impact_type,
        get_audit_status_text
    )

    # Get basic event
    event = session.get(Events, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    # Get user_audit_id for the specific audit
    user_audit_id = None
    if audit_id:
        user_audit_mapping = get_user_audit_mapping(
            current_user_id, audit_id, session, require_access=True
        )
        user_audit_id = user_audit_mapping.id

    # Get effective values
    if user_audit_id:
        effective_values, is_customised = get_effective_event_values(
            session, user_audit_id, event_id
        )
    else:
        effective_values = {
            'likelihood': event.likelihood,
            'magnitude': event.magnitude,
            'valence': event.valence
        }
        is_customised = False

    # Get entities using reusable helper
    entities_results = get_event_entities(event_id, session, audit_id, user_audit_id)
    associated_entities = [
        EventEntityDetail(
            entity_id=entity.id,
            entity_name=entity.name,
            num_individuals=entity.num_individuals
        )
        for entity in entities_results
    ]

    # Get categories using reusable helper
    categories_results = get_event_categories_with_access_control(
        event_id, session, user_audit_id
    )
    event_categories = [
        EventCategoryDetail(
            category_id=category.id,
            event_name=category.event_name,
            description=category.description
        )
        for category in categories_results
    ]

    # Get users (empty for now as per original implementation)
    assigned_users = []

    # Get audits using reusable helper
    audit_results = get_event_audits_with_details(event_id, session)

    # Deduplicate audits
    seen_audits = set()
    audit_details = []
    for audit, application, mapping in audit_results:
        if audit.id not in seen_audits:
            seen_audits.add(audit.id)
            audit_details.append(EventAuditDetail(
                audit_id=audit.id,
                audit_name=audit.name,
                audit_status=mapping.status if mapping.status is not None else 0,
                audit_status_text=get_audit_status_text(
                    mapping.status if mapping.status is not None else 0
                ),
                recommendation=mapping.recommendation if mapping.recommendation is not None else 0,
                notes=mapping.notes,
                application_id=application.id,
                application_name=application.name
            ))

    # Calculate risk assessment
    risk_level = determine_risk_level(effective_values['likelihood'], effective_values['magnitude'])
    impact_type = determine_impact_type(effective_values['valence'])

    return EnhancedEventDetailResponse(
        id=event.id,
        name=event.name,
        description=event.description,
        cause=event.cause,
        reason=event.reason,
        likelihood=effective_values['likelihood'],
        magnitude=effective_values['magnitude'],
        valence=effective_values['valence'],
        is_user_defined=True,
        is_template=False,
        event_category=None,
        risk_level=risk_level,
        impact_type=impact_type,
        associated_entities=associated_entities,
        event_categories=event_categories,
        assigned_users=assigned_users,
        audit_details=audit_details,
        total_entities=len(associated_entities),
        total_categories=len(event_categories),
        total_users=len(assigned_users),
        total_audits=len(audit_details)
    )


def list_events_with_details(
    current_user_id: str,
    session: Session,
    page: int = 1,
    page_size: int = 100,
    audit_id: Optional[int] = None,
    user_id: Optional[str] = None,
    sort_by: str = "likelihood",
    sort_order: str = "desc",
    user_defined_only: Optional[bool] = None,
    templates_only: Optional[bool] = None,
    category: Optional[str] = None
) -> 'EventsDetailedListResponse':
    """
    List events with detailed information, proper pagination, and access control.

    This is the main service function for listing events with comprehensive details.
    Implements critical security controls to prevent cross-user data leakage.

    Args:
        current_user_id: The current user's ID
        session: Database session
        page: Page number (1-indexed)
        page_size: Number of items per page
        audit_id: Optional audit ID for filtering
        user_id: Optional user ID for filtering
        sort_by: Field to sort by (likelihood, magnitude, valence)
        sort_order: Sort order (asc, desc)
        user_defined_only: Filter for user-defined events only
        templates_only: Filter for template events only
        category: Filter by category

    Returns:
        EventsDetailedListResponse with paginated event list

    Raises:
        HTTPException: If user has no access to specified audit
    """
    # Import models and utilities here to avoid circular imports
    from src.models import (
        EventsDetailedListResponse,
        EventDetailedListItem,
        EventEntitySummary,
        EventCategorySummary,
        EventAuditSummary,
        EventPipelineSummary
    )
    from .utils import (
        get_effective_event_values,
        get_event_metrics_with_values,
        get_audit_status_text,
        apply_sorting
    )

    # Get user_audit_id for the specific audit
    user_audit_id = None
    if audit_id:
        user_audit_mapping = session.exec(
            select(MappingAuditUser.id).where(
                MappingAuditUser.audit_id == audit_id,
                MappingAuditUser.user_id == current_user_id
            )
        ).first()
        user_audit_id = user_audit_mapping

    # Build filters dictionary
    filters = {
        "audit_id": audit_id,
        "user_id": user_id,
        "user_defined_only": user_defined_only,
        "templates_only": templates_only,
        "category": category
    }
    # Remove None values
    filters = {k: v for k, v in filters.items() if v is not None}

    # Get accessible event IDs using reusable helper (SECURITY CRITICAL)
    event_ids = get_accessible_event_ids(current_user_id, session, audit_id)

    # Build base query with event type join
    base_query = select(Events).join(
        EventType, Events.id == EventType.event_id, isouter=True
    ).where(
        Events.id.in_(event_ids)
    )

    # Apply additional filters
    if user_defined_only is not None:
        base_query = base_query.where(EventType.is_user_defined == user_defined_only)

    if templates_only is not None:
        base_query = base_query.where(EventType.is_template == templates_only)

    if category:
        base_query = base_query.where(EventType.category == category)

    # Get total count before pagination
    total_count = len(session.exec(base_query).all())

    # Apply sorting (import enums locally to avoid circular import)
    from src.api.routes.events import SortBy, SortOrder
    sort_by_enum = getattr(SortBy, sort_by, SortBy.likelihood)
    sort_order_enum = getattr(SortOrder, sort_order, SortOrder.desc)
    sorted_query = apply_sorting(base_query, sort_by_enum, sort_order_enum)

    # Apply pagination
    paginated_query = sorted_query.offset((page - 1) * page_size).limit(page_size)

    # Execute query
    events = session.exec(paginated_query).all()

    # Process each event
    event_items = []
    for event in events:
        # Get effective values
        if user_audit_id:
            effective_values, is_customised = get_effective_event_values(
                session, user_audit_id, event.id
            )
        else:
            effective_values = {
                'likelihood': event.likelihood,
                'magnitude': event.magnitude,
                'valence': event.valence
            }

        # Get entities using reusable helper
        entities_results = get_event_entities(event.id, session, audit_id, user_audit_id)
        associated_entities = [
            EventEntitySummary(
                entity_id=entity.id,
                entity_name=entity.name,
                num_individuals=entity.num_individuals
            )
            for entity in entities_results
        ]

        # Get metrics using reusable helper
        associated_metrics = get_event_metrics_with_values(
            event.id, session, audit_id, user_audit_id, current_user_id
        )

        # Get categories using reusable helper
        categories_results = get_event_categories_with_access_control(
            event.id, session, user_audit_id
        )
        event_categories = [
            EventCategorySummary(
                category_id=category.id,
                event_name=category.event_name
            )
            for category in categories_results
        ]

        # Get audits using reusable helper
        audit_results = get_event_audits_with_details(event.id, session)

        # Deduplicate audits
        seen_audits = set()
        audit_details = []
        for audit, application, mapping in audit_results:
            if audit.id not in seen_audits:
                seen_audits.add(audit.id)
                audit_details.append(EventAuditSummary(
                    audit_id=audit.id,
                    audit_name=audit.name,
                    audit_status=mapping.status if mapping.status is not None else 0,
                    audit_status_text=get_audit_status_text(mapping.status),
                    application_name=application.name
                ))

        # Check if event is from audit instigator
        is_audit_instigator = check_event_is_audit_instigator(event.id, session)

        # Get pipeline associations
        associated_pipelines = []
        if audit_id and user_audit_id:
            audit_pipeline_id = session.exec(
                select(MappingAuditPipelineAudit.audit_pipeline).where(
                    MappingAuditPipelineAudit.audit_id == audit_id
                )
            ).first()

            if audit_pipeline_id:
                for metric in associated_metrics:
                    exists = session.exec(
                        select(MappingAuditPipelineEvents).where(
                            MappingAuditPipelineEvents.audit_pipeline == int(audit_pipeline_id),
                            MappingAuditPipelineEvents.event_id == event.id,
                            MappingAuditPipelineEvents.metric_id == metric.metric_id,
                            MappingAuditPipelineEvents.user_audit_id == user_audit_id
                        )
                    ).first()

                    if exists:
                        associated_pipelines.append(
                            EventPipelineSummary(metric_id=exists.metric_id)
                        )

        # Build event item
        event_items.append(EventDetailedListItem(
            id=event.id,
            name=event.name,
            description=event.description,
            cause=event.cause,
            reason=event.reason,
            likelihood=effective_values['likelihood'],
            magnitude=effective_values['magnitude'],
            valence=effective_values['valence'],
            is_audit_instigator=is_audit_instigator,
            is_user_defined=not is_audit_instigator,
            associated_metrics=associated_metrics,
            associated_entities=associated_entities,
            associated_pipelines=associated_pipelines,
            event_categories=event_categories,
            assigned_users=[],
            audit_details=audit_details,
            total_metrics=len(associated_metrics),
            total_entities=len(associated_entities),
            total_categories=len(event_categories),
            total_users=0,
            total_audits=len(audit_details)
        ))

    # Calculate total pages
    total_pages = (total_count + page_size - 1) // page_size

    return EventsDetailedListResponse(
        events=event_items,
        total_count=total_count,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        filters_applied=filters
    )
