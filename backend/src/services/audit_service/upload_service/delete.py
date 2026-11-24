"""Delete service functions for file deletion"""
from typing import Any, Dict
from fastapi import HTTPException
from sqlmodel import Session, select
from pathlib import Path

from src.models import *
from src.services.utility_service.s3_storage_service import get_storage_manager, S3StorageManager


def delete_dataset_file_comprehensive(
    audit_id: int,
    filename: str,
    current_user_id: str,
    session: Session,
    tenant_id: str | None = None
) -> Dict[str, Any]:
    """
    Delete an uploaded dataset file for a specific audit and user.

    This service function handles the entire business logic for deleting a dataset file,
    including:
    - User audit access verification
    - File lookup by filename
    - Physical file deletion
    - Database record deletion
    - Response construction

    Args:
        audit_id: The audit ID
        filename: The filename to delete
        current_user_id: The ID of the user deleting the file
        session: Database session

    Returns:
        Dictionary with message, filename, and audit_id

    Raises:
        HTTPException: If user has no access, file not found, or deletion fails
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

    # Delete the physical file if it exists
    sm = get_storage_manager(tenant_id)
    if isinstance(sm, S3StorageManager):
        try:
            sm.delete_file(eval_data.location)
        except Exception:
            pass
    else:
        file_path = Path(eval_data.location)
        if file_path.exists():
            file_path.unlink()

    # Delete database records
    session.delete(mapping)
    session.delete(eval_data)
    session.commit()

    return {
        "message": "File deleted successfully",
        "filename": filename,
        "audit_id": audit_id
    }
