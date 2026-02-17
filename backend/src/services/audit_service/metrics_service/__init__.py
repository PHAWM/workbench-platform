"""
Metrics service module - Provides business logic for metric operations.

This module is organized into separate files for different operations:
- create.py: Metric creation functions
- read.py: Metric retrieval and query functions
- update.py: Metric modification functions
- delete.py: Metric deletion functions
- utils.py: Helper functions and utilities
"""

# Import all CRUD functions
from .create import (
    create_metric,
    create_qualitative_metric_comprehensive,
    create_quantitative_metric_comprehensive,
    assign_metric_to_event_comprehensive
)

from .read import (
    get_metric_by_id,
    list_metrics,
    get_metrics_by_audit,
    get_metric_detailed_with_context,
    list_metrics_by_audit_detailed,
    get_dataset_features_for_audit_with_context,
    get_metric_value_underlying_features_with_context,
    get_metric_value_target_features_with_context,
    get_metric_value_scale_points_with_context,
    get_metric_value_all_features_with_context,
    get_effective_threshold_with_context
)

from .update import (
    update_metric,
    update_qualitative_metric_comprehensive,
    update_quantitative_metric_comprehensive,
    update_threshold_comprehensive,
    update_metric_value_features_comprehensive
)

from .delete import (
    delete_metric,
    delete_qualitative_metric,
    delete_quantitative_metric,
    reset_threshold_to_default_comprehensive
)

# Import all utility functions
from .utils import (
    get_user_audit_ids,
    create_metric_value_details,
    get_metric_value_details,
    get_effective_threshold,
    get_dataset_for_audit,
    validate_feature_ids,
    validate_target_feature_ids
)

# Export all functions
__all__ = [
    # Create operations
    'create_metric',
    'create_qualitative_metric_comprehensive',
    'create_quantitative_metric_comprehensive',
    'assign_metric_to_event_comprehensive',

    # Read operations
    'get_metric_by_id',
    'list_metrics',
    'get_metrics_by_audit',
    'get_metric_detailed_with_context',
    'list_metrics_by_audit_detailed',
    'get_dataset_features_for_audit_with_context',
    'get_metric_value_underlying_features_with_context',
    'get_metric_value_target_features_with_context',
    'get_metric_value_scale_points_with_context',
    'get_metric_value_all_features_with_context',
    'get_effective_threshold_with_context',

    # Update operations
    'update_metric',
    'update_qualitative_metric_comprehensive',
    'update_quantitative_metric_comprehensive',
    'update_threshold_comprehensive',
    'update_metric_value_features_comprehensive',

    # Delete operations
    'delete_metric',
    'delete_qualitative_metric',
    'delete_quantitative_metric',
    'reset_threshold_to_default_comprehensive',

    # Utility functions
    'get_user_audit_ids',
    'create_metric_value_details',
    'get_metric_value_details',
    'get_effective_threshold',
    'get_dataset_for_audit',
    'validate_feature_ids',
    'validate_target_feature_ids',
]
