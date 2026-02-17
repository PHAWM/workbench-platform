"""Audit overview service module for audit listing and detail operations"""
from typing import Dict, List, Any, Tuple
from fastapi import HTTPException
from sqlmodel import Session, select

from src.models import *


def get_all_audits_overview_comprehensive(
    current_user_id: str,
    session: Session
) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    """
    Get all audits overview for the current user.

    This service function handles the entire business logic for retrieving all audits,
    including:
    - User audit access verification
    - Audit and application retrieval with joins
    - Status and completion percentage calculation for each audit
    - Recommendation retrieval for each audit
    - Audit instigator identification
    - Status summary aggregation

    Args:
        current_user_id: The ID of the current user
        session: Database session

    Returns:
        Tuple of (audit_overviews_list, status_summary_dict)
        - audit_overviews_list: List of audit overview dictionaries
        - status_summary_dict: Count of audits by status
    """
    from . import application_service

    # Get all audits where the current user is involved
    audits_statement = select(Audit, Application).join(
        MappingAuditApplication, Audit.id == MappingAuditApplication.audit_id
    ).join(
        Application, MappingAuditApplication.application_id == Application.id
    ).join(
        MappingAuditUser, Audit.id == MappingAuditUser.audit_id
    ).where(
        MappingAuditUser.user_id == current_user_id
    ).distinct()

    audit_results = session.exec(audits_statement).all()

    # Process each audit
    audit_overviews = []
    status_summary = {"Not Started": 0, "In Progress": 0, "Finished": 0, "Submitted": 0}

    for audit, application in audit_results:
        # Get user audit mapping to get user_audit_id
        user_audit_mapping = select(MappingAuditUser).where(
            MappingAuditUser.audit_id == audit.id,
            MappingAuditUser.user_id == current_user_id
        )
        user_audit = session.exec(user_audit_mapping).first()

        if user_audit:
            status_code, status_text, completion_percentage = application_service.get_audit_status(audit.id, user_audit.id, session)
            recommendation_code, recommendation_text = application_service.get_user_audit_outcome(audit.id, user_audit.id, session)
        else:
            status_code, status_text, completion_percentage = 0, "Not Started", 0.0
            recommendation_code, recommendation_text = 0, "Not Evaluated"

        status_summary[status_text] += 1

        # Get audit instigator
        instigator_statement = select(User.full_name).join(
            MappingAuditUser, User.id == MappingAuditUser.user_id
        ).join(AuditRoles, AuditRoles.id == MappingAuditUser.roles_id).where(
            MappingAuditUser.audit_id == audit.id,
            AuditRoles.role == 'audit_instigator'
        )

        audit_instigator = session.exec(instigator_statement).first()

        audit_overviews.append({
            "id": audit.id,
            "name": audit.name,
            "description": audit.description,
            "audit_instigator": audit_instigator,
            "status": status_code,
            "status_text": status_text,
            "completion_percentage": completion_percentage,
            "recommendation": recommendation_text,
            "application_id": application.id,
            "application_name": application.name,
            "application_description": getattr(application, 'description', None),
            "application_organisation": application.organisation,
            "application_url": application.url,
            "access_type": application.access_type,
            "testing_evaluation": application.testing_evaluation,
            "deployment": application.deployment,
            "business_case": application.business_case,
            "legal_framework": application.legal_framework
        })

    return audit_overviews, status_summary


