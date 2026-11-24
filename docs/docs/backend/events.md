# Events API

## Overview

The Events API provides endpoints for managing events within audit contexts. Events represent potential risks, opportunities, or incidents that can be evaluated and tracked. All endpoints require authentication and follow a user-audit-based access control system.

**Base Path:** `/events`

**Authentication:** All endpoints require a valid JWT token via `Depends(get_current_user)`

## Access Control

Events are scoped to specific audits and users through the `MappingAuditUser` relationship. Users can access events based on their audit permissions and roles.

---

## Endpoints

### 1. Create Event (Basic)

**Endpoint:** `POST /events/`

**Description:** Creates a basic event with enhanced type tracking.

**Query Parameters:**

- `description` (str, required): Event description
- `reason` (str, required): Reason for the event
- `cause` (str, required): Cause of the event
- `likelihood` (float, required): Likelihood between 0.0 and 1.0
- `magnitude` (float, required): Magnitude of impact
- `valence` (float, required): Valence between -1.0 and 1.0
- `is_user_defined` (bool, default: true): Whether event is user-defined
- `is_template` (bool, default: false): Whether event can be used as template
- `category` (str, optional): Event category

**Response:**
```json
{
  "id": 123,
  "name": "Event Name",
  "description": "Event description",
  "cause": "Root cause",
  "reason": "Business reason",
  "likelihood": 0.7,
  "magnitude": 0.8,
  "valence": -0.5
}
```

**Status Codes:**

- `200`: Successfully created
- `400`: Invalid request data

---

### 2. Create Event (Comprehensive)

**Endpoint:** `POST /events/comprehensive`

**Description:** Creates an event with all related entities (metrics, entities, categories, users) in a single call with enhanced metric association support.

**Request Body:**
```json
{
  "audit_id": 123,
  "name": "Model Performance Degradation",
  "description": "ML model accuracy has dropped below acceptable thresholds",
  "cause": "Data drift in production environment",
  "reason": "Need to maintain model reliability for business decisions",
  "likelihood": 0.75,
  "magnitude": 0.9,
  "valence": -0.8,
  "is_user_defined": true,
  "is_template": false,
  "metrics": [
    {
      "metric_id": 456,
      "values_id": 789
    }
  ],
  "entities": [
    {
      "entity_id": 101
    }
  ],
  "categories": [
    {
      "category_id": 202
    }
  ],
  "users": [
    {
      "user_audit_id": 303
    }
  ]
}
```

**Response:**
```json
{
  "id": 123,
  "description": "ML model accuracy has dropped below acceptable thresholds",
  "cause": "Data drift in production environment",
  "reason": "Need to maintain model reliability for business decisions",
  "likelihood": 0.75,
  "magnitude": 0.9,
  "valence": -0.8,
  "is_user_defined": true,
  "is_template": false,
  "event_category": "Performance",
  "risk_level": "high",
  "impact_type": "negative",
  "metrics": [
    {
      "metric_id": 456,
      "values_id": 789
    }
  ],
  "associated_entities": [...],
  "event_categories": [...],
  "assigned_users": [...],
  "audit_details": [...],
  "total_entities": 1,
  "total_categories": 1,
  "total_users": 1,
  "total_audits": 1
}
```

**Enhanced Features:**

- **Metric Association**: Direct metric-value linking during event creation
- **Automatic EventType Creation**: Creates event type entries with category mapping
- **Complete Relationship Setup**: All audit, user, and entity associations in one transaction

---

### 3. Get Event Details

**Endpoint:** `GET /events/by-event/{event_id}`

**Description:** Retrieves comprehensive details for a specific event including all associated entities.

**Path Parameters:**

- `event_id` (int): ID of the event to retrieve

