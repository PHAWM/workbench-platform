"""Upload service functions for file uploads"""
from typing import Any, Dict, List
from fastapi import HTTPException, UploadFile
from sqlmodel import Session, select
from pathlib import Path
import uuid

from src.models import *
from src.services.utility_service.s3_storage_service import get_storage_manager, S3StorageManager
from .utils import (
    ensure_directory_exists,
    extract_csv_headers,
    create_underlying_features_for_dataset,
    get_storage_path,
    check_duplicate_file,
    get_acceptable_formats_for_audit
)


def _save_upload(file: UploadFile, storage_dir: str, safe_filename: str, tenant_id: str | None = None) -> tuple[str, int]:
    """Save an uploaded file to local disk or S3. Returns (location_str, file_size)."""
    sm = get_storage_manager(tenant_id)
    contents = file.file.read()
    file_size = len(contents)

    if isinstance(sm, S3StorageManager):
        prefix = storage_dir.lstrip("/")
        if prefix.startswith("storage/"):
            prefix = prefix[len("storage/"):]
        if not prefix.endswith("/"):
            prefix += "/"
        key = prefix + safe_filename
        sm.write_file(key, contents, content_type=file.content_type or "application/octet-stream")
        location = key
    else:
        file_path = Path(storage_dir) / safe_filename
        file_path.write_bytes(contents)
        location = str(file_path)

    return location, file_size


