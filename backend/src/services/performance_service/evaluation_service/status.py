"""Status and submission service functions for evaluation"""
from typing import Any, Dict, List
from fastapi import HTTPException
from sqlmodel import Session, select

from src.models import *
from src.core.enums import STATUS_TEXT_MAP, RECOMMENDATION_TEXT_MAP


def get_status_summary_comprehensive(
    audit_id: int,
    current_user_id: str,
    session: Session
) -> 'AuditOutcomeResponse':
    """
    Get the status summary for an audit including all event-metric pairs.

    This service function handles the entire business logic for retrieving status summary,
    including:
    - User audit access verification
    - Event-metric status retrieval with joins
    - Status and recommendation mapping
    - User audit outcome creation or retrieval
    - Response construction

    Args:
        audit_id: The ID of the audit
        current_user_id: The ID of the user requesting the summary
        session: Database session

    Returns:
        AuditOutcomeResponse with audit_criteria list, recommendation, and notes

    Raises:
        HTTPException: If user has no access to the audit
    """
    user_metric_check = session.exec(
        select(MappingAuditUser)
        .where(
            MappingAuditUser.audit_id == audit_id,
            MappingAuditUser.user_id == current_user_id
        )
    ).first()

    if not user_metric_check:
        raise HTTPException(status_code=401, detail="Access denied")

    # Get the status of each pair of Events - Metrics
    base_status = session.exec(
        select(
            MappingEventsAuditStatus,
            Events.name,
            Metrics.name
        )
        .join(Events, MappingEventsAuditStatus.event_id == Events.id)
        .join(Metrics, MappingEventsAuditStatus.metric_id == Metrics.id)
        .where(
            MappingEventsAuditStatus.audit_id == audit_id,
            MappingEventsAuditStatus.user_audit_id == user_metric_check.id
        )
    ).all()

    # Add the status, names and recommendations of each pair of Events - Metrics
    audit_criteria = [
        AuditOutcomeStatus(
            audit_criteria_id=audit_status.id,
            event_name=event_name,
            metric_name=metric_name,
            recommendation=audit_status.recommendation if audit_status.recommendation is not None else 0,
            recommendation_text=RECOMMENDATION_TEXT_MAP.get(audit_status.recommendation, "Not Evaluated"),
            status=audit_status.status if audit_status.status is not None else 0,
            status_text=STATUS_TEXT_MAP.get(audit_status.status, "Unknown"),
            notes=audit_status.notes
        ).model_dump()
        for audit_status, event_name, metric_name in base_status
    ]

    # User Audit Outcome
    user_audit_outcome = session.exec(
        select(MappingAuditOutcomeUser)
        .where(
            MappingAuditOutcomeUser.user_audit_id == user_metric_check.id,
            MappingAuditOutcomeUser.audit_id == audit_id
        )
    ).first()

    # User Audit Outcome check if exists otherwise create
    if not user_audit_outcome:
        user_audit_outcome = MappingAuditOutcomeUser(
            user_audit_id=user_metric_check.id,
            audit_id=audit_id,
            status=1,
            recommendation=0,
            notes=None,
        )
        session.add(user_audit_outcome)
        session.flush()
        session.commit()

    return AuditOutcomeResponse(
        audit_criteria=audit_criteria,
        recommendation=user_audit_outcome.recommendation,
        recommendation_text=RECOMMENDATION_TEXT_MAP.get(user_audit_outcome.recommendation, "Unknown"),
        notes=user_audit_outcome.notes,
    )


def submit_audit_comprehensive(
    audit_id: int,
    submission: 'AuditSubmit',
    current_user_id: str,
    session: Session
) -> Dict[str, str]:
    """
    Submit audit with final recommendation and notes.

    This service function handles the entire business logic for submitting an audit,
    including:
    - User audit access verification
    - User audit outcome creation or update
    - Status update to "Finished" (status=2)
    - Recommendation and notes assignment
    - Response construction

    Args:
        audit_id: The ID of the audit
        submission: The audit submission data with recommendation and notes
        current_user_id: The ID of the user submitting the audit
        session: Database session

    Returns:
        Dictionary with success message

    Raises:
        HTTPException: If user has no access to the audit
    """
    user_metric_check = session.exec(
        select(MappingAuditUser)
        .where(
            MappingAuditUser.audit_id == audit_id,
            MappingAuditUser.user_id == current_user_id
        )
    ).first()

    if not user_metric_check:
        raise HTTPException(status_code=401, detail="Access denied")

    user_audit_outcome = session.exec(
        select(MappingAuditOutcomeUser)
        .where(
            MappingAuditOutcomeUser.user_audit_id == user_metric_check.id,
            MappingAuditOutcomeUser.audit_id == audit_id
        )
    ).first()

    if not user_audit_outcome:
        user_audit_outcome = MappingAuditOutcomeUser(
            user_audit_id=user_metric_check.id,
            audit_id=audit_id,
            status=2,
            recommendation=submission.recommendation,
            notes=submission.notes,
        )

    else:
        if submission.recommendation is not None:
            user_audit_outcome.recommendation = submission.recommendation
        if submission.notes is not None:
            user_audit_outcome.notes = submission.notes

        user_audit_outcome.status = 2

    session.add(user_audit_outcome)
    session.flush()
    session.commit()

    return {
        "message": "The Audit Outcome has been successfully submitted"
    }