**Response:**
```json
{
  "id": 123,
  "description": "ML model accuracy has dropped below acceptable thresholds",
  "cause": "Data drift in production environment",
  "reason": "Need to maintain model reliability for business decisions",
  "likelihood": 0.75,
  "magnitude": 0.9,
  "valence": -0.8,
  "is_user_defined": true,
  "is_template": false,
  "event_category": "Performance",
  "risk_level": "high",
  "impact_type": "negative",
  "associated_entities": [
    {
      "entity_id": 101,
      "entity_name": "Production Users",
      "num_individuals": 10000
    }
  ],
  "event_categories": [
    {
      "category_id": 202,
      "event_name": "Technical Risk",
      "description": "Risks related to technical systems"
    }
  ],
  "assigned_users": [
    {
      "user_id": "uuid-string",
      "full_name": "John Doe",
      "email": "john@example.com",
      "username": "johndoe"
    }
  ],
  "audit_details": [
    {
      "audit_id": 123,
      "audit_name": "Q4 Model Audit",
      "audit_status": 1,
      "audit_status_text": "In Progress",
      "recommendation": "Immediate review required",
      "application_id": 456,
      "application_name": "ML Prediction Service"
    }
  ],
  "total_entities": 1,
  "total_categories": 1,
  "total_users": 1,
  "total_audits": 1
}
```

**Status Codes:**

- `200`: Successfully retrieved
- `404`: Event not found

---

### 4. Update Event Values (Smart)

**Endpoint:** `PUT /events/{event_id}/values`

**Description:** Intelligently updates event values using either direct modification (for event creators) or customization system (for other users).

**Path Parameters:**

- `event_id` (int): ID of the event to update

**Query Parameters:**

- `audit_id` (int, required): Audit context for the update
- `likelihood` (float, optional): New likelihood value (0.0-1.0)
- `magnitude` (float, optional): New magnitude value
- `valence` (float, optional): New valence value (-1.0-1.0)

**Response (Direct Update):**
```json
{
  "message": "Event values updated directly",
  "event_id": 123,
  "updated_directly": true,
  "likelihood": 0.8,
  "magnitude": 0.75,
  "valence": -0.6
}
```

**Response (Customization):**
```json
{
  "message": "Event values updated via customisation",
  "event_id": 123,
  "updated_directly": false,
  "is_customised": true,
  "likelihood": 0.8,
  "magnitude": 0.75,
  "valence": -0.6
}
```

**Logic:**

- **Direct Update**: If user is the event creator in the same audit context, updates the base `Events` directly
- **Customization**: If different user or audit, creates/updates entry in `UserEventCustomisations` table
- **Effective Values**: System automatically returns appropriate values (custom or default) in event details

**Status Codes:**

- `200`: Successfully updated
- `403`: User has no access to this audit
- `400`: Database error

---

### 5. Update Event (Comprehensive)

**Endpoint:** `PUT /events/{event_id}/comprehensive`

**Description:** Comprehensively updates an event and all its related entities in one call.

**Path Parameters:**

- `event_id` (int): ID of the event to update

**Request Body:**
```json
{
  "audit_id": 123,
  "name": "Updated Event Name",
  "description": "Updated description",
  "cause": "Updated cause",
  "reason": "Updated reason",
  "likelihood": 0.8,
  "magnitude": 0.7,
  "valence": -0.6,
  "is_template": false,
  "entities": [
    {
      "entity_id": 101
    },
    {
      "entity_id": 102
    }
  ],
  "categories": [
    {
      "category_id": 202
    }
  ],
  "users": [
    {
      "user_audit_id": 303
    }
  ]
}
```

**Response:** Same structure as the enhanced event detail response

**Notes:**

- Associations are replaced entirely with the provided lists
- Omitted associations are removed
- New associations are added

---

### 6. Customize Event Values

**Endpoint:** `PUT /events/{event_id}/customise`

**Description:** Updates event values with user-specific customizations for general use.

**Path Parameters:**

- `event_id` (int): ID of the event to customize

**Request Body:**
```json
{
  "likelihood": 0.85,
  "magnitude": 0.7,
  "valence": -0.5
}
```

