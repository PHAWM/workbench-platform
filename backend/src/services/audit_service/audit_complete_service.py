"""Audit complete service module for comprehensive audit information retrieval"""
from typing import Dict, List, Any, Union
from fastapi import HTTPException
from sqlmodel import Session, select

from src.models import *


def _build_complete_audit_response(
    audit: Audit,
    application: Application,
    user_audit: MappingAuditUser,
    current_user_id: str,
    session: Session
) -> Dict[str, Any]:
    """
    Helper function to build complete audit response with all relationships.

    Args:
        audit: Audit entity
        application: Application entity
        user_audit: User audit mapping
        current_user_id: Current user ID
        session: Database session

    Returns:
        Dictionary with complete audit information
    """
    from . import application_service

    # Get user recommendation for this audit
    status_code, status_text, completion_percentage = application_service.get_audit_status(audit.id, user_audit.id, session) if user_audit else (0, "Not Started", 0.0)
    recommendation_code, recommendation_text = application_service.get_user_audit_outcome(audit.id, user_audit.id, session) if user_audit else (0, "Not Evaluated")

    # Get associated models
    models_statement = select(Modelmetadata).join(
        MappingAuditModel, Modelmetadata.id == MappingAuditModel.model_id
    ).where(MappingAuditModel.audit_id == audit.id)
    models = session.exec(models_statement).all()

    # Get audit pipeline information
    pipeline_statement = select(AuditPipeline).join(
        MappingAuditPipelineAudit, AuditPipeline.id == MappingAuditPipelineAudit.audit_pipeline
    ).where(MappingAuditPipelineAudit.audit_id == audit.id)
    pipelines = session.exec(pipeline_statement).all()

    # Get pipeline events
    pipeline_events = []
    for pipeline in pipelines:
        events_statement = select(Events).join(
            MappingAuditPipelineEvents, Events.id == MappingAuditPipelineEvents.event_id
        ).where(MappingAuditPipelineEvents.audit_pipeline == pipeline.id)
        events = session.exec(events_statement).all()

        pipeline_events.append({
            "pipeline_id": pipeline.id,
            "associated_events": [
                {
                    "event_id": event.id,
                    "description": event.description,
                    "cause": event.cause,
                    "likelihood": event.likelihood,
                    "magnitude": event.magnitude,
                    "valence": event.valence
                } for event in events
            ]
        })

    # Get model-dataset mappings
    dataset_mappings = []
    if pipelines:  # Only if there are pipelines
        mapping_statement = select(MappingModelDatasetAudit, Modelmetadata, DatasetMetadata).join(
            Modelmetadata, MappingModelDatasetAudit.model_id == Modelmetadata.id
        ).join(
            DatasetMetadata, MappingModelDatasetAudit.dataset_id == DatasetMetadata.id
        ).where(MappingModelDatasetAudit.auditpipeline.in_([p.id for p in pipelines]))

        mapping_results = session.exec(mapping_statement).all()
        for mapping, model, dataset in mapping_results:
            dataset_mappings.append({
                "model_id": model.id,
                "model_name": model.name,
                "dataset_id": dataset.id,
                "dataset_purpose": dataset.purpose
            })

    # Process associated models
    model_responses = []
    for model in models:
        model_type_text = "Generative AI" if model.model_type else "Predictive AI"
        model_responses.append({
            "model_id": model.id,
            "model_name": model.name,
            "model_type": model.model_type,
            "model_type_text": model_type_text,
            "task": model.task
        })

    # Get audit instigator
    instigator_statement = select(User.full_name).join(
        MappingAuditUser, User.id == MappingAuditUser.user_id
    ).join(AuditRoles, AuditRoles.id == MappingAuditUser.roles_id).where(
        MappingAuditUser.audit_id == audit.id,
        AuditRoles.role == 'audit_instigator'
    )

    audit_instigator = session.exec(instigator_statement).first()

    return {
        "id": audit.id,
        "name": audit.name,
        "description": audit.description,
        "audit_insigator": audit_instigator,
        "status": status_code,
        "status_text": status_text,
        "recommendation_text": recommendation_text,
        "application_id": application.id,
        "application_name": application.name,
        "associated_models": model_responses,
        "audit_pipelines": pipeline_events,
        "model_dataset_mappings": dataset_mappings,
        "total_models": len(model_responses),
        "total_pipelines": len(pipeline_events),
        "total_mappings": len(dataset_mappings)
    }