def upload_dataset_comprehensive(
    file: UploadFile,
    audit_id: int,
    current_user_id: str,
    session: Session,
    tenant_id: str | None = None
) -> Dict[str, Any]:
    """
    Upload a dataset file to the evaluation system.

    This service function handles the entire business logic for uploading a dataset file,
    including:
    - User audit access verification
    - File type validation
    - Storage path management
    - Duplicate file checking
    - File saving with unique identifiers
    - Database record creation

    Args:
        file: The uploaded file
        audit_id: The audit ID for mapping
        current_user_id: The ID of the user uploading the file
        session: Database session

    Returns:
        Dictionary with upload status, filename, file_size, file_path, and data_id

    Raises:
        HTTPException: If user has no access, file type invalid, or duplicate file exists
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

    # Get acceptable formats from the model associated with this audit
    model_formats = get_acceptable_formats_for_audit(session, audit_id)

    # Use model formats if available, otherwise fall back to default allowed extensions
    if model_formats:
        # Model formats are stored without dots (e.g., ['txt', 'html']), add dots for comparison
        allowed_extensions = {f'.{fmt.lower()}' for fmt in model_formats}
    else:
        # Default fallback if no model formats are specified
        allowed_extensions = {'.csv', '.json', '.xlsx', '.txt', '.parquet', '.wav', '.html', '.mp3'}

    file_extension = Path(file.filename).suffix.lower()

    if file_extension not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"File type {file_extension} not allowed. Allowed types: {', '.join(allowed_extensions)}"
        )

    # Get storage path and ensure directory exists
    storage_dir = get_storage_path("output_evaluation", user_id=current_user_id, audit_id=audit_id)
    ensure_directory_exists(storage_dir)

    # Check for duplicate file
    is_duplicate, existing_filename = check_duplicate_file(storage_dir, file.filename, tenant_id=tenant_id)
    if is_duplicate:
        raise HTTPException(
            status_code=400,
            detail=f"A file with the same name '{file.filename}' already exists as '{existing_filename}'. Please delete the existing file or rename your file before uploading."
        )

    # Generate safe filename with unique identifier to avoid conflicts
    file_stem = Path(file.filename).stem
    file_suffix = Path(file.filename).suffix
    unique_id = str(uuid.uuid4())[:8]
    safe_filename = f"{file_stem}_{unique_id}{file_suffix}"

    # Save the uploaded file (local or S3)
    file_location, file_size = _save_upload(file, storage_dir, safe_filename, tenant_id=tenant_id)

    # Create database records
    output_eval_data = OutputEvaluationData(location=file_location)
    session.add(output_eval_data)
    session.flush()

    output_eval_user = MappingOutputEvaluationUser(
        user_audit_id=user_audit.id,
        output_eval_id=output_eval_data.id
    )

    session.add(output_eval_user)
    session.flush()

    # Get the audit instigator's user_audit_id to find event-metric pairs
    audit_instigator = session.exec(
        select(MappingAuditUser)
        .join(AuditRoles, AuditRoles.id == MappingAuditUser.roles_id)
        .where(
            MappingAuditUser.audit_id == audit_id,
            AuditRoles.role == 'audit_instigator'
        )
    ).first()

    instigator_user_audit_id = audit_instigator.id if audit_instigator else user_audit.id

    # Get all event-metric pairs for this audit
    event_metric_pairs = session.exec(
        select(
            MappingEventsAuditStatus.event_id,
            MappingEventsAuditStatus.metric_id
        )
        .where(
            MappingEventsAuditStatus.audit_id == audit_id,
            MappingEventsAuditStatus.user_audit_id == instigator_user_audit_id
        )
    ).all()

    # Create MappingOutcomeEvaluationValues records for each event-metric pair
    created_outcome_ids = []
    for event_id, metric_id in event_metric_pairs:
        # Check if record already exists
        existing_outcome = session.exec(
            select(MappingOutcomeEvaluationValues)
            .where(
                MappingOutcomeEvaluationValues.data_id == output_eval_data.id,
                MappingOutcomeEvaluationValues.audit_id == audit_id,
                MappingOutcomeEvaluationValues.user_audit_id == user_audit.id,
                MappingOutcomeEvaluationValues.event_id == event_id,
                MappingOutcomeEvaluationValues.metric_id == metric_id
            )
        ).first()

        if not existing_outcome:
            new_outcome = MappingOutcomeEvaluationValues(
                metric_id=metric_id,
                event_id=event_id,
                audit_id=audit_id,
                user_audit_id=user_audit.id,
                data_id=output_eval_data.id,
                output={},
                meet_requirement=0,
                notes=""
            )
            session.add(new_outcome)
            session.flush()
            created_outcome_ids.append(new_outcome.id)

    session.commit()
    session.refresh(output_eval_user)

    return {
        "message": "Dataset uploaded successfully",
        "filename": safe_filename,
        "original_filename": file.filename,
        "file_size": file_size,
        "file_path": file_location,
        "content_type": file.content_type,
        "storage_type": "output_evaluation",
        "data_id": output_eval_user.id,
        "outcome_records_created": len(created_outcome_ids)
    }


def upload_multiple_datasets_comprehensive(
    files: List[UploadFile],
    audit_id: int,
    current_user_id: str,
    session: Session,
    tenant_id: str | None = None
) -> Dict[str, Any]:
    """
    Upload multiple dataset files including metadata.csv.

    This service function handles the entire business logic for uploading multiple files,
    including:
    - User audit access verification
    - File type validation for each file
    - Storage path management
    - Duplicate file checking
    - File saving with unique identifiers
    - Metadata.csv processing and header extraction
    - Dataset creation or lookup
    - Underlying features creation from metadata
    - Database record creation

    Args:
        files: List of uploaded files
        audit_id: The audit ID for mapping
        current_user_id: The ID of the user uploading the files
        session: Database session

    Returns:
        Dictionary with upload status, uploaded_files list, failed_files list, dataset_id, and features_created

    Raises:
        HTTPException: If user has no access or upload fails
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

    # Get the audit instigator's user_audit_id to find event-metric pairs
    audit_instigator = session.exec(
        select(MappingAuditUser)
        .join(AuditRoles, AuditRoles.id == MappingAuditUser.roles_id)
        .where(
            MappingAuditUser.audit_id == audit_id,
            AuditRoles.role == 'audit_instigator'
        )
    ).first()

    instigator_user_audit_id = audit_instigator.id if audit_instigator else user_audit.id

    # Get all event-metric pairs for this audit (for creating MappingOutcomeEvaluationValues)
    event_metric_pairs = session.exec(
        select(
            MappingEventsAuditStatus.event_id,
            MappingEventsAuditStatus.metric_id
        )
        .where(
            MappingEventsAuditStatus.audit_id == audit_id,
            MappingEventsAuditStatus.user_audit_id == instigator_user_audit_id
        )
    ).all()

    # Get acceptable formats from the model associated with this audit
    model_formats = get_acceptable_formats_for_audit(session, audit_id)

    # Use model formats if available, otherwise fall back to default allowed extensions
    if model_formats:
        # Model formats are stored without dots (e.g., ['txt', 'html']), add dots for comparison
        allowed_extensions = {f'.{fmt.lower()}' for fmt in model_formats}
    else:
        # Default fallback if no model formats are specified
        allowed_extensions = {'.csv', '.json', '.xlsx', '.txt', '.parquet', '.wav'}

    # Get storage path and ensure directory exists
    storage_dir = get_storage_path("output_evaluation", user_id=current_user_id, audit_id=audit_id)
    ensure_directory_exists(storage_dir)

    uploaded_files = []
    failed_files = []
    metadata_csv_path = None

    # First pass: save all files
    for file in files:
        try:
            # Validate file type
            file_extension = Path(file.filename).suffix.lower()

            if file_extension not in allowed_extensions:
                failed_files.append({
                    "filename": file.filename,
                    "error": f"File type {file_extension} not allowed. Allowed types: {', '.join(allowed_extensions)}"
                })
                continue

            # Check for duplicate file
            is_duplicate, existing_filename = check_duplicate_file(storage_dir, file.filename, tenant_id=tenant_id)
            if is_duplicate:
                failed_files.append({
                    "filename": file.filename,
                    "error": f"A file with the same name already exists as '{existing_filename}'"
                })
                continue

            # Generate unique filename
            file_stem = Path(file.filename).stem
            file_suffix = Path(file.filename).suffix
            unique_id = str(uuid.uuid4())[:8]
            safe_filename = f"{file_stem}_{unique_id}{file_suffix}"

            # Save file (local or S3)
            file_location, file_size = _save_upload(file, storage_dir, safe_filename, tenant_id=tenant_id)

            # Track metadata.csv path but don't create database record for it
            if file.filename.lower() == "metadata.csv":
                # For S3, store key; for local, keep as Path for extract_csv_headers
                sm = get_storage_manager(tenant_id)
                metadata_csv_path = file_location if isinstance(sm, S3StorageManager) else Path(file_location)
                uploaded_files.append({
                    "filename": safe_filename,
                    "original_filename": file.filename,
                    "file_size": file_size,
                    "status": "success (metadata only)"
                })
                continue  # Skip database record creation for metadata.csv

            # Create database records only for non-metadata files
            output_eval_data = OutputEvaluationData(location=file_location)
            session.add(output_eval_data)
            session.flush()

            output_eval_user = MappingOutputEvaluationUser(
                user_audit_id=user_audit.id,
                output_eval_id=output_eval_data.id
            )
            session.add(output_eval_user)
            session.flush()

            # Create MappingOutcomeEvaluationValues records for each event-metric pair
            outcome_records_created = 0
            for event_id, metric_id in event_metric_pairs:
                # Check if record already exists
                existing_outcome = session.exec(
                    select(MappingOutcomeEvaluationValues)
                    .where(
                        MappingOutcomeEvaluationValues.data_id == output_eval_data.id,
                        MappingOutcomeEvaluationValues.audit_id == audit_id,
                        MappingOutcomeEvaluationValues.user_audit_id == user_audit.id,
                        MappingOutcomeEvaluationValues.event_id == event_id,
                        MappingOutcomeEvaluationValues.metric_id == metric_id
                    )
                ).first()

                if not existing_outcome:
                    new_outcome = MappingOutcomeEvaluationValues(
                        metric_id=metric_id,
                        event_id=event_id,
                        audit_id=audit_id,
                        user_audit_id=user_audit.id,
                        data_id=output_eval_data.id,
                        output={},
                        meet_requirement=0,
                        notes=""
                    )
                    session.add(new_outcome)
                    outcome_records_created += 1

            session.flush()

            uploaded_files.append({
                "filename": safe_filename,
                "original_filename": file.filename,
                "file_size": file_size,
                "status": "success",
                "data_id": output_eval_user.id,
                "outcome_records_created": outcome_records_created
            })

        except Exception as e:
            failed_files.append({
                "filename": file.filename,
                "status": "failed",
                "error": str(e)
            })

    # Second pass: process metadata.csv and create dataset if found
    dataset_id = None
    features_created = []

    # Resolve metadata.csv for header extraction (works for both local and S3)
    _metadata_readable = None
    sm = get_storage_manager(tenant_id)
    if metadata_csv_path:
        if isinstance(sm, S3StorageManager):
            import tempfile, os
            _csv_bytes = sm.read_file(metadata_csv_path if isinstance(metadata_csv_path, str) else str(metadata_csv_path))
            _tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".csv")
            _tmp.write(_csv_bytes)
            _tmp.close()
            _metadata_readable = Path(_tmp.name)
        else:
            _metadata_readable = metadata_csv_path

    if _metadata_readable and _metadata_readable.exists():
        try:
            # Extract headers from metadata.csv
            headers = extract_csv_headers(_metadata_readable)
            if isinstance(sm, S3StorageManager):
                import os as _os
                _os.unlink(_metadata_readable)

            if headers:
                # Check if dataset already exists for this audit
                audit_pipeline = session.exec(
                    select(MappingModelDatasetAudit)
                    .join(MappingAuditPipelineAudit, MappingModelDatasetAudit.auditpipeline == MappingAuditPipelineAudit.audit_pipeline)
                    .where(MappingAuditPipelineAudit.audit_id == audit_id)
                ).first()

                # Get existing features to avoid duplicates
                existing_features = session.exec(
                    select(UnderlyingFeatures.feature_name)
                ).all()
                existing_feature_names = set(existing_features)

                if audit_pipeline and audit_pipeline.dataset_id:
                    # Use existing dataset
                    dataset_id = audit_pipeline.dataset_id
                else:
                    # Create new dataset metadata
                    new_dataset = DatasetMetadata(
                        purpose="output_evaluation",
                        copyright_agreement=True
                    )
                    session.add(new_dataset)
                    session.flush()
                    dataset_id = new_dataset.id

                    # Update the audit pipeline with the new dataset
                    if audit_pipeline:
                        audit_pipeline.dataset_id = dataset_id
                        session.add(audit_pipeline)

                # Create underlying features for the dataset
                feature_ids = create_underlying_features_for_dataset(
                    session,
                    dataset_id,
                    headers,
                    existing_feature_names
                )
                features_created = headers

        except Exception as e:
            print(f"Error processing metadata.csv: {e}")

    session.commit()

    return {
        "message": f"Processed {len(files)} files",
        "uploaded_files": uploaded_files,
        "failed_files": failed_files,
        "storage_type": "output_evaluation",
        "metadata_processed": metadata_csv_path is not None,
        "features_created": features_created,
        "dataset_id": dataset_id
    }