**Response:**
```json
{
  "event_id": 123,
  "likelihood": 0.85,
  "magnitude": 0.7,
  "valence": -0.5,
  "is_customized": true
}
```

---

### 7. Customize Event Values for Specific Audit

**Endpoint:** `PUT /events/{event_id}/customise/{audit_id}`

**Description:** Updates event values with user-specific customizations for a specific audit context.

**Path Parameters:**

- `event_id` (int): ID of the event to customize
- `audit_id` (int): ID of the audit context

**Request Body:**
```json
{
  "likelihood": 0.9,
  "magnitude": 0.8,
  "valence": -0.7
}
```

**Response:**
```json
{
  "event_id": 123,
  "audit_id": 456,
  "likelihood": 0.9,
  "magnitude": 0.8,
  "valence": -0.7,
  "is_customized": true
}
```

**Features:**

- **Audit-Specific Customization**: Each audit context can have different customized values
- **Non-Destructive**: Original event values preserved
- **Access Control**: Verifies user has access to the specific audit

---

### 8. List Events (Detailed with Effective Values)

**Endpoint:** `GET /events/all`

**Description:** Lists events with comprehensive filtering, sorting, and pagination options, including enhanced metric information and **effective event values**.

**Query Parameters:**

- `page` (int, default: 1): Page number for pagination
- `page_size` (int, default: 100): Number of items per page
- `audit_id` (int, optional): Filter by specific audit ID (enables effective values)
- `user_id` (str, optional): Filter by specific user ID
- `sort_by` (enum): Sort field - `likelihood`, `magnitude`, `valence`, `risk_level`, `created_date`
- `sort_order` (enum): Sort order - `asc`, `desc`
- `user_defined_only` (bool, optional): Filter to only user-defined events
- `templates_only` (bool, optional): Filter to only template events
- `category` (str, optional): Filter by category name

**Response:**
```json
{
  "events": [
    {
      "id": 123,
      "description": "Event description",
      "cause": "Event cause",
      "reason": "Event reason",
      "likelihood": 0.8,
      "magnitude": 0.85,
      "valence": -0.7,
      "is_user_defined": true,
      "is_audit_instigator": false,
      "associated_metrics": [
        {
          "metric_id": 456,
          "metric_description": "Model Accuracy",
          "metric_name": "Accuracy Score",
          "metric_type": "quantitative",
          "threshold": ">=0.95",
          "formula": "TP/(TP+FP)",
          "metric_value_output": "High",
          "underlying_features": [
            {
              "feature_id": 1,
              "ranges": ["0.95-1.0"]
            }
          ],
          "target_features": [
            {
              "feature_id": 2,
              "ranges": ["target_range"]
            }
          ],
          "scale_points": {
            "excellent": 0.95,
            "good": 0.85
          },
          "is_user_defined": true,
          "is_audit_instigator": false
        }
      ],
      "associated_entities": [...],
      "associated_pipelines": [
        {
          "metric_id": 456
        }
      ],
      "event_categories": [...],
      "assigned_users": [...],
      "audit_details": [...],
      "total_metrics": 1,
      "total_entities": 2,
      "total_categories": 1,
      "total_users": 3,
      "total_audits": 1
    }
  ],
  "total_count": 25,
  "page": 1,
  "page_size": 100,
  "total_pages": 1,
  "filters_applied": {
    "audit_id": 123,
    "user_defined_only": true
  }
}
```

**Enhanced Features:**

- **Effective Event Values**: When `audit_id` is provided, returns customized likelihood/magnitude/valence values
- **Rich Metric Information**: Includes underlying features, target features, and scale points
- **Effective Threshold Resolution**: Returns appropriate thresholds based on user-audit context
- **Pipeline Association**: Shows audit pipeline connections via metric relationships
- **Advanced Role Detection**: Distinguishes between user-defined and audit instigator metrics
- **Comprehensive Filtering**: Multiple filter combinations for precise event discovery

