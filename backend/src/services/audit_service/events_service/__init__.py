"""
Events service module - Provides business logic for event operations.

This module is organized into separate files for different operations:
- create.py: Event and related entity creation functions
- read.py: Event retrieval and query functions
- update.py: Event modification functions
- delete.py: Event deletion functions
- utils.py: Helper functions and utilities
"""

# Import all functions from submodules for backward compatibility
from .create import (
    create_event,
    create_user_feature,
    create_user_target_feature,
    create_user_entity,
    create_user_category,
    create_comprehensive_event
)

from .read import (
    get_underlying_features_for_audit,
    get_user_categories_for_audit,
    get_user_entities_for_audit,
    get_user_features_for_audit,
    # Reusable helper functions
    get_user_audit_mapping,
    get_accessible_event_ids,
    get_audit_instigator_user_audit_id,
    get_allowed_user_audit_ids,
    get_event_entities,
    get_event_categories_with_access_control,
    get_event_audits_with_details,
    check_event_is_audit_instigator,
    # Main service functions
    get_event_detailed_with_context,
    list_events_with_details
)

from .update import (
    update_event,
    update_event_values,
    update_event_comprehensive,
    customise_event_values_simple,
    customise_event_values_for_audit
)

from .delete import (
    delete_event
)

from .utils import (
    get_effective_event_values,
    apply_filters_to_query,
    determine_risk_level,
    determine_impact_type,
    get_audit_status_text,
    apply_sorting,
    get_user_audit_ids,
    get_event_metrics_with_values
)

# Export all functions
__all__ = [
    # Create operations
    'create_event',
    'create_user_feature',
    'create_user_target_feature',
    'create_user_entity',
    'create_user_category',
    'create_comprehensive_event',

    # Read operations
    'get_underlying_features_for_audit',
    'get_user_categories_for_audit',
    'get_user_entities_for_audit',
    'get_user_features_for_audit',
    # Reusable helper functions
    'get_user_audit_mapping',
    'get_accessible_event_ids',
    'get_audit_instigator_user_audit_id',
    'get_allowed_user_audit_ids',
    'get_event_entities',
    'get_event_categories_with_access_control',
    'get_event_audits_with_details',
    'check_event_is_audit_instigator',
    # Main service functions
    'get_event_detailed_with_context',
    'list_events_with_details',

    # Update operations
    'update_event',
    'update_event_values',
    'update_event_comprehensive',
    'customise_event_values_simple',
    'customise_event_values_for_audit',

    # Delete operations
    'delete_event',

    # Utility functions
    'get_effective_event_values',
    'apply_filters_to_query',
    'determine_risk_level',
    'determine_impact_type',
    'get_audit_status_text',
    'apply_sorting',
    'get_user_audit_ids',
    'get_event_metrics_with_values',
]
