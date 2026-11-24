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


def _is_audit_instigator(user_audit: 'MappingAuditUser', session: Session) -> bool:
    """Check if a user_audit mapping has the audit_instigator role."""
    if not user_audit.roles_id:
        return False
    role = session.get(AuditRoles, user_audit.roles_id)
    return role and role.role == "audit_instigator"


def _get_dataset_id_for_audit(audit_id: int, session: Session) -> Optional[int]:
    """Get the dataset_id linked to an audit via the pipeline."""
    audit_pipeline_mapping = session.exec(
        select(MappingAuditPipelineAudit).where(
            MappingAuditPipelineAudit.audit_id == audit_id
        )
    ).first()
    if not audit_pipeline_mapping:
        return None
    dataset_mapping = session.exec(
        select(MappingModelDatasetAudit).where(
            MappingModelDatasetAudit.auditpipeline == audit_pipeline_mapping.audit_pipeline
        )
    ).first()
    return dataset_mapping.dataset_id if dataset_mapping else None


def _get_or_create_placeholder_dataset_for_audit(
    audit_id: int, session: Session
) -> Optional[int]:
    """Return the audit's dataset_id, auto-creating a placeholder for opaque-box audits.

    The instigator features/target-features flow links new rows to the audit's
    dataset via MappingDatasetFeatures / MappingModelTargetFeatures. For
    opaque-box audits (Application.access_type == 0) there is often no real
    dataset, which used to surface as "No dataset linked to this audit".

    For opaque-box audits with at least one model attached we instead create a
    placeholder DatasetMetadata seeded from the model's task/output_context
    fields, plus minimal Input/Output rows so downstream readers don't crash.
    The placeholder still has empty location/headers payloads, so the
    performance-pipeline skip in `should_skip_performance_pipeline` continues
    to fire — placeholders are catalogue stubs, not real data.

    Returns the resulting dataset_id, or None if:
      * the audit is not opaque-box and has no real dataset, or
      * the opaque-box audit has no model to attach the placeholder to.
    Callers should treat None the same way they used to treat the old error.
    """
    existing = _get_dataset_id_for_audit(audit_id, session)
    if existing:
        return existing

    application = session.exec(
        select(Application)
        .join(MappingAuditApplication, MappingAuditApplication.application_id == Application.id)
        .where(MappingAuditApplication.audit_id == audit_id)
    ).first()
    if not application or application.access_type != 0:
        return None

    audit_pipeline_mapping = session.exec(
        select(MappingAuditPipelineAudit).where(
            MappingAuditPipelineAudit.audit_id == audit_id
        )
    ).first()
    if not audit_pipeline_mapping:
        return None

    audit_model = session.exec(
        select(MappingAuditModel).where(MappingAuditModel.audit_id == audit_id)
    ).first()
    if not audit_model:
        return None

    model = session.get(Modelmetadata, audit_model.model_id)
    task = (model.task if model and model.task else "unknown") if model else "unknown"
    output_context = (
        model.output_context if model and model.output_context else "unknown"
    ) if model else "unknown"

    dataset = DatasetMetadata(purpose=task, copyright_agreement=None)
    session.add(dataset)
    session.flush()

    session.add(InputDatasetMetadata(
        dataset_metadata_id=dataset.id,
        headers={"task": task},
        datatypes={"task": "string"},
        location=None,
    ))
    session.add(OutputDatasetMetadata(
        dataset_metadata_id=dataset.id,
        headers={"output_context": output_context},
        datatypes={"output_context": "string"},
        location=None,
    ))

    session.add(MappingModelDatasetAudit(
        auditpipeline=audit_pipeline_mapping.audit_pipeline,
        model_id=audit_model.model_id,
        dataset_id=dataset.id,
    ))
    session.flush()

    return dataset.id


