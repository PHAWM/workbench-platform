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

def invite_user_to_audit(
    session: Session,
    audit_id: int,
    email: str,
    inviter_name: Optional[str] = None,
    tenant_id: Optional[str] = None,
) -> dict:
    """
    Invite a user to an audit as an auditor, by email address.

    Two paths depending on whether the email is registered:

    - **Not registered**: creates a placeholder User record (inactive, no password),
      links them to the audit, generates an invitation token, and sends a
      registration invitation email (set-password link).

    - **Already registered**: links them directly to the audit with the auditor role
      and sends a simple audit notification email (no token, no password step —
      they log in with their existing credentials).

    Args:
        session: SQLModel database session
        audit_id: ID of the audit
        email: Email address of the user to invite
        inviter_name: Display name of the instigator (shown in the email)
    """
    from src.services import user_service
    from src.services.email_service import send_invitation_email, send_audit_notification_email

    # 1. Validate audit exists
    audit = session.get(Audit, audit_id)
    if not audit:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Audit with ID {audit_id} not found",
        )

    # 2. Resolve the 'auditor' role once — needed for both paths
    auditor_role = session.exec(
        select(AuditRoles).where(AuditRoles.role == "auditor")
    ).first()
    if not auditor_role:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="'auditor' role not found in database. Run migrations first.",
        )

    # 3. Look up user by email
    user = user_service.get_user_by_email(session=session, email=email)
    is_new_user = user is None

    try:
        if is_new_user:
            # --- PATH A: unregistered ---
            # Create a minimal placeholder account so MappingAuditUser can be created.
            # is_active=False and hashed_password is a placeholder until they set it.
            user = User(
                email=email.lower(),
                full_name=email.split("@")[0],   # placeholder name
                username=email.split("@")[0],
                hashed_password="",              # no password until they accept
                is_active=False,
                is_verified=False,
            )
            session.add(user)
            session.flush()
        else:
            # --- PATH B: already registered ---
            if not user.is_active:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"User account for '{email}' exists but is inactive.",
                )

        # 4. Check for duplicate audit assignment
        existing = session.exec(
            select(MappingAuditUser).where(
                MappingAuditUser.audit_id == audit_id,
                MappingAuditUser.user_id == user.id,
            )
        ).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"'{email}' is already assigned to this audit",
            )

        # 5. Link user to audit with auditor role
        audit_user = MappingAuditUser(
            audit_id=audit_id,
            user_id=user.id,
            roles_id=auditor_role.id,
        )
        session.add(audit_user)
        session.flush()

        # 6. Create initial outcome row so get_audit_status never sees a NULL status
        session.add(MappingAuditOutcomeUser(
            user_audit_id=audit_user.id,
            audit_id=audit_id,
            status=0,
            recommendation=0,
            notes=None,
        ))
        session.flush()

        invitation_token = None
        invitation_expires = None

        if is_new_user:
            # 6a. Generate invitation token for registration
            user_invitation = UserInvitation(
                user_id=user.id,
                invitation_token=secrets.token_urlsafe(64),
                invitation_used=False,
            )
            session.add(user_invitation)
            session.flush()
            invitation_token = user_invitation.invitation_token
            invitation_expires = user_invitation.expires_at.isoformat()

        session.commit()

        # 7. Send email — non-fatal
        try:
            if is_new_user:
                send_invitation_email(
                    email_to=email,
                    token=invitation_token,
                    inviter_name=inviter_name,
                    tenant_id=tenant_id,
                )
            else:
                send_audit_notification_email(
                    email_to=user.email,
                    audit_name=audit.name,
                    inviter_name=inviter_name,
                    tenant_id=tenant_id,
                )
        except Exception:
            pass

        return {
            "audit_id": audit_id,
            "audit_name": audit.name,
            "user_id": str(user.id),
            "user_email": email,
            "role": "auditor",
            "is_new_user": is_new_user,
            "invitation_token": invitation_token,
            "invitation_expires": invitation_expires,
            "message": (
                f"Invitation sent to '{email}'. They will receive an email to set their password and join the audit."
                if is_new_user else
                f"'{email}' has been added to audit '{audit.name}' and notified by email."
            ),
        }

    except HTTPException:
        session.rollback()
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to invite user to audit: {str(e)}",
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