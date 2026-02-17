"""Application service module for audit-related application operations"""
from typing import Dict, List, Optional, Tuple, Any
from fastapi import HTTPException
from sqlmodel import Session, select

from src.models import *


# ============= HELPER FUNCTIONS =============

def get_audit_status(audit_id: int, user_audit_id: int, session: Session) -> Tuple[int, str, float]:
    """
    Calculate audit status based on event evaluations.

    This function determines the audit status by checking:
    - Total event-metric pairs for the audit
    - How many have been evaluated (status = 2)
    - Overall audit outcome status

    Args:
        audit_id: The ID of the audit
        user_audit_id: The ID of the user-audit mapping
        session: Database session

    Returns:
        Tuple of (status_code, status_text, completion_percentage)
        - status_code: 0 = Not Started, 1 = In Progress, 2 = Finished/Submitted
        - status_text: Human-readable status
        - completion_percentage: Percentage of evaluated event-metric pairs (0-100)
    """
    # Get all events for this audit and user
    events_status_statement = select(MappingEventsAuditStatus).where(
        MappingEventsAuditStatus.audit_id == audit_id,
        MappingEventsAuditStatus.user_audit_id == user_audit_id
    )
    event_statuses = session.exec(events_status_statement).all()

    if not event_statuses:
        return 0, "Not Started", 0.0

    # Check evaluation status
    evaluated_count = 0
    for es in event_statuses:
        if es.status == 2:
            evaluated_count += 1

    total_count = len(event_statuses)
    completion_percentage = (evaluated_count / total_count) * 100 if total_count > 0 else 0.0

    audit_status = session.exec(select(MappingAuditOutcomeUser.status).where(
        MappingAuditOutcomeUser.audit_id == audit_id,
        MappingAuditOutcomeUser.user_audit_id == user_audit_id
    )).first()

    if evaluated_count == 0:
        return audit_status, "Not Started", completion_percentage
    elif evaluated_count == total_count and audit_status < 2:
        return audit_status, "Finished", completion_percentage
    elif evaluated_count == total_count and audit_status == 2:
        return audit_status, "Submitted", completion_percentage
    else:
        return audit_status, "In Progress", completion_percentage


def get_user_audit_outcome(audit_id: int, user_audit_id: int, session: Session) -> Tuple[int, str]:
    """
    Get user audit outcome for a specific audit.

    This function retrieves the recommendation status for a user's audit.

    Args:
        audit_id: The ID of the audit
        user_audit_id: The ID of the user-audit mapping
        session: Database session

    Returns:
        Tuple of (recommendation_code, recommendation_text)
        - recommendation_code: 0 = Not Evaluated, 1 = Inconclusive, 2 = Fail, 3 = Pass
        - recommendation_text: Human-readable recommendation
    """
    outcome_statement = select(MappingAuditOutcomeUser).where(
        MappingAuditOutcomeUser.audit_id == audit_id,
        MappingAuditOutcomeUser.user_audit_id == user_audit_id
    )
    outcome = session.exec(outcome_statement).first()

    if not outcome:
        return 0, "Not Evaluated"

    recommendation_map = {
        0: "Not Evaluated",
        1: "Inconclusive",
        2: "Fail",
        3: "Pass"
    }
    return outcome.recommendation, recommendation_map.get(outcome.recommendation, "Unknown")


# ============= CRUD OPERATIONS =============

def create_application_comprehensive(
    name: str,
    description: str,
    url: str,
    access_type: Any,
    testing_evaluation: Any,
    deployment: Any,
    business_case: Any,
    legal_framework: Any,
    session: Session
) -> Application:
    """
    Create a new application entity.

    This service function handles creating an application with all its metadata.

    Args:
        name: Application name
        description: Application description
        url: Application URL
        access_type: Access type configuration
        testing_evaluation: Testing/evaluation configuration
        deployment: Deployment configuration
        business_case: Business case information
        legal_framework: Legal framework information
        session: Database session

    Returns:
        Created Application object

    Raises:
        Exception: If creation fails
    """
    db_entity = Application(
        name=name,
        description=description,
        url=url,
        access_type=access_type,
        testing_evaluation=testing_evaluation,
        deployment=deployment,
        business_case=business_case,
        legal_framework=legal_framework
    )

    session.add(db_entity)
    session.commit()
    session.refresh(db_entity)
    return db_entity


def update_application_comprehensive(
    application_id: int,
    application_update: 'ApplicationUpdate',
    session: Session
) -> Application:
    """
    Update an existing application entity.

    This service function handles updating application fields based on provided data.
    Only fields present in the update object will be modified.

    Args:
        application_id: The ID of the application to update
        application_update: Update data (only set fields will be updated)
        session: Database session

    Returns:
        Updated Application object

    Raises:
        HTTPException: If application not found (404)
    """
    statement = select(Application).where(Application.id == application_id)
    db_application = session.exec(statement).first()

    if not db_application:
        raise HTTPException(status_code=404, detail="Application not found")

    update_data = application_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_application, field, value)

    session.add(db_application)
    session.commit()
    session.refresh(db_application)

    return db_application
