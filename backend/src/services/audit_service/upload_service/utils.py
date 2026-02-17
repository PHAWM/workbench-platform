"""Upload utility and helper functions"""
from pathlib import Path
from typing import List, Optional, Tuple
from sqlmodel import Session, select
import pandas as pd

from src.models import *


def ensure_directory_exists(directory_path: str) -> None:
    """Create directory if it doesn't exist"""
    Path(directory_path).mkdir(parents=True, exist_ok=True)


def extract_csv_headers(file_path: Path) -> list[str]:
    """Extract column headers from a CSV file"""
    try:
        df = pd.read_csv(file_path, nrows=0)
        return df.columns.tolist()
    except Exception as e:
        print(f"Error reading CSV headers: {e}")
        return []


def create_underlying_features_for_dataset(
    session: Session,
    dataset_id: int,
    headers: list[str],
    existing_feature_names: set = None
) -> list[int]:
    """
    Create UnderlyingFeatures records for dataset headers and link them
    Returns list of created feature IDs

    Args:
        existing_feature_names: Set of already existing feature names to avoid duplicates
    """
    feature_ids = []

    for header in headers:
        # Check if feature already exists
        existing_feature = session.exec(
            select(UnderlyingFeatures)
            .where(UnderlyingFeatures.feature_name == header)
        ).first()

        if existing_feature:
            feature_id = existing_feature.id
        else:
            # Only create if not in existing_feature_names set (global check)
            if existing_feature_names and header in existing_feature_names:
                print(f"Skipping duplicate feature: {header}")
                continue

            # Create new underlying feature
            new_feature = UnderlyingFeatures(feature_name=header)
            session.add(new_feature)
            session.flush()
            feature_id = new_feature.id

        # Check if mapping already exists
        existing_mapping = session.exec(
            select(MappingDatasetFeatures)
            .where(
                MappingDatasetFeatures.dataset_metadata_id == dataset_id,
                MappingDatasetFeatures.feature_id == feature_id
            )
        ).first()

        if not existing_mapping:
            # Create mapping between dataset and feature
            mapping = MappingDatasetFeatures(
                dataset_metadata_id=dataset_id,
                feature_id=feature_id
            )
            session.add(mapping)

        feature_ids.append(feature_id)

    return feature_ids


def get_storage_path(storage_type: str, user_id: int = None, audit_id: int = None) -> str:
    """
    Get the appropriate storage path based on storage type

    Args:
        storage_type: 'output_evaluation' or 'audit_input'
        user_id: Required for output_evaluation
        audit_id: Required for both output_evaluation and audit_input

    Storage structure:
        - Audit input data: storage/audits/audit_{audit_id}/input/
        - Audit results: storage/audits/audit_{audit_id}/results.csv
        - User evaluation uploads: storage/audits/audit_{audit_id}/users/{user_id}/output_evaluation/input/
    """
    if storage_type == "output_evaluation":
        if user_id is None or audit_id is None:
            raise ValueError("Both user_id and audit_id are required for output_evaluation storage")
        return f"storage/users/{user_id}/output_evaluation/audit_{audit_id}/input"

    elif storage_type == "audit_input":
        if audit_id is None:
            raise ValueError("audit_id is required for audit_input storage")
        return f"storage/audits/audit_{audit_id}/input"

    else:
        raise ValueError(f"Invalid storage_type: {storage_type}")


def check_duplicate_file(storage_dir: str, original_filename: str) -> Tuple[bool, str | None]:
    """
    Check if a file with the same base name already exists in the storage directory.
    Excludes the last 9 characters (underscore + 8 character hash) from comparison.

    Args:
        storage_dir: Directory to check for duplicates
        original_filename: The original filename to check

    Returns:
        Tuple of (is_duplicate: bool, existing_filename: str | None)
    """
    storage_path = Path(storage_dir)
    if not storage_path.exists():
        return False, None

    original_stem = Path(original_filename).stem
    original_suffix = Path(original_filename).suffix

    # Check all files in the directory
    for existing_file in storage_path.iterdir():
        if existing_file.is_file():
            existing_name = existing_file.name
            existing_stem = existing_file.stem
            existing_suffix = existing_file.suffix

            # Check if suffix matches
            if existing_suffix != original_suffix:
                continue

            # Remove the last 9 characters (_xxxxxxxx) from the existing filename
            # Format is: original_name_12345678.ext
            if len(existing_stem) > 9 and existing_stem[-9] == '_':
                base_existing_stem = existing_stem[:-9]
            else:
                base_existing_stem = existing_stem

            # Compare base names
            if base_existing_stem == original_stem:
                return True, existing_name

    return False, None


def get_acceptable_formats_for_audit(session: Session, audit_id: int) -> Optional[List[str]]:
    """
    Get the acceptable file formats for an audit based on its associated model.

    This function traverses the relationship:
    audit_id -> MappingAuditPipelineAudit -> MappingModelDatasetAudit -> Modelmetadata

    Args:
        session: Database session
        audit_id: The audit ID to get acceptable formats for

    Returns:
        List of acceptable file format extensions (e.g., ['txt', 'html', 'wav', 'mp3'])
        or None if no model is associated or no formats are specified
    """
    # Get the audit pipeline for this audit
    audit_pipeline_mapping = session.exec(
        select(MappingAuditPipelineAudit).where(
            MappingAuditPipelineAudit.audit_id == audit_id
        )
    ).first()

    if not audit_pipeline_mapping:
        return None

    # Get the model-dataset-audit mapping to find the model
    model_dataset_mapping = session.exec(
        select(MappingModelDatasetAudit).where(
            MappingModelDatasetAudit.auditpipeline == audit_pipeline_mapping.audit_pipeline
        )
    ).first()

    if not model_dataset_mapping:
        return None

    # Get the model metadata to retrieve acceptable formats
    model = session.get(Modelmetadata, model_dataset_mapping.model_id)

    if not model:
        return None

    return model.acceptable_formats