def update_status_comprehensive(
    audit_id: int,
    updated_data: 'AuditStatusUpdate',
    current_user_id: str,
    session: Session
) -> Dict[str, Any]:
    """
    Update status for a single event-metric pair.

    This service function handles the entire business logic for updating audit status,
    including:
    - User audit access verification
    - Event-metric mapping retrieval
    - Recommendation and notes update
    - Status update to "Evaluated" (status=2)
    - Response construction

    Args:
        audit_id: The ID of the audit
        updated_data: The status update data with event_id, metric_id, recommendation, notes
        current_user_id: The ID of the user updating the status
        session: Database session

    Returns:
        Dictionary with message, event_id, audit_id, and updated_directly flag

    Raises:
        HTTPException: If user has no access or event-metric pair not found
    """
    user_metric_check = session.exec(
        select(MappingAuditUser)
        .where(
            MappingAuditUser.audit_id == audit_id,
            MappingAuditUser.user_id == current_user_id
        )
    ).first()

    if not user_metric_check:
        raise HTTPException(status_code=401, detail="Access denied")

    base_status = session.exec(
        select(MappingEventsAuditStatus)
        .where(
            MappingEventsAuditStatus.audit_id == audit_id,
            MappingEventsAuditStatus.event_id == updated_data.event_id,
            MappingEventsAuditStatus.metric_id == updated_data.metric_id,
            MappingEventsAuditStatus.user_audit_id == user_metric_check.id
        )
    ).first()

    if not base_status:
        raise HTTPException(status_code=404, detail="Event-Metric pair not found or access denied")

    if updated_data.recommendation is not None:
        base_status.recommendation = updated_data.recommendation
        base_status.status = 2
    if updated_data.notes is not None:
        base_status.notes = updated_data.notes

    session.add(base_status)
    session.commit()
    session.refresh(base_status)

    return {
        "message": "Audit Status has been updated",
        "event_id": updated_data.event_id,
        "audit_id": audit_id,
        "updated_directly": True,
    }


def update_status_batch_comprehensive(
    audit_id: int,
    batch_updated_data: 'BatchAuditStatusUpdate',
    current_user_id: str,
    session: Session
) -> Dict[str, Any]:
    """
    Update status for multiple event-metric pairs in batch.

    This service function handles the entire business logic for batch status updates,
    including:
    - User audit access verification
    - Multiple event-metric mappings retrieval
    - Batch recommendation and notes updates
    - Status updates to "Evaluated" (status=2)
    - Outcome evaluation values notes sync
    - Response construction with success/failure lists

    Args:
        audit_id: The ID of the audit
        batch_updated_data: List of status updates with event_id, metric_id, recommendation, notes
        current_user_id: The ID of the user updating the statuses
        session: Database session

    Returns:
        Dictionary with message, updated_status list, not_updated_status list, and updated_directly flag

    Raises:
        HTTPException: If user has no access to the audit
    """
    user_metric_check = session.exec(
        select(MappingAuditUser)
        .where(
            MappingAuditUser.audit_id == audit_id,
            MappingAuditUser.user_id == current_user_id
        )
    ).first()

    if not user_metric_check:
        raise HTTPException(status_code=401, detail="Access denied")

    updated_status = []
    not_updated_status = []

    for updated_data in batch_updated_data:
        # Update MappingEventsAuditStatus (audit status/recommendation)
        base_status = session.exec(
            select(MappingEventsAuditStatus)
            .where(
                MappingEventsAuditStatus.audit_id == audit_id,
                MappingEventsAuditStatus.event_id == updated_data.event_id,
                MappingEventsAuditStatus.metric_id == updated_data.metric_id,
                MappingEventsAuditStatus.user_audit_id == updated_data.user_audit_id
            )
        ).first()

        if not base_status:
            not_updated_status.append({
                "event_id": updated_data.event_id,
                "metric_id": updated_data.metric_id,
            })
        else:
            status_updated = False

            if updated_data.recommendation is not None:
                base_status.recommendation = updated_data.recommendation
                base_status.status = 2  # Mark as evaluated
                status_updated = True

            if updated_data.notes is not None:
                base_status.notes = updated_data.notes
                status_updated = True

            if status_updated:
                session.add(base_status)

            # Also update notes in MappingOutcomeEvaluationValues if it exists
            if updated_data.notes is not None:
                outcome_mapping = session.exec(
                    select(MappingOutcomeEvaluationValues)
                    .where(
                        MappingOutcomeEvaluationValues.event_id == updated_data.event_id,
                        MappingOutcomeEvaluationValues.metric_id == updated_data.metric_id,
                        MappingOutcomeEvaluationValues.user_audit_id == updated_data.user_audit_id,
                        MappingOutcomeEvaluationValues.audit_id == audit_id
                    )
                ).first()

                if outcome_mapping:
                    outcome_mapping.notes = updated_data.notes
                    session.add(outcome_mapping)

            if status_updated:
                updated_status.append({
                    "event_id": updated_data.event_id,
                    "metric_id": updated_data.metric_id,
                })

    # Commit all changes at once
    session.commit()

    return {
        "message": "Audit Status has been updated",
        "updated_status": updated_status,
        "not_updated_status": not_updated_status,
        "updated_directly": True,
    }