---

### 6. List Events (Simple)

**Endpoint:** `GET /events/`

**Description:** Simple event listing with basic pagination.

**Query Parameters:**

- `skip` (int, default: 0): Number of records to skip
- `limit` (int, default: 100): Maximum number of records to return

**Response:** Array of basic event objects

---

### 7. Update Event (Basic)

**Endpoint:** `PUT /events/{event_id}`

**Description:** Updates basic event properties only.

**Request Body:**
```json
{
  "description": "Updated description",
  "likelihood": 0.8,
  "magnitude": 0.7,
  "valence": -0.6,
  "cause": "Updated cause",
  "reason": "Updated reason"
}
```

**Response:** Updated event object

---

### 8. Delete Event

**Endpoint:** `DELETE /events/{event_id}`

**Description:** Deletes an event and sets event_id to null in dependent mappings.

**Path Parameters:**

- `event_id` (int): ID of the event to delete

**Response:**
```json
{
  "message": "Event deleted successfully"
}
```

---

### 9. Get Events by Audit

**Endpoint:** `GET /events/by-audit/{audit_id}`

**Description:** Retrieves all events associated with a specific audit.

**Path Parameters:**

- `audit_id` (int): ID of the audit

**Query Parameters:**

- `page` (int, default: 1): Page number
- `page_size` (int, default: 20, max: 100): Items per page

**Response:** Events list response with pagination

---

### 10. Get Events by Category

**Endpoint:** `GET /events/by-category/{category_id}`

**Description:** Retrieves all events associated with a specific category.

**Path Parameters:**

- `category_id` (int): ID of the category

**Query Parameters:**

- `page` (int, default: 0): Page offset
- `page_size` (int, default: 100): Items per page

**Response:** Events list response with pagination

---

## Audit Pipeline Events Mapping Endpoints

### 11. Create Audit Pipeline Events Mapping

**Endpoint:** `POST /events/audit-pipeline-mapping`

**Description:** Creates a mapping between events, metrics, and audit pipelines.

**Request Body:**
```json
{
  "audit_id": 123,
  "event_id": 456,
  "metric_id": 789
}
```

**Response:**
```json
{
  "id": 101,
  "audit_pipeline": 111,
  "event_id": 456,
  "metric_id": 789,
  "user_audit_id": 222,
  "message": "Audit pipeline events mapping created successfully"
}
```

---

### 12. Create Audit Pipeline Events Mappings (Batch)

**Endpoint:** `POST /events/audit-pipeline-mapping/batch`

**Description:** Creates multiple mappings in batch and removes mappings not in the batch.

**Request Body:**
```json
{
  "audit_id": 123,
  "mappings": [
    {
      "event_id": 456,
      "metric_id": 789
    },
    {
      "event_id": 457,
      "metric_id": 790
    }
  ]
}
```

**Response:**
```json
{
  "created_mappings": [...],
  "updated_mappings": [...],
  "deleted_mappings": [...],
  "errors": [],
  "total_processed": 2,
  "total_existing": 5,
  "successful_creates": 1,
  "successful_updates": 1,
  "successful_deletes": 3,
  "failed": 0,
  "message": "Batch operation completed: 1 created, 1 already existed, 3 deleted, 0 failed"
}
```

---

### 13. Get Audit Pipeline Events Mappings

**Endpoint:** `GET /events/audit-pipeline-mapping/{audit_pipeline_id}`

**Description:** Retrieves all events and metrics mapped to a specific audit pipeline.

**Path Parameters:**

- `audit_pipeline_id` (int): ID of the audit pipeline

**Response:**
```json
[
  {
    "mapping_id": 101,
    "audit_pipeline": 111,
    "event": {
      "id": 456,
      "description": "Event description",
      "cause": "Event cause",
      "reason": "Event reason",
      "likelihood": 0.7,
      "magnitude": 0.8,
      "valence": -0.5
    },
    "metric": {
      "id": 789,
      "description": "Metric description",
      "reason": "Metric reason"
    },
    "user_audit_id": 222
  }
]
```