def get_audit_overview_comprehensive(
    audit_id: int,
    current_user_id: str,
    session: Session
) -> Dict[str, Any]:
    """
    Get single audit overview with application details.

    This service function handles the entire business logic for retrieving a single audit,
    including:
    - User audit access verification
    - Audit and application retrieval
    - Status and completion calculation
    - Recommendation retrieval
    - Model metadata retrieval
    - Dataset metadata retrieval with input/output metadata
    - Audit instigator identification

    Args:
        audit_id: The ID of the audit
        current_user_id: The ID of the current user
        session: Database session

    Returns:
        Dictionary with audit overview data

    Raises:
        HTTPException: If user has no access (403) or audit not found (404)
    """
    from . import application_service

    # Verify user has access to this audit
    audit_user_check = select(MappingAuditUser).where(
        MappingAuditUser.audit_id == audit_id,
        MappingAuditUser.user_id == current_user_id
    )
    user_audit = session.exec(audit_user_check).first()
    if not user_audit:
        raise HTTPException(status_code=403, detail="Access denied to this audit")

    # Get audit with application details
    audit_statement = select(Audit, Application).join(
        MappingAuditApplication, Audit.id == MappingAuditApplication.audit_id
    ).join(
        Application, MappingAuditApplication.application_id == Application.id
    ).where(Audit.id == audit_id)

    audit_result = session.exec(audit_statement).first()
    if not audit_result:
        raise HTTPException(status_code=404, detail="Audit not found")

    audit, application = audit_result

    status_code, status_text, completion_percentage = application_service.get_audit_status(audit.id, user_audit.id, session)
    recommendation_code, recommendation_text = application_service.get_user_audit_outcome(audit.id, user_audit.id, session)

    # Get audit instigator
    instigator_statement = select(User.full_name).join(
        MappingAuditUser, User.id == MappingAuditUser.user_id
    ).join(AuditRoles, AuditRoles.id == MappingAuditUser.roles_id).where(
        MappingAuditUser.audit_id == audit.id,
        AuditRoles.role == 'audit_instigator'
    )

    model_query = session.exec(
        select(Modelmetadata)
        .join(MappingAuditModel, Modelmetadata.id == MappingAuditModel.model_id)
        .where(MappingAuditModel.audit_id == audit_id)
    ).all()

    model_list = []
    for model in model_query:
        model_list.append({
            "id": model.id,
            "name": model.name,
            "model_type": model.model_type,
            "acceptable_formats": model.acceptable_formats,
            "output_context": model.output_context,
            "task": model.task
        })

    dataset_list = []

    datasets = session.exec(
        select(DatasetMetadata)
        .join(MappingModelDatasetAudit, MappingModelDatasetAudit.dataset_id==DatasetMetadata.id)
        .join(MappingAuditPipelineAudit, MappingAuditPipelineAudit.audit_pipeline == MappingModelDatasetAudit.auditpipeline)
        .where(
            MappingAuditPipelineAudit.audit_id == audit_id
        )
    ).all()

    for dataset in datasets:
        input_metadata = dataset.input_dataset_metadata[-1] if dataset.input_dataset_metadata else None
        output_metadata = dataset.output_dataset_metadata[-1] if dataset.output_dataset_metadata else None
        dataset_list.append({
            "id": dataset.id,
            "purpose": dataset.purpose,
            "copyright_agreement": dataset.copyright_agreement,
            "input_metadata": {
                "id": input_metadata.id,
                "dataset_metadata_id": input_metadata.dataset_metadata_id,
                "headers": input_metadata.headers,
                "benchmark_dataset": input_metadata.benchmark_dataset,
                "datatypes": input_metadata.datatypes,
                "location": input_metadata.location
            } if input_metadata else None,
            "output_metadata": {
                "id": output_metadata.id,
                "dataset_metadata_id": output_metadata.dataset_metadata_id,
                "headers": output_metadata.headers,
                "benchmark_dataset": output_metadata.benchmark_dataset,
                "datatypes": output_metadata.datatypes,
                "location": output_metadata.location
            } if output_metadata else None,
            "message": "Dataset retrieved successfully"
        })

    audit_instigator = session.exec(instigator_statement).first()

    return {
        "id": audit.id,
        "name": audit.name,
        "description": audit.description,
        "audit_instigator": audit_instigator,
        "status": status_code,
        "status_text": status_text,
        "completion_percentage": completion_percentage,
        "recommendation": recommendation_text,
        "application_id": application.id,
        "application_name": application.name,
        "application_description": getattr(application, 'description', None),
        "application_organisation": application.organisation,
        "application_url": application.url,
        "application_models": model_list,
        "application_datasets": dataset_list,
        "access_type": application.access_type,
        "testing_evaluation": application.testing_evaluation,
        "deployment": application.deployment,
        "business_case": application.business_case,
        "legal_framework": application.legal_framework
    }