def get_all_audits_complete_comprehensive(
    current_user_id: str,
    session: Session
) -> List[Dict[str, Any]]:
    """
    Get comprehensive audit information for all audits where user is an auditor.

    This service function handles the entire business logic for retrieving all complete audits,
    including:
    - User auditor role verification
    - Audit and application retrieval with role filtering
    - Status and recommendation for each audit
    - Models, pipelines, events, and dataset mappings for each audit
    - Response construction for each audit

    Args:
        current_user_id: The ID of the current user
        session: Database session

    Returns:
        List of complete audit dictionaries

    Raises:
        HTTPException: If no audits found (404)
    """
    # Check if user has any audits with auditor role
    audit_user_check = select(MappingAuditUser).join(AuditRoles, AuditRoles.id == MappingAuditUser.roles_id).where(
        MappingAuditUser.user_id == current_user_id,
        AuditRoles.role == "auditor"
    )
    if not session.exec(audit_user_check).first():
        raise HTTPException(status_code=404, detail="No Audits found")

    # Get audit and application
    user_audits_statement = select(Audit, Application).join(
        MappingAuditApplication, Audit.id == MappingAuditApplication.audit_id
    ).join(
        Application, MappingAuditApplication.application_id == Application.id
    ).join(
        MappingAuditUser, Audit.id == MappingAuditUser.audit_id
    ).join(
        AuditRoles, AuditRoles.id == MappingAuditUser.roles_id
    ).where(
        MappingAuditUser.user_id == current_user_id,
        AuditRoles.role == "auditor"
    ).order_by(Audit.id.desc())  # Most recent first

    audit_results = session.exec(user_audits_statement).all()

    if not audit_results:
        raise HTTPException(status_code=404, detail="No Audits found")

    user_audit_list = []

    for audit, application in audit_results:
        # Get user audit mapping for this specific audit
        user_audit_mapping = select(MappingAuditUser).where(
            MappingAuditUser.audit_id == audit.id,
            MappingAuditUser.user_id == current_user_id
        )
        user_audit = session.exec(user_audit_mapping).first()

        # Build complete response for this audit
        audit_response = _build_complete_audit_response(
            audit=audit,
            application=application,
            user_audit=user_audit,
            current_user_id=current_user_id,
            session=session
        )

        user_audit_list.append(audit_response)

    return user_audit_list


def get_single_audit_complete_comprehensive(
    audit_id: int,
    current_user_id: str,
    session: Session
) -> Dict[str, Any]:
    """
    Get comprehensive audit information for a single audit.

    This service function handles the entire business logic for retrieving a single complete audit,
    including:
    - User auditor role and audit access verification
    - Audit and application retrieval
    - Status and recommendation retrieval
    - Models, pipelines, events, and dataset mappings retrieval
    - Response construction

    Args:
        audit_id: The ID of the audit
        current_user_id: The ID of the current user
        session: Database session

    Returns:
        Complete audit dictionary

    Raises:
        HTTPException: If user has no access (403) or audit not found (404)
    """
    # Verify user has access to this audit with auditor role
    audit_user_check = select(MappingAuditUser).join(AuditRoles, AuditRoles.id == MappingAuditUser.roles_id).where(
        MappingAuditUser.audit_id == audit_id,
        MappingAuditUser.user_id == current_user_id,
        AuditRoles.role == "auditor"
    )
    user_audit = session.exec(audit_user_check).first()
    if not user_audit:
        raise HTTPException(status_code=403, detail="Access denied to this audit")

    # Get audit and application
    audit_statement = select(Audit, Application).join(
        MappingAuditApplication, Audit.id == MappingAuditApplication.audit_id
    ).join(
        Application, MappingAuditApplication.application_id == Application.id
    ).where(Audit.id == audit_id)

    audit_result = session.exec(audit_statement).first()
    if not audit_result:
        raise HTTPException(status_code=404, detail="Audit not found")

    audit, application = audit_result

    # Build and return complete response
    return _build_complete_audit_response(
        audit=audit,
        application=application,
        user_audit=user_audit,
        current_user_id=current_user_id,
        session=session
    )