---

### 14. Delete Audit Pipeline Events Mapping

**Endpoint:** `DELETE /events/audit-pipeline-mapping/{mapping_id}`

**Description:** Deletes a specific audit pipeline events mapping.

**Path Parameters:**

- `mapping_id` (int): ID of the mapping to delete

**Response:**
```json
{
  "message": "Audit pipeline events mapping deleted successfully"
}
```

---

## Utility Endpoints

### 15. Get Categories

**Endpoint:** `GET /events/categories`

**Description:** Retrieves all available event categories.

**Response:**
```json
[
  {
    "id": 1,
    "event_name": "Technical Risk",
    "description": "Risks related to technical systems"
  },
  {
    "id": 2,
    "event_name": "Business Risk", 
    "description": "Risks related to business operations"
  }
]
```

---

### 16. Get Features

**Endpoint:** `GET /events/features/underlying/{audit_id}`

**Description:** Retrieves the underlying features available for an audit. Features
are derived from the audit's `DatasetMetadata` (the input files under
`storage/audits/audit_{audit_id}/input/`), so they are scoped to a single audit
rather than global.

**Path Parameters:**

- `audit_id` (int): ID of the audit whose underlying features to list

**Response:**
```json
[
  {
    "id": 1,
    "feature_name": "Model Accuracy"
  },
  {
    "id": 2,
    "feature_name": "Response Time"
  }
]
```

---

## Batch Operations

### 17. Batch Delete Events

**Endpoint:** `POST /events/batch/delete`

**Description:** Deletes multiple events at once.

**Request Body:**
```json
[123, 456, 789]
```

**Response:**
```json
{
  "message": "Batch deletion completed",
  "deleted_events": 2,
  "errors": [
    {
      "event_id": 789,
      "error": "Event not found"
    }
  ],
  "total_processed": 3,
  "successful": 2,
  "failed": 1
}
```

---

## Analytics and Statistics

### 18. Get Events Statistics (Enhanced)

**Endpoint:** `GET /events/statistics/summary`

**Description:** Retrieves comprehensive statistics about events using **effective event values** for accurate risk assessment.

**Query Parameters:**

- `audit_id` (int, optional): Specific audit context for customized statistics

**Response:**
```json
{
  "total_events": 150,
  "risk_distribution": {
    "low": 45,
    "medium": 75,
    "high": 30
  },
  "impact_distribution": {
    "positive": 20,
    "negative": 100,
    "neutral": 30
  },
  "average_likelihood": 0.68,
  "average_magnitude": 0.72,
  "average_valence": -0.25,
  "audit_id": 123
}
```

**Enhanced Features:**

- **Effective Values Statistics**: When `audit_id` provided, uses customized event values for calculations
- **Accurate Risk Assessment**: Risk levels calculated using personalized likelihood/magnitude values
- **Context-Aware Averages**: Statistical averages reflect user-audit-specific customizations

## Key System Features

### Effective Event Values System

The events system implements an intelligent value management system that provides personalized event assessments while preserving original event definitions:

**How It Works:**
1. **Event Creators**: Users who create events in an audit context can directly modify the base values
2. **Other Users**: Users accessing events created by others get customizable values via the `UserEventCustomisations` table
3. **Automatic Resolution**: The system automatically serves the appropriate values (customized or default) based on user-audit-event context

**Benefits:**

- **Non-Destructive**: Original event definitions remain intact
- **Personalization**: Each user-audit context can have customized likelihood/magnitude/valence
- **Transparency**: Clear indication when values have been customized
- **Audit Trail**: All customizations are tracked with timestamps and user information

### Smart Value Update Logic