def upload_audit_input_comprehensive(
    files: List[UploadFile],
    audit_id: int,
    current_user_id: str,
    session: Session,
    tenant_id: str | None = None
) -> Dict[str, Any]:
    """
    Upload one or more input files for an audit (audit instigator).

    Accepts any mix of data files + an optional metadata.csv.

    - All files are saved to audits/audit_{id}/input/ (S3 or local)
    - If metadata.csv is included:
        - Its columns are registered as UnderlyingFeatures
        - InputDatasetMetadata.location is set to the input directory
        - DatasetMetadata is created/linked if not already present
    """
    allowed_extensions = {'.csv', '.json', '.xlsx', '.txt', '.parquet', '.pdf', '.wav', '.mp3', '.html'}

    storage_dir = get_storage_path("audit_input", audit_id=audit_id)
    ensure_directory_exists(storage_dir)

    uploaded_files = []
    failed_files = []
    metadata_csv_location = None

    for file in files:
        file_extension = Path(file.filename).suffix.lower()
        if file_extension not in allowed_extensions:
            failed_files.append({"filename": file.filename, "error": f"File type {file_extension} not allowed"})
            continue

        is_duplicate, existing_filename = check_duplicate_file(storage_dir, file.filename, tenant_id=tenant_id)
        if is_duplicate:
            failed_files.append({"filename": file.filename, "error": f"Already exists as '{existing_filename}'"})
            continue

        if file.filename.lower() == "metadata.csv":
            # Save metadata.csv without a unique suffix so it's always findable
            file_location, file_size = _save_upload(file, storage_dir, "metadata.csv", tenant_id=tenant_id)
            metadata_csv_location = file_location
        else:
            file_stem = Path(file.filename).stem
            file_suffix = Path(file.filename).suffix
            unique_id = str(uuid.uuid4())[:8]
            safe_filename = f"{file_stem}_{unique_id}{file_suffix}"
            file_location, file_size = _save_upload(file, storage_dir, safe_filename, tenant_id=tenant_id)

        uploaded_files.append({
            "filename": file.filename,
            "file_size": file_size,
            "file_path": file_location,
        })

    # --- Process metadata.csv: update InputDatasetMetadata ---
    features_created = []
    dataset_id = None

    if metadata_csv_location:
        try:
            # Read headers from metadata.csv
            sm = get_storage_manager(tenant_id)
            if isinstance(sm, S3StorageManager):
                import tempfile as _tf, os as _os, io as _io
                raw = sm.read_file(metadata_csv_location)
                import pandas as _pd
                headers = list(_pd.read_csv(_io.BytesIO(raw), nrows=0).columns)
            else:
                headers = extract_csv_headers(Path(metadata_csv_location))

            if headers:
                # Find or create DatasetMetadata linked to this audit
                audit_pipeline = session.exec(
                    select(MappingModelDatasetAudit)
                    .join(MappingAuditPipelineAudit, MappingModelDatasetAudit.auditpipeline == MappingAuditPipelineAudit.audit_pipeline)
                    .where(MappingAuditPipelineAudit.audit_id == audit_id)
                ).first()

                if audit_pipeline and audit_pipeline.dataset_id:
                    dataset_id = audit_pipeline.dataset_id
                else:
                    new_dataset = DatasetMetadata(purpose="audit_input", copyright_agreement=True)
                    session.add(new_dataset)
                    session.flush()
                    dataset_id = new_dataset.id
                    if audit_pipeline:
                        audit_pipeline.dataset_id = dataset_id
                        session.add(audit_pipeline)

                # Normalise storage_dir to S3 key prefix or local path
                input_location = storage_dir
                if isinstance(sm, S3StorageManager):
                    input_location = storage_dir.lstrip("/")
                    if input_location.startswith("storage/"):
                        input_location = input_location[len("storage/"):]
                    input_location = input_location.rstrip("/")

                # Create or update InputDatasetMetadata
                existing_input = session.exec(
                    select(InputDatasetMetadata).where(
                        InputDatasetMetadata.dataset_metadata_id == dataset_id
                    )
                ).first()

                headers_dict = {h: h for h in headers}
                if existing_input:
                    existing_input.headers = headers_dict
                    existing_input.location = input_location
                    session.add(existing_input)
                else:
                    session.add(InputDatasetMetadata(
                        dataset_metadata_id=dataset_id,
                        headers=headers_dict,
                        benchmark_dataset=False,
                        datatypes={},
                        location=input_location,
                    ))

                # Register underlying features
                existing_feature_names = set(session.exec(select(UnderlyingFeatures.feature_name)).all())
                features_created = create_underlying_features_for_dataset(
                    session, dataset_id, headers, existing_feature_names
                )

        except Exception as e:
            print(f"Error processing metadata.csv: {e}")

    session.commit()

    return {
        "message": f"Processed {len(files)} file(s) for audit {audit_id}",
        "uploaded_files": uploaded_files,
        "failed_files": failed_files,
        "storage_location": storage_dir,
        "metadata_processed": metadata_csv_location is not None,
        "features_created": features_created,
        "dataset_id": dataset_id,
    }
