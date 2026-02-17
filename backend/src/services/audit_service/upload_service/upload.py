"""Upload service functions for file uploads"""
from typing import Any, Dict, List
from fastapi import HTTPException, UploadFile
from sqlmodel import Session, select
from pathlib import Path
import shutil
import uuid

from src.models import *
from .utils import (
    ensure_directory_exists,
    extract_csv_headers,
    create_underlying_features_for_dataset,
    get_storage_path,
    check_duplicate_file,
    get_acceptable_formats_for_audit
)


def upload_dataset_comprehensive(
    file: UploadFile,
    audit_id: int,
    current_user_id: str,
    session: Session
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
    is_duplicate, existing_filename = check_duplicate_file(storage_dir, file.filename)
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
    file_path = Path(storage_dir) / safe_filename

    # Save the uploaded file
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # Create database records
    output_eval_data = OutputEvaluationData(location=str(file_path))
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

    # Get file info
    file_size = file_path.stat().st_size

    return {
        "message": "Dataset uploaded successfully",
        "filename": safe_filename,
        "original_filename": file.filename,
        "file_size": file_size,
        "file_path": str(file_path),
        "content_type": file.content_type,
        "storage_type": "output_evaluation",
        "data_id": output_eval_user.id,
        "outcome_records_created": len(created_outcome_ids)
    }


def upload_multiple_datasets_comprehensive(
    files: List[UploadFile],
    audit_id: int,
    current_user_id: str,
    session: Session
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
            is_duplicate, existing_filename = check_duplicate_file(storage_dir, file.filename)
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
            file_path = Path(storage_dir) / safe_filename

            # Save file
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)

            file_size = file_path.stat().st_size

            # Track metadata.csv path but don't create database record for it
            if file.filename.lower() == "metadata.csv":
                metadata_csv_path = file_path
                uploaded_files.append({
                    "filename": safe_filename,
                    "original_filename": file.filename,
                    "file_size": file_size,
                    "status": "success (metadata only)"
                })
                continue  # Skip database record creation for metadata.csv

            # Create database records only for non-metadata files
            output_eval_data = OutputEvaluationData(location=str(file_path))
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

    if metadata_csv_path and metadata_csv_path.exists():
        try:
            # Extract headers from metadata.csv
            headers = extract_csv_headers(metadata_csv_path)

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
    file: UploadFile,
    audit_id: int,
    current_user_id: str,
    session: Session
) -> Dict[str, Any]:
    """
    Upload input data for an audit (audit instigator).

    This service function handles the entire business logic for uploading audit input files,
    including:
    - File type validation
    - Storage path management
    - Duplicate file checking
    - File saving with unique identifiers

    Args:
        file: The uploaded file
        audit_id: The audit ID
        current_user_id: The ID of the user uploading the file
        session: Database session

    Returns:
        Dictionary with upload status, filename, file_size, and file_path

    Raises:
        HTTPException: If file type invalid or duplicate file exists
    """
    # Validate file type
    allowed_extensions = {'.csv', '.json', '.xlsx', '.txt', '.parquet', '.pdf', '.wav'}
    file_extension = Path(file.filename).suffix.lower()

    if file_extension not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"File type {file_extension} not allowed"
        )

    # Get storage path and ensure directory exists
    storage_dir = get_storage_path("audit_input", audit_id=audit_id)
    ensure_directory_exists(storage_dir)

    # Check for duplicate file
    is_duplicate, existing_filename = check_duplicate_file(storage_dir, file.filename)
    if is_duplicate:
        raise HTTPException(
            status_code=400,
            detail=f"A file with the same name '{file.filename}' already exists as '{existing_filename}'. Please delete the existing file or rename your file before uploading."
        )

    # Generate unique filename
    file_stem = Path(file.filename).stem
    file_suffix = Path(file.filename).suffix
    unique_id = str(uuid.uuid4())[:8]
    safe_filename = f"{file_stem}_{unique_id}{file_suffix}"
    file_path = Path(storage_dir) / safe_filename

    # Save the uploaded file
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # Get file info
    file_size = file_path.stat().st_size

    return {
        "message": "Audit input data uploaded successfully",
        "filename": safe_filename,
        "original_filename": file.filename,
        "file_size": file_size,
        "file_path": str(file_path),
        "content_type": file.content_type,
        "storage_type": "audit_input"
    }