def create_user_feature(feature_name: str, audit_id: int, user_id: int, session: Session) -> Dict[str, Any]:
    """
    Create a new feature for an audit.
    If the user is the audit_instigator, the feature is linked to the dataset (system feature).
    Otherwise, it is linked to the user's audit participation (user-specific feature).
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

    is_instigator = _is_audit_instigator(user_audit, session)

    if is_instigator:
        # Link to dataset as a system feature. For opaque-box audits with no
        # real dataset we auto-provision a placeholder so the flow doesn't
        # error — see _get_or_create_placeholder_dataset_for_audit.
        dataset_id = _get_or_create_placeholder_dataset_for_audit(audit_id, session)
        if not dataset_id:
            raise HTTPException(status_code=400, detail="No dataset linked to this audit")

        existing_mapping = session.exec(
            select(MappingDatasetFeatures).where(
                MappingDatasetFeatures.dataset_metadata_id == dataset_id,
                MappingDatasetFeatures.underlying_feature_id == feature_id
            )
        ).first()

        if existing_mapping:
            raise HTTPException(
                status_code=400,
                detail=f"Feature '{feature_name}' already exists as a system feature for this audit's dataset"
            )

        session.add(MappingDatasetFeatures(
            dataset_metadata_id=dataset_id,
            underlying_feature_id=feature_id
        ))
        session.commit()

        return {
            "id": feature_id,
            "feature_name": feature_name,
            "audit_id": audit_id,
            "dataset_id": dataset_id,
            "type": "system",
            "message": f"Feature '{feature_name}' created as system feature linked to dataset"
        }
    else:
        # Link to user audit as a user-specific feature
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

        session.add(MappingUserAuditFeatures(
            user_audit_id=user_audit.id,
            underlying_feature_id=feature_id
        ))
        session.commit()

        return {
            "id": feature_id,
            "feature_name": feature_name,
            "audit_id": audit_id,
            "user_audit_id": user_audit.id,
            "type": "user",
            "message": f"Feature '{feature_name}' created and mapped to user's audit"
        }


def create_user_target_feature(target_feature: str, audit_id: int, user_id: int, session: Session) -> Dict[str, Any]:
    """
    Create a new target feature for an audit.
    If the user is the audit_instigator, the feature is linked to the dataset (system feature).
    Otherwise, it is linked to the user's audit participation (user-specific feature).
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

    # Resolve function_name from METRICS_REGISTRY if it exists
    from src.services.performance_service.functions import METRICS_REGISTRY
    resolved_function_name = None
    target_key = target_feature.lower().replace(" ", "_")
    if target_key in METRICS_REGISTRY:
        resolved_function_name = METRICS_REGISTRY[target_key].__name__

    if existing_feature:
        feature_id = existing_feature.id
        # Update function_name if it was previously None
        if not existing_feature.function_name and resolved_function_name:
            existing_feature.function_name = resolved_function_name
            session.add(existing_feature)
            session.flush()
    else:
        # Create new target feature
        new_feature = TargetFeatures(
            target_feature=target_feature,
            function_name=resolved_function_name
        )
        session.add(new_feature)
        session.flush()
        feature_id = new_feature.id

    is_instigator = _is_audit_instigator(user_audit, session)

    if is_instigator:
        # Link to dataset as a system feature. For opaque-box audits with no
        # real dataset we auto-provision a placeholder so the flow doesn't
        # error — see _get_or_create_placeholder_dataset_for_audit.
        dataset_id = _get_or_create_placeholder_dataset_for_audit(audit_id, session)
        if not dataset_id:
            raise HTTPException(status_code=400, detail="No dataset linked to this audit")

        existing_mapping = session.exec(
            select(MappingModelTargetFeatures).where(
                MappingModelTargetFeatures.dataset_metadata_id == dataset_id,
                MappingModelTargetFeatures.target_feature_id == feature_id
            )
        ).first()

        if existing_mapping:
            raise HTTPException(
                status_code=400,
                detail=f"Target feature '{target_feature}' already exists as a system feature for this audit's dataset"
            )

        session.add(MappingModelTargetFeatures(
            dataset_metadata_id=dataset_id,
            target_feature_id=feature_id
        ))
        session.commit()

        return {
            "id": feature_id,
            "target_feature": target_feature,
            "function_name": resolved_function_name,
            "audit_id": audit_id,
            "dataset_id": dataset_id,
            "type": "system",
            "message": f"Target feature '{target_feature}' created as system feature linked to dataset"
        }
    else:
        # Link to user audit as a user-specific feature
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

        session.add(MappingUserAuditTargetFeatures(
            user_audit_id=user_audit.id,
            target_feature_id=feature_id
        ))
        session.commit()

        return {
            "id": feature_id,
            "target_feature": target_feature,
            "function_name": resolved_function_name,
            "audit_id": audit_id,
            "user_audit_id": user_audit.id,
            "type": "user",
            "message": f"Target feature '{target_feature}' created and mapped to user's audit"
        }