**Direct Updates:**
```
IF (user is event creator) AND (same audit context)
THEN update base Events table directly
ELSE create/update UserEventCustomisations entry
```

**Effective Value Resolution:**
```
IF user has customization for this event-audit context
THEN return customized values
ELSE return base event values
```

### Advanced Risk Assessment

**Dynamic Risk Calculation:**

- Risk levels are calculated using effective values (customized or default)
- Each user-audit context can have different risk assessments for the same event
- Statistics and analytics reflect personalized risk perspectives

### Context-Aware Operations

**Audit-Specific Context:**

- Event values are resolved per user-audit combination
- Same event can have different effective values in different audit contexts
- All operations respect the audit-specific customization scope

### Enhanced Access Control

**Multi-Level Permission System:**

- **Audit-User Mapping**: Base access through `MappingAuditUser`
- **Event Creator Privileges**: Direct modification rights for original creators
- **Customization Rights**: All authorized users can create personal customizations
- **Context Isolation**: Customizations are isolated per user-audit combination

---

## Migration and Maintenance

### 19. Create Default Event Types

**Endpoint:** `POST /events/migration/create-default-types`

**Description:** Creates EventType entries for existing events that don't have them (migration helper).

**Response:**
```json
{
  "message": "Created EventType entries for 25 events",
  "created_count": 25
}
```

---

## Data Models

### Core Event Model
```json
{
  "id": "integer",
  "name": "string",
  "description": "string (required)",
  "cause": "string (required)",
  "reason": "string (required)",
  "likelihood": "float (0.0-1.0, required)",
  "magnitude": "float (required)",
  "valence": "float (-1.0-1.0, required)"
}
```

### Event Risk Assessment
- **Risk Level**: Calculated as `likelihood * magnitude`
  - High: >= 0.7
  - Medium: 0.4 - 0.69
  - Low: < 0.4

- **Impact Type**: Based on valence
  - Positive: > 0.1
  - Negative: < -0.1
  - Neutral: -0.1 to 0.1

### Event Associations

#### EventMetricSummary
```json
{
  "metric_id": "integer",
  "metric_description": "string",
  "metric_name": "string",
  "metric_type": "string",
  "threshold": "string",
  "formula": "string (optional)",
  "metric_value_output": "string (optional)",
  "underlying_features": "array (optional)",
  "target_features": "array (optional)",
  "scale_points": "object (optional)",
  "is_user_defined": "boolean",
  "is_audit_instigator": "boolean"
}
```

#### EventEntitySummary
```json
{
  "entity_id": "integer",
  "entity_name": "string",
  "num_individuals": "integer"
}
```

#### EventCategorySummary
```json
{
  "category_id": "integer",
  "event_name": "string"
}
```

## Enums

### SortBy Options
- `likelihood`
- `magnitude`
- `valence`
- `risk_level`
- `created_date`

### SortOrder Options
- `asc`
- `desc`

### RiskLevel Options
- `low`
- `medium`
- `high`

### ImpactType Options
- `positive`
- `negative`
- `neutral`

## Error Handling

All endpoints return appropriate HTTP status codes:

- `200`: Success
- `400`: Bad Request (invalid data, validation errors)
- `403`: Forbidden (insufficient permissions)
- `404`: Not Found (resource doesn't exist or no access)
- `500`: Internal Server Error

Error responses include a `detail` field with descriptive error messages.

## Authentication & Authorization

- All endpoints require valid JWT authentication
- Access is controlled through the `MappingAuditUser` system
- Users can access events based on their audit permissions
- Audit instigators (role ID 1 or 3) have additional privileges
- Event ownership is tracked through the `EventType` table

## Notes

- Events support complex associations with metrics, entities, categories, and users
- The system distinguishes between user-defined and system/template events
- Risk calculations are automatic based on likelihood and magnitude
- Batch operations provide efficient bulk management
- All database operations use transactions with rollback on error
- The comprehensive endpoints allow full CRUD operations in single calls