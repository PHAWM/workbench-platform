import uuid
from typing import Dict, List, Optional, Tuple, Any, Union
from fastapi import HTTPException, status
import secrets

from src.models import *

from sqlmodel import Session, select

def create_audit(session: Session, audit_request: AuditCreateRequest) -> AuditCreateResponse:
    """
    Create a new audit with application relationship
    
    Args:
        session: SQLModel database session
        audit_request: AuditCreateRequest containing audit details
        
    Returns:
        AuditCreateResponse with created audit details
        
    Raises:
        HTTPException: If application doesn't exist
    """
    
    # 1. Validate that the application exists
    application = session.get(Application, audit_request.application_id)
    if not application:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Application with ID {audit_request.application_id} not found"
        )
    
    # 2. Check if audit with same name already exists for this application
    existing_audit = session.exec(
        select(Audit).where(
            Audit.name == audit_request.name,
            Audit.application_id == audit_request.application_id
        )
    ).first()
    
    if existing_audit:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Audit with name '{audit_request.name}' already exists for this application"
        )
    
    try:
        # 3. Create the main audit record
        audit = Audit(
            name=audit_request.name,
            status=audit_request.status,
            recommendation=audit_request.recommendation,
            application_id=audit_request.application_id
        )
        session.add(audit)
        session.flush()  # Get the audit ID
        
        # 4. Create audit-application mapping
        audit_application_mapping = MappingAuditApplication(
            audit_id=audit.id,
            application_id=application.id
        )
        session.add(audit_application_mapping)
        
        # 5. Create audit pipeline (if needed)
        audit_pipeline = AuditPipeline()
        session.add(audit_pipeline)
        session.flush()
        
        # 6. Create audit pipeline-audit mapping
        audit_pipeline_mapping = MappingAuditPipelineAudit(
            audit_pipeline=audit_pipeline.id,
            audit_id=audit.id
        )
        session.add(audit_pipeline_mapping)
        
        # Commit all changes
        session.commit()
        
        return AuditCreateResponse(
            id=audit.id,
            name=audit.name,
            status=audit.status,
            recommendation=audit.recommendation,
            application_id=audit.application_id,
            application_name=application.name,
            message=f"Audit '{audit.name}' created successfully"
        )
        
    except Exception as e:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create audit: {str(e)}"
        )

def invite_user_to_audit(session: Session, audit_id: int, user_id: uuid.UUID) -> dict:
    """
    Invite a user to participate in an audit
    
    Args:
        session: SQLModel database session
        audit_id: ID of the audit
        user_id: ID of the user to invite
        
    Returns:
        Dictionary with invitation details
        
    Raises:
        HTTPException: If audit or user doesn't exist, or user already invited
    """
    
    # 1. Validate audit exists
    audit = session.get(Audit, audit_id)
    if not audit:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Audit with ID {audit_id} not found"
        )
    
    # 2. Validate user exists and is active
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {user_id} not found"
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"User {user.full_name} is not active"
        )
    
    # 3. Check if user is already assigned to this audit
    existing_assignment = session.exec(
        select(MappingAuditUser).where(
            MappingAuditUser.audit_id == audit_id,
            MappingAuditUser.user_id == user_id
        )
    ).first()
    
    if existing_assignment:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"User {user.full_name} is already assigned to this audit"
        )
    
    try:
        # 4. Create audit user assignment
        audit_user = MappingAuditUser(
            audit_id=audit_id,
            user_id=user_id
        )
        session.add(audit_user)
        session.flush()
        
        # 5. Create user invitation record
        user_invitation = UserInvitation(
            user_id=user_id,
            invitation_token=secrets.token_urlsafe(64),
            invitation_used=False
        )
        session.add(user_invitation)
        
        session.commit()
        
        return {
            "audit_id": audit_id,
            "audit_name": audit.name,
            "user_id": str(user_id),
            "user_name": user.full_name,
            "user_email": user.email,
            "invitation_token": user_invitation.invitation_token,
            "invitation_expires": user_invitation.expires_at.isoformat(),
            "message": f"User {user.full_name} successfully invited to audit '{audit.name}'"
        }
        
    except Exception as e:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to invite user to audit: {str(e)}"
        )
        
def get_audit_details(session: Session, audit_id: int, user_id) -> dict:
    """
    Get detailed information about an audit including all relationships
    
    Args:
        session: SQLModel database session
        audit_id: ID of the audit to retrieve
        
    Returns:
        Dictionary containing audit details with all relationships
    """
    
    # Get the audit
    audit, application_id = session.exec(select(Audit, MappingAuditApplication.application_id).join(MappingAuditApplication, Audit.id ==MappingAuditApplication.audit_id).where(MappingAuditApplication.audit_id == audit_id)).first()
    
    if not audit:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Audit with ID {audit_id} not found"
        )
    
    # Get application details
    application = session.get(Application, application_id)
    
    # Get assigned users (if any)
    audit_users_query = session.exec(
        select(MappingAuditUser, User).join(User).where(MappingAuditUser.audit_id == audit_id)
    )
    assigned_users = [
        {
            "id": str(user.id),
            "full_name": user.full_name,
            "email": user.email,
            "username": user.username
        }
        for audit_user, user in audit_users_query
    ]
    
    # Get events associated with this audit
    events_query = session.exec(
        select(Events, MappingEventsAuditStatus)
        .join(MappingEventsAuditStatus)
        .where(MappingEventsAuditStatus.audit_id == audit_id)
    )
    
    events = [
        {
            "id": event.id,
            "description": event.description,
            "cause": event.cause,
            "likelihood": event.likelihood,
            "magnitude": event.magnitude,
            "valence": event.valence,
            "recommendation": mapping.recommendation
        }
        for event, mapping in events_query
    ]
    
    audit_status =  session.exec(
        select(MappingAuditOutcomeUser)
        .join(MappingAuditUser, MappingAuditUser.id == MappingAuditOutcomeUser.user_audit_id)
        .where(
            MappingAuditUser.user_id == user_id,
            MappingAuditUser.audit_id == audit_id,
        )
    ).first()
    
    return {
        "audit": {
            "id": audit.id,
            "name": audit.name,
            "status": audit_status.status,
            "recommendation": audit_status.recommendation,
            "status_text": {0: "Not Started", 1: "In Progress", 2: "Finished"}[audit_status.status]
        },
        "application": {
            "id": application.id,
            "name": application.name,
            "description": application.description,
            "url": application.url
        } if application else None,
        # "assigned_users": assigned_users,
        "total_assigned_users": len(assigned_users),
        "events": events,
        "total_events": len(events)
    }