def create_user_entity(name: str, num_individuals: int, audit_id: int, user_id: int, session: Session) -> Dict[str, Any]:
    """
    Create a new entity for an audit.
    If the user is the audit_instigator, the entity is linked to the audit via MappingEventsEntities (system entity).
    Otherwise, it is linked to the user's audit participation via MappingUserEntities (user-specific entity).
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

    is_instigator = _is_audit_instigator(user_audit, session)

    if is_instigator:
        # Link to audit as a system entity via MappingEventsEntities
        existing_mapping = session.exec(
            select(MappingEventsEntities).where(
                MappingEventsEntities.audit_id == audit_id,
                MappingEventsEntities.entity_id == entity_id,
                MappingEventsEntities.user_audit_id == user_audit.id,
                MappingEventsEntities.event_id == None
            )
        ).first()

        if existing_mapping:
            raise HTTPException(
                status_code=400,
                detail=f"Entity '{name}' already exists as a system entity for this audit"
            )

        session.add(MappingEventsEntities(
            audit_id=audit_id,
            entity_id=entity_id,
            user_audit_id=user_audit.id,
            event_id=None
        ))
        session.commit()

        return {
            "entities_id": entity_id,
            "name": name,
            "num_individuals": num_individuals,
            "audit_id": audit_id,
            "user_audit_id": user_audit.id,
            "type": "system",
            "message": f"Entity '{name}' created as system entity linked to audit"
        }
    else:
        # Link to user audit as a user-specific entity
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

        session.add(MappingUserEntities(
            user_audit_id=user_audit.id,
            entity_id=entity_id
        ))
        session.commit()

        return {
            "entities_id": entity_id,
            "name": name,
            "num_individuals": num_individuals,
            "audit_id": audit_id,
            "user_audit_id": user_audit.id,
            "type": "user",
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


# ---------------------------------------------------------------------------
# Delete feature / target feature for an audit
# ---------------------------------------------------------------------------

def delete_user_feature(feature_id: int, audit_id: int, user_id: int, session: Session) -> Dict[str, Any]:
    """
    Delete an underlying feature from an audit.
    audit_instigator: removes from MappingDatasetFeatures (system feature).
    auditor: removes from MappingUserAuditFeatures (user-specific feature).
    """
    user_audit = session.exec(
        select(MappingAuditUser).where(
            MappingAuditUser.audit_id == audit_id,
            MappingAuditUser.user_id == user_id
        )
    ).first()

    if not user_audit:
        raise HTTPException(status_code=403, detail="User does not have access to this audit")

    feature = session.get(UnderlyingFeatures, feature_id)
    if not feature:
        raise HTTPException(status_code=404, detail="Feature not found")

    is_instigator = _is_audit_instigator(user_audit, session)

    if is_instigator:
        # Read-only here — don't auto-provision a placeholder on delete.
        # No dataset means there cannot be a MappingDatasetFeatures row, so
        # the unlink is a 404 rather than the legacy 400.
        dataset_id = _get_dataset_id_for_audit(audit_id, session)
        if not dataset_id:
            raise HTTPException(status_code=404, detail="Feature not linked to this audit's dataset")

        mapping = session.exec(
            select(MappingDatasetFeatures).where(
                MappingDatasetFeatures.dataset_metadata_id == dataset_id,
                MappingDatasetFeatures.underlying_feature_id == feature_id
            )
        ).first()

        if not mapping:
            raise HTTPException(status_code=404, detail="Feature not linked to this audit's dataset")

        session.delete(mapping)
        session.commit()

        return {
            "feature_id": feature_id,
            "feature_name": feature.feature_name,
            "audit_id": audit_id,
            "type": "system",
            "message": f"System feature '{feature.feature_name}' removed from audit's dataset"
        }
    else:
        mapping = session.exec(
            select(MappingUserAuditFeatures).where(
                MappingUserAuditFeatures.user_audit_id == user_audit.id,
                MappingUserAuditFeatures.underlying_feature_id == feature_id
            )
        ).first()

        if not mapping:
            raise HTTPException(status_code=404, detail="Feature not linked to this user's audit")

        session.delete(mapping)
        session.commit()

        return {
            "feature_id": feature_id,
            "feature_name": feature.feature_name,
            "audit_id": audit_id,
            "type": "user",
            "message": f"User feature '{feature.feature_name}' removed from audit"
        }


def delete_user_target_feature(target_feature_id: int, audit_id: int, user_id: int, session: Session) -> Dict[str, Any]:
    """
    Delete a target feature from an audit.
    audit_instigator: removes from MappingModelTargetFeatures (system target).
    auditor: removes from MappingUserAuditTargetFeatures (user-specific target).
    """
    user_audit = session.exec(
        select(MappingAuditUser).where(
            MappingAuditUser.audit_id == audit_id,
            MappingAuditUser.user_id == user_id
        )
    ).first()

    if not user_audit:
        raise HTTPException(status_code=403, detail="User does not have access to this audit")

    target = session.get(TargetFeatures, target_feature_id)
    if not target:
        raise HTTPException(status_code=404, detail="Target feature not found")

    is_instigator = _is_audit_instigator(user_audit, session)

    if is_instigator:
        # Read-only here — don't auto-provision a placeholder on delete.
        # No dataset means there cannot be a MappingModelTargetFeatures row,
        # so the unlink is a 404 rather than the legacy 400.
        dataset_id = _get_dataset_id_for_audit(audit_id, session)
        if not dataset_id:
            raise HTTPException(status_code=404, detail="Target feature not linked to this audit's dataset")

        mapping = session.exec(
            select(MappingModelTargetFeatures).where(
                MappingModelTargetFeatures.dataset_metadata_id == dataset_id,
                MappingModelTargetFeatures.target_feature_id == target_feature_id
            )
        ).first()

        if not mapping:
            raise HTTPException(status_code=404, detail="Target feature not linked to this audit's dataset")

        session.delete(mapping)
        session.commit()

        return {
            "target_feature_id": target_feature_id,
            "target_feature": target.target_feature,
            "audit_id": audit_id,
            "type": "system",
            "message": f"System target feature '{target.target_feature}' removed from audit's dataset"
        }
    else:
        mapping = session.exec(
            select(MappingUserAuditTargetFeatures).where(
                MappingUserAuditTargetFeatures.user_audit_id == user_audit.id,
                MappingUserAuditTargetFeatures.target_feature_id == target_feature_id
            )
        ).first()

        if not mapping:
            raise HTTPException(status_code=404, detail="Target feature not linked to this user's audit")

        session.delete(mapping)
        session.commit()

        return {
            "target_feature_id": target_feature_id,
            "target_feature": target.target_feature,
            "audit_id": audit_id,
            "type": "user",
            "message": f"User target feature '{target.target_feature}' removed from audit"
        }
