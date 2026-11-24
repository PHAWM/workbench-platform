"""View service functions for file retrieval"""
from typing import Any, Dict, Tuple
from fastapi import HTTPException
from sqlmodel import Session, select
from pathlib import Path

from src.models import *
from src.services.utility_service.s3_storage_service import get_storage_manager, S3StorageManager


def view_dataset_file_comprehensive(
    audit_id: int,
    filename: str,
    current_user_id: str,
    session: Session,
    tenant_id: str | None = None
) -> Tuple[str, str]:
    """
    Retrieve an uploaded dataset file for viewing/download.
    Returns (file_path_or_temp_path, filename).
    For S3, file_path is a temporary file that the caller should delete after use.
    """
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

    file_mappings = session.exec(
        select(MappingOutputEvaluationUser, OutputEvaluationData)
        .join(OutputEvaluationData)
        .where(MappingOutputEvaluationUser.user_audit_id == user_audit.id)
    ).all()

    storage_manager = get_storage_manager(tenant_id)
    is_s3 = isinstance(storage_manager, S3StorageManager)

    for mapping, eval_data in file_mappings:
        location = eval_data.location

        if is_s3:
            # location is an S3 prefix — search for a matching filename under it
            s3_files = storage_manager.list_files(location)
            for f in s3_files:
                if f["file_name"] == filename:
                    suffix = "." + filename.rsplit(".", 1)[-1] if "." in filename else ""
                    tmp_path = storage_manager.download_to_temp(f["key"], suffix=suffix)
                    return tmp_path, filename
        else:
            file_path = Path(location)
            if file_path.name == filename and file_path.exists():
                return str(file_path), file_path.name

    raise HTTPException(
        status_code=404,
        detail=f"File '{filename}' not found or not associated with this user and audit"
    )


def view_audit_file_comprehensive(
    audit_id: int,
    filename: str,
    current_user_id: str,
    session: Session,
    tenant_id: str | None = None
) -> Tuple[str, str]:
    """
    Retrieve an audit input file or results.csv for viewing/download.
    Returns (file_path_or_temp_path, filename).
    For S3, file_path is a temporary file that the caller should delete after use.
    """
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

    storage_manager = get_storage_manager(tenant_id)
    is_s3 = isinstance(storage_manager, S3StorageManager)

    if is_s3:
        suffix = "." + filename.rsplit(".", 1)[-1] if "." in filename else ""

        # Check audit input prefix first
        audit_input_prefix = storage_manager.get_audit_input_path(str(audit_id))
        candidate_key = audit_input_prefix.rstrip("/") + "/" + filename
        if storage_manager.file_exists(candidate_key):
            tmp_path = storage_manager.download_to_temp(candidate_key, suffix=suffix)
            return tmp_path, filename

        # Check results.csv at audit root
        if filename == "results.csv":
            results_key = storage_manager.get_audit_results_path(str(audit_id))
            if storage_manager.file_exists(results_key):
                tmp_path = storage_manager.download_to_temp(results_key, suffix=suffix)
                return tmp_path, filename

        # Check user's output evaluation input directory
        user_prefix = f"users/{current_user_id}/output_evaluation/audit_{audit_id}/input/{filename}"
        if storage_manager.file_exists(user_prefix):
            tmp_path = storage_manager.download_to_temp(user_prefix, suffix=suffix)
            return tmp_path, filename

        raise HTTPException(
            status_code=404,
            detail=f"File '{filename}' not found in audit directory or user uploads"
        )

    else:
        # Local filesystem
        if filename == "results.csv":
            file_path = Path(f"storage/audits/audit_{audit_id}/results.csv")
        else:
            file_path = Path(f"storage/audits/audit_{audit_id}/input/{filename}")
            if not file_path.exists():
                user_file_path = Path(f"storage/users/{current_user_id}/output_evaluation/audit_{audit_id}/input/{filename}")
                if user_file_path.exists():
                    file_path = user_file_path

        # Security: prevent directory traversal
        resolved_path = file_path.resolve()
        audit_base = Path(f"storage/audits/audit_{audit_id}").resolve()
        user_base = Path(f"storage/users/{current_user_id}/output_evaluation/audit_{audit_id}").resolve()

        if not (str(resolved_path).startswith(str(audit_base)) or
                str(resolved_path).startswith(str(user_base))):
            raise HTTPException(status_code=403, detail="Access denied: Invalid file path")

        if not file_path.exists():
            raise HTTPException(
                status_code=404,
                detail=f"File '{filename}' not found in audit directory or user uploads"
            )

        return str(file_path), file_path.name
