"""List service functions for retrieving upload information"""
from typing import Any, Dict, List
from fastapi import HTTPException
from sqlmodel import Session, select
from pathlib import Path

from src.models import *
from .utils import get_storage_path

from src.services.utility_service.s3_storage_service import get_storage_manager, S3StorageManager


def list_uploaded_datasets_comprehensive(
    audit_id: int,
    current_user_id: str,
    session: Session,
    tenant_id: str | None = None
) -> Dict[str, Any]:
    """
    List all uploaded dataset files for a specific audit and user.
    Works with both local filesystem and S3 backends.
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

    storage_manager = get_storage_manager(tenant_id)
    is_s3 = isinstance(storage_manager, S3StorageManager)

    output_eval_mappings = session.exec(
        select(MappingOutputEvaluationUser, OutputEvaluationData)
        .join(OutputEvaluationData)
        .where(MappingOutputEvaluationUser.user_audit_id == user_audit.id)
    ).all()

    files = []
    for mapping, eval_data in output_eval_mappings:
        location = eval_data.location

        if is_s3:
            # location is an S3 key — get metadata from S3 object listing
            s3_files = storage_manager.list_files(location)
            for f in s3_files:
                files.append({
                    "id": eval_data.id,
                    "data_id": mapping.id,
                    "filename": f["file_name"],
                    "file_size": f["size"],
                    "upload_time": f["last_modified"].timestamp() if hasattr(f["last_modified"], "timestamp") else f["last_modified"],
                    "file_path": f["key"],
                })
        else:
            file_path = Path(location)
            if file_path.exists():
                files.append({
                    "id": eval_data.id,
                    "data_id": mapping.id,
                    "filename": file_path.name,
                    "file_size": file_path.stat().st_size,
                    "upload_time": file_path.stat().st_mtime,
                    "file_path": str(file_path),
                })

    return {
        "uploaded_files": files,
        "total_files": len(files),
        "audit_id": audit_id,
        "storage_type": "output_evaluation",
    }


def list_audit_files_comprehensive(
    audit_id: int,
    current_user_id: str,
    session: Session,
    tenant_id: str | None = None
) -> Dict[str, Any]:
    """
    List all input files for a specific audit.
    Works with both local filesystem and S3 backends.
    """
    storage_manager = get_storage_manager(tenant_id)
    is_s3 = isinstance(storage_manager, S3StorageManager)

    files = []

    if is_s3:
        prefix = storage_manager.get_audit_input_path(str(audit_id))
        s3_files = storage_manager.list_files(prefix)
        for f in s3_files:
            files.append({
                "filename": f["file_name"],
                "file_size": f["size"],
                "upload_time": f["last_modified"].timestamp() if hasattr(f["last_modified"], "timestamp") else f["last_modified"],
                "file_path": f["key"],
            })

        # Also check for results.csv at the audit root
        results_key = storage_manager.get_audit_results_path(str(audit_id))
        if storage_manager.file_exists(results_key):
            obj = storage_manager.list_files(results_key.rsplit("/", 1)[0] + "/")
            for f in obj:
                if f["file_name"] == "results.csv":
                    files.append({
                        "filename": "results.csv",
                        "file_size": f["size"],
                        "upload_time": f["last_modified"].timestamp() if hasattr(f["last_modified"], "timestamp") else f["last_modified"],
                        "file_path": results_key,
                    })
    else:
        storage_dir = get_storage_path("audit_input", audit_id=audit_id)
        storage_path = Path(storage_dir)

        if storage_path.exists():
            for file_path in storage_path.iterdir():
                if file_path.is_file():
                    files.append({
                        "filename": file_path.name,
                        "file_size": file_path.stat().st_size,
                        "upload_time": file_path.stat().st_mtime,
                        "file_path": str(file_path),
                    })

        results_path = Path(f"storage/audits/audit_{audit_id}/results.csv")
        if results_path.exists():
            files.append({
                "filename": "results.csv",
                "file_size": results_path.stat().st_size,
                "upload_time": results_path.stat().st_mtime,
                "file_path": str(results_path),
            })

    return {
        "files": files,
        "total_files": len(files),
        "audit_id": audit_id,
        "storage_type": "audit_input",
    }
