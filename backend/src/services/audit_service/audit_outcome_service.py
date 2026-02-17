"""Audit outcome service module for managing audit outcomes"""
from typing import Dict, Any
from fastapi import HTTPException
from sqlmodel import Session, select

from src.models import *


def update_audit_outcome_comprehensive(
    audit_id: int,
    outcome_data: 'AuditOutcomeUpdate',
    current_user_id: str,
    session: Session
) -> Dict[str, Any]:
    """
    Update audit outcome for the current user.

    This service function handles the entire business logic for updating audit outcome,
    including:
    - User audit access verification
    - Audit outcome retrieval or creation
    - Status, recommendation, and notes update
    - Transaction management

    Args:
        audit_id: The ID of the audit
        outcome_data: Update data containing status, recommendation, notes
        current_user_id: The ID of the current user
        session: Database session

    Returns:
        Dictionary with success message and outcome_id

    Raises:
        HTTPException: If user has no access (403) or update fails (400)
    """
    # Verify user has access to this audit
    audit_user_check = select(MappingAuditUser).where(
        MappingAuditUser.audit_id == audit_id,
        MappingAuditUser.user_id == current_user_id
    )
    user_audit = session.exec(audit_user_check).first()
    if not user_audit:
        raise HTTPException(status_code=403, detail="Access denied to this audit")

    # Get or create audit outcome
    outcome_statement = select(MappingAuditOutcomeUser).where(
        MappingAuditOutcomeUser.audit_id == audit_id,
        MappingAuditOutcomeUser.user_audit_id == user_audit.id
    )
    outcome = session.exec(outcome_statement).first()

    if not outcome:
        # Create new outcome
        outcome = MappingAuditOutcomeUser(
            user_audit_id=user_audit.id,
            audit_id=audit_id,
            status=outcome_data.status,
            recommendation=outcome_data.recommendation,
            notes=outcome_data.notes
        )
        session.add(outcome)
    else:
        # Update existing outcome
        if "status" in outcome_data.model_dump(exclude_unset=True):
            outcome.status = outcome_data.status
        if "recommendation" in outcome_data.model_dump(exclude_unset=True):
            outcome.recommendation = outcome_data.recommendation
        if "notes" in outcome_data.model_dump(exclude_unset=True):
            outcome.notes = outcome_data.notes

    try:
        session.commit()
        return {"message": "Audit outcome updated successfully", "outcome_id": outcome.id}
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=400, detail=f"Error updating audit outcome: {str(e)}")


def get_audit_outcome_comprehensive(
    audit_id: int,
    current_user_id: str,
    session: Session
) -> Dict[str, Any]:
    """
    Get audit outcome for the current user.

    This service function handles the entire business logic for retrieving audit outcome,
    including:
    - User audit access verification
    - Audit outcome retrieval
    - Status and recommendation text mapping
    - Default values if outcome doesn't exist

    Args:
        audit_id: The ID of the audit
        current_user_id: The ID of the current user
        session: Database session

    Returns:
        Dictionary with status, status_text, recommendation, recommendation_text, notes

    Raises:
        HTTPException: If user has no access (403)
    """
    # Verify user has access to this audit
    audit_user_check = select(MappingAuditUser).where(
        MappingAuditUser.audit_id == audit_id,
        MappingAuditUser.user_id == current_user_id
    )
    user_audit = session.exec(audit_user_check).first()
    if not user_audit:
        raise HTTPException(status_code=403, detail="Access denied to this audit")

    # Get audit outcome
    outcome_statement = select(MappingAuditOutcomeUser).where(
        MappingAuditOutcomeUser.audit_id == audit_id,
        MappingAuditOutcomeUser.user_audit_id == user_audit.id
    )
    outcome = session.exec(outcome_statement).first()

    if not outcome:
        # Return default values if no outcome exists yet
        return {
            "status": 0,
            "status_text": "Not Started",
            "recommendation": 0,
            "recommendation_text": "Not Evaluated",
            "notes": None
        }

    status_map = {
        0: "Not Started",
        1: "In Progress",
        2: "Finished"
    }

    recommendation_map = {
        0: "Not Evaluated",
        1: "Inconclusive",
        2: "Fail",
        3: "Pass"
    }

    return {
        "status": outcome.status,
        "status_text": status_map.get(outcome.status, "Unknown"),
        "recommendation": outcome.recommendation,
        "recommendation_text": recommendation_map.get(outcome.recommendation, "Unknown"),
        "notes": outcome.notes
    }
