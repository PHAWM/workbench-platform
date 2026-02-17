"""List service functions for retrieving upload information"""
from typing import Any, Dict, List
from fastapi import HTTPException
from sqlmodel import Session, select
from pathlib import Path

from src.models import *
from .utils import get_storage_path


def list_uploaded_datasets_comprehensive(
    audit_id: int,
    current_user_id: str,
    session: Session
) -> Dict[str, Any]:
    """
    List all uploaded dataset files for a specific audit and user.

    This service function handles the entire business logic for listing uploaded datasets,
    including:
    - User audit access verification
    - Database query for uploaded files
    - File metadata extraction
    - Response construction

    Args:
        audit_id: The audit ID
        current_user_id: The ID of the user requesting the list
        session: Database session

    Returns:
        Dictionary with uploaded_files list, total_files count, audit_id, and storage_type

    Raises:
        HTTPException: If user has no access to the audit
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

    # Get files from database
    output_eval_mappings = session.exec(
        select(MappingOutputEvaluationUser, OutputEvaluationData)
        .join(OutputEvaluationData)
        .where(MappingOutputEvaluationUser.user_audit_id == user_audit.id)
    ).all()

    files = []
    for mapping, eval_data in output_eval_mappings:
        file_path = Path(eval_data.location)
        if file_path.is_file():
            files.append({
                "id": eval_data.id,
                "data_id": mapping.id,
                "filename": file_path.name,
                "file_size": file_path.stat().st_size,
                "upload_time": file_path.stat().st_mtime,
                "file_path": str(file_path)
            })

    return {
        "uploaded_files": files,
        "total_files": len(files),
        "audit_id": audit_id,
        "storage_type": "output_evaluation"
    }


def list_audit_files_comprehensive(
    audit_id: int,
    current_user_id: str,
    session: Session
) -> Dict[str, Any]:
    """
    List all input files for a specific audit.

    This service function handles the entire business logic for listing audit files,
    including:
    - Storage directory retrieval
    - File system scanning
    - Results.csv inclusion (at audit root, not in output folder)
    - File metadata extraction
    - Response construction

    Args:
        audit_id: The audit ID
        current_user_id: The ID of the user requesting the list
        session: Database session

    Returns:
        Dictionary with files list, total_files count, audit_id, and storage_type

    Raises:
        HTTPException: If operation fails
    """
    storage_dir = get_storage_path("audit_input", audit_id=audit_id)

    files = []
    storage_path = Path(storage_dir)

    if storage_path.exists():
        for file_path in storage_path.iterdir():
            if file_path.is_file():
                files.append({
                    "filename": file_path.name,
                    "file_size": file_path.stat().st_size,
                    "upload_time": file_path.stat().st_mtime,
                    "file_path": str(file_path)
                })

    # Also check for results.csv in the audit root
    results_path = Path(f"storage/audits/audit_{audit_id}/results.csv")
    if results_path.exists():
        files.append({
            "filename": "results.csv",
            "file_size": results_path.stat().st_size,
            "upload_time": results_path.stat().st_mtime,
            "file_path": str(results_path)
        })

    return {
        "files": files,
        "total_files": len(files),
        "audit_id": audit_id,
        "storage_type": "audit_input"
    }
