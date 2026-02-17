"""
Upload service module - Provides business logic for file upload operations.

This module is organized into separate files for different operations:
- upload.py: File upload functions
- list.py: File listing and retrieval functions
- delete.py: File deletion functions
- view.py: File viewing/download functions
- utils.py: Helper functions and utilities
"""

# Import all CRUD functions
from .upload import (
    upload_dataset_comprehensive,
    upload_multiple_datasets_comprehensive,
    upload_audit_input_comprehensive
)

from .list import (
    list_uploaded_datasets_comprehensive,
    list_audit_files_comprehensive
)

from .delete import (
    delete_dataset_file_comprehensive
)

from .view import (
    view_dataset_file_comprehensive,
    view_audit_file_comprehensive
)

# Import all utility functions
from .utils import (
    ensure_directory_exists,
    extract_csv_headers,
    create_underlying_features_for_dataset,
    get_storage_path,
    check_duplicate_file
)

# Export all functions
__all__ = [
    # Upload operations
    'upload_dataset_comprehensive',
    'upload_multiple_datasets_comprehensive',
    'upload_audit_input_comprehensive',

    # List operations
    'list_uploaded_datasets_comprehensive',
    'list_audit_files_comprehensive',

    # Delete operations
    'delete_dataset_file_comprehensive',

    # View operations
    'view_dataset_file_comprehensive',
    'view_audit_file_comprehensive',

    # Utility functions
    'ensure_directory_exists',
    'extract_csv_headers',
    'create_underlying_features_for_dataset',
    'get_storage_path',
    'check_duplicate_file',
]
