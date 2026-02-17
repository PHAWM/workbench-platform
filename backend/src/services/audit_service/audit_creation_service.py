"""Audit creation service module for creating audits with full setup"""
from typing import Dict, Any
from fastapi import HTTPException
from sqlmodel import Session

from src.models import *


def create_audit_comprehensive(
    audit_data: 'AuditCompleteCreate',
    current_user_id: str,
    session: Session
) -> Dict[str, Any]:
    """
    Create audit with model associations and pipeline setup in one call.

    This service function handles the entire business logic for creating an audit,
    including:
    - Application existence verification
    - Audit entity creation
    - User-audit association creation
    - Initial audit outcome creation
    - Audit pipeline creation (if requested)
    - Pipeline-audit linking
    - Model associations creation
    - Application-audit mapping creation
    - Transaction management

    Args:
        audit_data: Complete audit creation data including name, description, application_id, model_ids, create_pipeline
        current_user_id: The ID of the current user creating the audit
        session: Database session

    Returns:
        Dictionary with created audit details, pipeline info, and model associations

    Raises:
        HTTPException: If application not found (400) or creation fails (400)
    """
    try:
        # Verify application exists
        application = session.get(Application, audit_data.application_id)
        if not application:
            raise HTTPException(status_code=400, detail="Application not found")

        # Create audit
        audit = Audit(
            name=audit_data.name,
            description=audit_data.description,
        )

        session.add(audit)
        session.flush()

        # Create audit user association
        audit_user = MappingAuditUser(
            audit_id=audit.id,
            user_id=current_user_id
        )
        session.add(audit_user)
        session.flush()

        # Create initial audit outcome for user
        audit_outcome = MappingAuditOutcomeUser(
            user_audit_id=audit_user.id,
            audit_id=audit.id,
            status=0,  # Not started
            recommendation=0,  # Not evaluated
            notes=None
        )
        session.add(audit_outcome)
        session.flush()

        # Create audit pipeline if requested
        pipeline = None
        if audit_data.create_pipeline:
            pipeline = AuditPipeline()
            session.add(pipeline)
            session.flush()

            # Link pipeline to audit
            pipeline_audit = MappingAuditPipelineAudit(
                audit_pipeline=pipeline.id,
                audit_id=audit.id
            )
            session.add(pipeline_audit)
            session.flush()

        # Associate models if provided
        model_associations = []
        if audit_data.model_ids:
            for model_id in audit_data.model_ids:
                # Verify model exists
                model = session.get(Modelmetadata, model_id)
                if not model:
                    continue  # Skip invalid models

                mapping = MappingAuditModel(
                    model_id=model_id,
                    audit_id=audit.id
                )
                session.add(mapping)
                model_associations.append(mapping)

            session.flush()

        # Create application-audit mapping
        app_audit_mapping = MappingAuditApplication(
            audit_id=audit.id,
            application_id=audit_data.application_id
        )
        session.add(app_audit_mapping)

        session.commit()

        return {
            "id": audit.id,
            "name": audit.name,
            "description": audit.description,
            "status": audit_outcome.status,
            "recommendation": None,  # Recommendation is now per user
            "application_id": audit_data.application_id,
            "application_name": application.name,
            "pipeline_created": pipeline.id if pipeline else None,
            "models_associated": len(model_associations),
            "model_association_ids": [ma.id for ma in model_associations],
            "message": "Audit created successfully with model associations and pipeline"
        }

    except HTTPException:
        session.rollback()
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=400, detail=f"Error creating complete audit: {str(e)}")
