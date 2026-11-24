"""Utility functions for evaluation service"""
import math
import numpy as np
import pandas as pd
from sqlmodel import Session, select


def should_skip_performance_pipeline(audit_id: int, session: Session) -> tuple[bool, str | None]:
    """Decide whether to skip the performance-evaluation pipeline for an audit.

    Skip rule: Black-box applications (Application.access_type == 0) with no
    input AND no output dataset metadata on any of the audit's datasets have
    nothing for the pipeline to evaluate, so we short-circuit instead of
    raising. Grey/white-box audits, and black-box audits where either input
    or output data is present, run as normal.

    Returns (skip, reason). When skip is True, callers should return an empty
    "skipped" response without touching the rest of the pipeline.
    """
    # Local imports to avoid circulars at module load time.
    from src.models import (
        Application,
        DatasetMetadata,
        MappingAuditApplication,
        MappingAuditPipelineAudit,
        MappingModelDatasetAudit,
    )

    application = session.exec(
        select(Application)
        .join(MappingAuditApplication, MappingAuditApplication.application_id == Application.id)
        .where(MappingAuditApplication.audit_id == audit_id)
    ).first()

    if not application or application.access_type != 0:
        return False, None

    # Black-box — collect dataset ids attached to the audit via its
    # AuditPipeline. MappingModelDatasetAudit links datasets through the
    # pipeline, not directly to the audit.
    dataset_ids: set[int] = set()
    rows = session.exec(
        select(MappingModelDatasetAudit.dataset_id)
        .join(
            MappingAuditPipelineAudit,
            MappingAuditPipelineAudit.audit_pipeline == MappingModelDatasetAudit.auditpipeline,
        )
        .where(MappingAuditPipelineAudit.audit_id == audit_id)
    ).all()
    for ds_id in rows:
        if ds_id is not None:
            dataset_ids.add(ds_id)

    if not dataset_ids:
        return True, "Opaque-box application with no datasets attached — performance analysis skipped."

    # Placeholder datasets (created on demand for opaque-box audits) carry
    # I/O rows seeded from the model's task/output_context with no `location`
    # — they're catalogue stubs, not real data. Treat I/O as absent unless at
    # least one row has a location pointing at actual files.
    for ds in session.exec(
        select(DatasetMetadata).where(DatasetMetadata.id.in_(dataset_ids))
    ).all():
        for io_row in (ds.input_dataset_metadata or []) + (ds.output_dataset_metadata or []):
            if getattr(io_row, "location", None):
                return False, None

    return True, "Opaque-box application with no input or output data — performance analysis skipped."


def convert_numpy_to_json_serializable(obj):
    """
    Convert numpy arrays and other non-serializable objects to JSON-serializable format.

    This function recursively converts numpy/pandas objects to native Python types
    that can be serialized to JSON, handling special cases like NaN, infinity, and
    various numpy data types.

    Args:
        obj: Any object that needs to be converted to JSON-serializable format

    Returns:
        JSON-serializable version of the input object
    """
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, dict):
        # Convert dict with proper key handling
        result = {}
        for key, value in obj.items():
            # Convert numpy keys to native Python types
            if isinstance(key, (np.int64, np.int32, np.int16, np.int8)):
                key = int(key)
            elif isinstance(key, (np.float64, np.float32, np.float16)):
                key = float(key)
            elif isinstance(key, np.str_):
                key = str(key)
            elif key is None:
                key = "null"  # JSON doesn't support None as dict key
            result[key] = convert_numpy_to_json_serializable(value)
        return result
    elif isinstance(obj, list):
        return [convert_numpy_to_json_serializable(item) for item in obj]
    elif isinstance(obj, tuple):
        return [convert_numpy_to_json_serializable(item) for item in obj]
    elif isinstance(obj, (np.int64, np.int32, np.int16, np.int8)):
        return int(obj)
    elif isinstance(obj, (np.float64, np.float32, np.float16)):
        # Check if it's NaN or infinite before converting
        if pd.isna(obj):
            return None
        if math.isinf(float(obj)):
            return None  # or return string "Infinity"/"-Infinity"
        return float(obj)
    elif isinstance(obj, np.bool_):
        return bool(obj)
    elif isinstance(obj, np.str_):
        return str(obj)
    elif isinstance(obj, pd.Timestamp):
        return obj.isoformat()
    elif pd.isna(obj):
        # Handle any other NaN values (np.nan, pd.NA, None, float('nan'))
        return None
    elif isinstance(obj, (pd.Series, pd.DataFrame)):
        # Convert pandas objects to native types
        return convert_numpy_to_json_serializable(obj.to_dict())
    else:
        return obj
