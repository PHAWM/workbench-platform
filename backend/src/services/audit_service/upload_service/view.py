"""View service functions for file retrieval"""
from typing import Any, Dict, Tuple
from fastapi import HTTPException
from sqlmodel import Session, select
from pathlib import Path

from src.models import *


def view_dataset_file_comprehensive(
    audit_id: int,
    filename: str,
    current_user_id: str,
    session: Session
) -> Tuple[Path, str]:
    """
    Retrieve an uploaded dataset file for viewing/download.

    This service function handles the entire business logic for retrieving a dataset file,
    including:
    - User audit access verification
    - File lookup by filename
    - File existence check
    - File path and name retrieval

    Args:
        audit_id: The audit ID
        filename: The filename to view
        current_user_id: The ID of the user viewing the file
        session: Database session

    Returns:
        Tuple of (file_path, filename) for FileResponse

    Raises:
        HTTPException: If user has no access, file not found, or retrieval fails
    """
    # Get user audit mapping
    user_audit = session.exec(
        select(MappingAuditUser)
        .where(
            MappingAuditUser.audit_id == audit_id,
            MappingAuditUser.user_id == current_user_id
        )
    ).first()

    if not user_audit:
        raise HTTPException(
            status_code=404,
            detail="User not associated with this audit"
        )

    # Get all files for this user and audit
    file_mappings = session.exec(
        select(MappingOutputEvaluationUser, OutputEvaluationData)
        .join(OutputEvaluationData)
        .where(MappingOutputEvaluationUser.user_audit_id == user_audit.id)
    ).all()

    # Find the file with matching filename
    file_mapping = None
    for mapping, eval_data in file_mappings:
        file_path = Path(eval_data.location)
        if file_path.name == filename:
            file_mapping = (mapping, eval_data)
            break

    if not file_mapping:
        raise HTTPException(
            status_code=404,
            detail=f"File '{filename}' not found or not associated with this user and audit"
        )

    mapping, eval_data = file_mapping
    file_path = Path(eval_data.location)

    # Check if file exists
    if not file_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"File '{filename}' not found on disk"
        )

    return file_path, file_path.name


def view_audit_file_comprehensive(
    audit_id: int,
    filename: str,
    current_user_id: str,
    session: Session
) -> Tuple[Path, str]:
    """
    Retrieve an audit input file or results.csv for viewing/download.

    This service function handles the entire business logic for retrieving an audit file,
    including:
    - User audit access verification
    - File location determination (audit input, user output evaluation, or results.csv)
    - Security check for directory traversal
    - File existence check
    - File path and name retrieval

    Args:
        audit_id: The audit ID
        filename: The filename to view
        current_user_id: The ID of the user viewing the file
        session: Database session

    Returns:
        Tuple of (file_path, filename) for FileResponse

    Raises:
        HTTPException: If user has no access, file not found, or access denied
    """
    # Verify user has access to this audit
    user_audit = session.exec(
        select(MappingAuditUser)
        .where(
            MappingAuditUser.audit_id == audit_id,
            MappingAuditUser.user_id == current_user_id
        )
    ).first()

    if not user_audit:
        raise HTTPException(
            status_code=403,
            detail="User not authorized to access this audit"
        )

    # Check if it's results.csv at audit root
    if filename == "results.csv":
        file_path = Path(f"storage/audits/audit_{audit_id}/results.csv")
    else:
        # Check in multiple possible locations:
        # 1. Audit input directory (common files like SAM audio)
        file_path = Path(f"storage/audits/audit_{audit_id}/input/{filename}")

        # 2. User's output evaluation input directory (user-uploaded files like Annif texts)
        if not file_path.exists():
            user_file_path = Path(f"storage/users/{current_user_id}/output_evaluation/audit_{audit_id}/input/{filename}")
            if user_file_path.exists():
                file_path = user_file_path

    # Security check: prevent directory traversal
    resolved_path = file_path.resolve()

    # Allow access to both audit directory and user's directory
    audit_base = Path(f"storage/audits/audit_{audit_id}").resolve()
    user_base = Path(f"storage/users/{current_user_id}/output_evaluation/audit_{audit_id}").resolve()

    is_in_audit_dir = str(resolved_path).startswith(str(audit_base))
    is_in_user_dir = str(resolved_path).startswith(str(user_base))

    if not (is_in_audit_dir or is_in_user_dir):
        raise HTTPException(
            status_code=403,
            detail="Access denied: Invalid file path"
        )

    # Check if file exists
    if not file_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"File '{filename}' not found in audit directory or user uploads"
        )

    return file_path, file_path.name
