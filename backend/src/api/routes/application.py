from typing import Any, List

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import col, delete, func, select

from src.api.deps import (
    SessionDep, get_current_user
)

from src.models import *
from src.services.audit_service import (
    application_service,
    audit_setup_service,
    audit_overview_service,
    audit_creation_service,
    audit_complete_service,
    audit_outcome_service
)

router = APIRouter(prefix="/audits", tags=["Audit Management"])


@router.get("/")
def get_all_audits_overview(session: SessionDep, current_user: User = Depends(get_current_user)):
    """Get all audits overview for the current user"""
    try:
        audit_overviews, status_summary = audit_overview_service.get_all_audits_overview_comprehensive(
            current_user_id=current_user.id,
            session=session
        )

        return AllAuditsOverviewResponse(
            audits=[AuditOverviewResponse(**audit) for audit in audit_overviews],
            total_audits=len(audit_overviews),
            status_summary=status_summary
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get audits overview: {str(e)}")


@router.get("/{audit_id}")
def get_audit_overview(audit_id: int, session: SessionDep, current_user: User = Depends(get_current_user)):
    """Get single audit overview with application details"""
    try:
        audit_data = audit_overview_service.get_audit_overview_comprehensive(
            audit_id=audit_id,
            current_user_id=current_user.id,
            session=session
        )

        return AuditOverviewResponse(**audit_data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get audit overview: {str(e)}")


@router.post("/")
def create_audit(
    audit_data: AuditCompleteCreate,
    session: SessionDep,
    current_user: User = Depends(get_current_user)
):
    """Create audit with model associations and pipeline setup in one call"""
    try:
        result = audit_creation_service.create_audit_comprehensive(
            audit_data=audit_data,
            current_user_id=current_user.id,
            session=session
        )

        return AuditCompleteCreateResponse(**result)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create audit: {str(e)}")


@router.get("/{audit_id}/complete")
def get_audit_complete(
    audit_id: int | str,
    session: SessionDep,
    current_user: User = Depends(get_current_user)
):
    """Get comprehensive audit information with all relationships"""
    try:
        if isinstance(audit_id, str):
            # Get all audits for user (when audit_id is "all" or similar string)
            audit_list = audit_complete_service.get_all_audits_complete_comprehensive(
                current_user_id=current_user.id,
                session=session
            )
            return [AuditCompleteResponse(**audit) for audit in audit_list]
        else:
            # Get single audit
            audit_data = audit_complete_service.get_single_audit_complete_comprehensive(
                audit_id=audit_id,
                current_user_id=current_user.id,
                session=session
            )
            return AuditCompleteResponse(**audit_data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get complete audit: {str(e)}")


@router.get("/{audit_id}/summary")
async def get_audit_summary(audit_id: int, session: SessionDep, current_user: User = Depends(get_current_user)):
    """Get audit summary with serialized JSON fields"""
    try:
        # Verify user has access to this audit
        audit_user_check = select(MappingAuditUser).where(
            MappingAuditUser.audit_id == audit_id,
            MappingAuditUser.user_id == current_user.id
        )
        if not session.exec(audit_user_check).first():
            raise HTTPException(status_code=403, detail="Access denied to this audit")

        audit_details = audit_setup_service.get_audit_details(session, audit_id, current_user.id)

        # Get application with JSON fields serialized
        application = session.get(Application, audit_details["audit"]["id"])
        if application:
            # Serialize specific JSON fields
            testing_evaluation_json = application.model_dump_json(include={"testing_evaluation"})
            deployment_json = application.model_dump_json(include={"deployment"})

            return {
                "audit_summary": audit_details,
                "application_testing": testing_evaluation_json,
                "application_deployment": deployment_json
            }

        return audit_details
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get audit summary: {str(e)}")


@router.put("/{audit_id}/outcome")
def update_audit_outcome(
    audit_id: int,
    outcome_data: AuditOutcomeUpdate,
    session: SessionDep,
    current_user: User = Depends(get_current_user)
):
    """Update audit outcome for the current user"""
    try:
        result = audit_outcome_service.update_audit_outcome_comprehensive(
            audit_id=audit_id,
            outcome_data=outcome_data,
            current_user_id=current_user.id,
            session=session
        )
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update audit outcome: {str(e)}")


@router.get("/{audit_id}/outcome")
def get_audit_outcome(
    audit_id: int,
    session: SessionDep,
    current_user: User = Depends(get_current_user)
):
    """Get audit outcome for the current user"""
    try:
        result = audit_outcome_service.get_audit_outcome_comprehensive(
            audit_id=audit_id,
            current_user_id=current_user.id,
            session=session
        )
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get audit outcome: {str(e)}")


# Application endpoints
@router.post("/applications/")
def create_application(name: str, description: str, url, access_type, testing_evaluation, deployment, business_case, legal_framework, session: SessionDep):
    """Create a new application"""
    try:
        db_entity = application_service.create_application_comprehensive(
            name=name,
            description=description,
            url=url,
            access_type=access_type,
            testing_evaluation=testing_evaluation,
            deployment=deployment,
            business_case=business_case,
            legal_framework=legal_framework,
            session=session
        )

        return db_entity

    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=400, detail=f"Error creating application: {str(e)}")


@router.put("/applications/{application_id}")
def update_application(application_id: int, application_update: ApplicationUpdate, session: SessionDep):
    """Update an existing application"""
    try:
        db_application = application_service.update_application_comprehensive(
            application_id=application_id,
            application_update=application_update,
            session=session
        )
        return db_application
    except HTTPException:
        session.rollback()
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=400, detail=f"Error updating application: {str(e)}")
