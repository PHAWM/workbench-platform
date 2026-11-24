# Metrics API

## Overview

The Metrics API provides endpoints for managing quantitative and qualitative metrics within audit contexts. All endpoints require authentication and follow a user-audit-based access control system.

**Base Path:** `/metrics`

**Authentication:** All endpoints require a valid JWT token via `Depends(get_current_user)`

## Key System Features

### Effective Threshold System

The metrics system implements an intelligent threshold management system that provides personalized metric thresholds while preserving original metric definitions:

**How It Works:**
1. **Metric Creators**: Users who create metrics in an audit context can directly modify the base thresholds
2. **Other Users**: Users accessing metrics created by others get customizable thresholds via the `UserMetricThresholds` table
3. **Automatic Resolution**: The system automatically serves the appropriate threshold (customized or default) based on user-audit-metric context

**Benefits:**

- **Non-Destructive**: Original metric definitions remain intact
- **Personalization**: Each user-audit context can have customized thresholds
- **Transparency**: Clear indication when thresholds have been customized
- **Audit Trail**: All customizations are tracked with timestamps

### Advanced Feature Management

The system supports sophisticated metric value configurations:

**Features Integration:**

- **Underlying Features**: Link metrics to specific data features with range specifications
- **Scale Points**: Define measurement scales with named breakpoints
- **Feature Validation**: Automatic validation of feature IDs against the `UnderlyingFeatures` table

**Complex Relationships:**

- **Event-Metric-User-Audit**: Four-way relationship ensuring proper access control and context
- **Multi-Value Support**: Single metrics can have multiple value configurations for different scenarios
- **Hierarchical Access**: Role-based access with audit instigator privileges

---

## Endpoints

### 1. Create Quantitative Metric

**Endpoint:** `POST /metrics/quantitative/create`

**Description:** Creates a complete quantitative metric with associated values, features, scale points, and event mappings.

**Request Body:**
```json
{
  "audit_id": 123,
  "name": "Model Accuracy",
  "description": "Measures the accuracy of the ML model",
  "reason": "Critical for assessing model performance",
  "formula": "TP + TN / (TP + TN + FP + FN)",
  "metric_values": [
    {
      "output": "High Accuracy",
      "threshold": ">=0.95",
      "features": [
        {
          "feature_id": 1,
          "ranges": ["0.95-1.0"]
        }
      ],
      "scale_points": {
        "excellent": 0.95,
        "good": 0.85,
        "fair": 0.75
      }
    }
  ],
  "event_mappings": [
    {
      "event_id": 456
    }
  ]
}
```

**Response:**
```json
{
  "id": 789,
  "description": "Measures the accuracy of the ML model",
  "reason": "Critical for assessing model performance",
  "metric_type": "quantitative",
  "quantitative_details": {
    "id": 101,
    "metric_id": 789,
    "formula": "TP + TN / (TP + TN + FP + FN)"
  },
  "qualitative_details": null,
  "created_values": [...],
  "created_mappings": [1, 2, 3],
  "total_values_created": 1,
  "total_mappings_created": 3
}
```

**Status Codes:**

- `200`: Successfully created
- `400`: Invalid request data or feature IDs
- `403`: User lacks access to the specified audit

---

### 2. Create Qualitative Metric

**Endpoint:** `POST /metrics/qualitative/create`

**Description:** Creates a complete qualitative metric with associated values and event mappings.

**Request Body:**
```json
{
  "audit_id": 123,
  "name": "User Satisfaction",
  "description": "Qualitative assessment of user satisfaction",
  "reason": "Important for user experience evaluation",
  "definition": "Measured through user feedback and surveys",
  "metric_values": [
    {
      "output": "Highly Satisfied",
      "threshold": ">=4.5/5",
      "features": [
        {
          "feature_id": 2,
          "ranges": ["4.5-5.0"]
        }
      ],
      "scale_points": {
        "very_satisfied": 5,
        "satisfied": 4,
        "neutral": 3
      }
    }
  ],
  "event_mappings": [
    {
      "event_id": 456
    }
  ]
}
```

**Response:** Same structure as quantitative metric response with `metric_type: "qualitative"`

---

### 3. Get Metric Details (Enhanced)

**Endpoint:** `GET /metrics/{metric_id}`

**Description:** Retrieves comprehensive details for a specific metric including associated events, values, features, scale points, and **effective thresholds** (customized or default).

**Path Parameters:**

- `metric_id` (int): ID of the metric to retrieve

**Response:**
```json
{
  "id": 789,
  "name": "Model Accuracy",
  "description": "Measures the accuracy of the ML model",
  "reason": "Critical for assessing model performance",
  "metric_type": "quantitative",
  "is_quantitative": true,
  "is_qualitative": false,
  "quantitative_details": {
    "id": 101,
    "metric_id": 789,
    "formula": "TP + TN / (TP + TN + FP + FN)"
  },
  "qualitative_details": null,
  "associated_events": [
    {
      "event_id": 456,
      "event_description": "Model performance degradation",
      "event_reason": "Accuracy drops below threshold",
      "event_name": "Performance Alert",
      "likelihood": 0.3,
      "magnitude": 0.8,
      "valence": -0.9
    }
  ],
  "metric_values": [
    {
      "id": 234,
      "event_id": 456,
      "output": "High Accuracy",
      "threshold": ">=0.97",
      "is_threshold_customized": true,
      "features": [
        {
          "feature_id": 1,
          "ranges": ["0.95-1.0"]
        }
      ],
      "scale_points": {
        "excellent": 0.95,
        "good": 0.85,
        "fair": 0.75
      }
    }
  ],
  "total_events": 1,
  "total_values": 1
}
```

**New Features:**

- **Effective Thresholds**: Returns customized thresholds when available, defaults otherwise
- **Threshold Status**: `is_threshold_customized` indicates if threshold has been personalized
- **Context-Aware**: Thresholds are user-audit-specific, ensuring personalized experience

**Status Codes:**

- `200`: Successfully retrieved
- `404`: Metric not found or access denied

---

### 4. List Metrics

**Endpoint:** `GET /metrics/`

**Description:** Lists all metrics accessible to the current user with pagination and optional filtering.

**Query Parameters:**

- `skip` (int, default: 0): Number of records to skip
- `limit` (int, default: 100): Maximum number of records to return
- `audit_id` (int, optional): Filter by specific audit ID
- `event_id` (int, optional): Filter by specific event ID

**Response:**
```json
[
  {
    "id": 789,
    "name": "Model Accuracy",
    "description": "Measures the accuracy of the ML model",
    "reason": "Critical for assessing model performance"
  },
  {
    "id": 790,
    "name": "User Satisfaction",
    "description": "Qualitative assessment of user satisfaction", 
    "reason": "Important for user experience evaluation"
  }
]
```

---

### 5. Update Metric (Basic)

**Endpoint:** `PUT /metrics/{metric_id}`

**Description:** Updates basic metric information (description only in current implementation).

**Path Parameters:**

- `metric_id` (int): ID of the metric to update

**Request Body:**
```json
{
  "description": "Updated description of the metric"
}
```

**Response:** Updated metric object

---

### 6. Update Quantitative Metric (Complete)

**Endpoint:** `PUT /metrics/quantitative/{metric_id}`

**Description:** Comprehensively updates a quantitative metric including its values, features, and scale points.

**Request Body:**
```json
{
  "description": "Updated description",
  "name": "Updated Model Accuracy",
  "reason": "Updated reason",
  "formula": "Updated formula",
  "metric_values": [
    {
      "id": 234, // Optional
      "audit_id": 234,
      "event_id": 234,
      "output": "Updated High Accuracy",
      "threshold": ">=0.97",
      "features": [
        {
          "feature_id": 1,
          "ranges": ["0.97-1.0"]
        }
      ],
      "scale_points": {
        "excellent": 0.97,
        "good": 0.87,
        "fair": 0.77
      },
      "delete": false
    },
    {
      "output": "New Medium Accuracy",
      "threshold": "0.8-0.94",
      "delete": false
    }
  ]
}
```

**Response:**
```json
{
  "id": 789,
  "description": "Updated description",
  "reason": "Updated reason", 
  "metric_type": "quantitative",
  "quantitative_details": {...},
  "qualitative_details": null,
  "updated_values": [...],
  "created_values": [...],
  "deleted_values": [],
  "total_values_updated": 1,
  "total_values_created": 1,
  "total_values_deleted": 0
}
```

---

### 7. Update Qualitative Metric (Complete)

**Endpoint:** `PUT /metrics/qualitative/{metric_id}`

**Description:** Comprehensively updates a qualitative metric including its values, features, and scale points.

**Request Body:** Similar to quantitative update but with `definition` instead of `formula`

**Response:** Similar to quantitative update response

---

### 8. Delete Metric

**Endpoint:** `DELETE /metrics/{metric_id}`

**Description:** Deletes a metric and all associated values, features, scale points, and event mappings.

**Path Parameters:**

- `metric_id` (int): ID of the metric to delete

**Response:**
```json
{
  "message": "Metric deleted successfully"
}
```

**Status Codes:**

- `200`: Successfully deleted
- `404`: Metric not found or access denied

---

### 9. Get Metrics by Audit

**Endpoint:** `GET /metrics/by-audit/{audit_id}`

**Description:** Retrieves all metrics associated with a specific audit.

**Path Parameters:**

- `audit_id` (int): ID of the audit

**Query Parameters:**

- `skip` (int, default: 0): Pagination offset
- `limit` (int, default: 100): Pagination limit

**Response:** Array of metric objects

---

### 10. Get Metrics by Event

**Endpoint:** `GET /metrics/by-event/{event_id}`

**Description:** Retrieves all metrics associated with a specific event.

**Path Parameters:**

- `event_id` (int): ID of the event

**Query Parameters:**

- `skip` (int, default: 0): Pagination offset
- `limit` (int, default: 100): Pagination limit

**Response:** Array of metric objects

---

### 11. Get Detailed Metrics by Audit

**Endpoint:** `GET /metrics/by-audit/{audit_id}/detailed`

**Description:** Retrieves detailed metrics information for an audit with creator information and metadata.

**Response:**
```json
{
  "metrics": [
    {
      "id": 789,
      "name": "Model Accuracy",
      "description": "Measures the accuracy of the ML model",
      "reason": "Critical for assessing model performance",
      "metric_type": "quantitative",
      "is_user_defined": true,
      "is_audit_instigator": false,
      "created_by_user_id": 123,
      "created_by_username": null,
      "created_at": "2024-01-01T10:00:00Z",
      "formula": "TP + TN / (TP + TN + FP + FN)",
      "definition": null,
      "total_events": 1,
      "total_values": 1
    }
  ],
  "total_count": 1,
  "page": 1,
  "page_size": 100,
  "has_next": false,
  "has_previous": false
}
```

---

### 12. Get Metric Value Features

**Endpoint:** `GET /metrics/values/{value_id}/all-features`

**Description:** Retrieves features associated with a specific metric value.

**Response:**
```json
[
  {
    "id": 1,
    "feature_id": 123,
    "ranges": ["0.95-1.0", "excellent"]
  }
]
```

---

### 13. Get Metric Value Scale Points

**Endpoint:** `GET /metrics/values/{value_id}/scale-points`

**Description:** Retrieves scale points associated with a specific metric value.

**Response:**
```json
{
  "id": 1,
  "scale_points": {
    "excellent": 0.95,
    "good": 0.85,
    "fair": 0.75,
    "poor": 0.65
  }
}
```

---

### 14. Update Metric Threshold (Smart)

**Endpoint:** `PUT /metrics/{metric_id}/threshold`

**Description:** Intelligently updates metric thresholds using either direct modification (for metric creators) or customization system (for other users).

**Path Parameters:**

- `metric_id` (int): ID of the metric to update

**Request Body:**
```json
{
  "id": 234,
  "output": "Updated output description",
  "threshold": ">=0.98",
  "event_id": 456,
  "audit_id": 123
}
```

**Response (Direct Update):**
```json
{
  "message": "Threshold updated directly",
  "metric_id": 456,
  "event_id": 789,
  "updated_directly": true,
  "new_threshold": ">=0.98"
}
```

**Response (Customization):**
```json
{
  "message": "Threshold updated via customization",
  "metric_id": 456,
  "event_id": 789,
  "updated_directly": false,
  "is_custom": true,
  "new_threshold": ">=0.98"
}
```

**Logic:**

- **Direct Update**: If user is the metric creator in the same audit context, updates the base `MetricsValues` directly
- **Customization**: If different user or audit, creates/updates entry in `UserMetricThresholds` table
- **Effective Thresholds**: System automatically returns appropriate threshold (custom or default) in metric details

**Status Codes:**

- `200`: Successfully updated
- `403`: User audit mapping not found
- `404`: Metric-event mapping not found
- `400`: Database error

**Features:**

- **Smart Context Detection**: Automatically determines update method based on user-audit-metric relationship
- **Non-Destructive**: Original metric values preserved when using customization
- **Audit Trail**: Custom thresholds include timestamps and user tracking
- **Seamless Integration**: Effective thresholds automatically served in all metric retrieval endpoints

---

## Data Models

### Core Models

#### MetricsValues
- `id`: Primary key
- `output`: String description of the metric output
- `threshold`: String describing the threshold criteria

#### MetricsUnderlyingFeatures
- Links metric values to underlying features with ranges

#### MetricsScalePoints  
- Associates metric values with scale point definitions

#### MetricsTargetFeatures
- Links metric values to target features with ranges

### Request Models

#### MetricValuesDetail
```json
{
  "id": "integer",
  "event_id": "integer (optional)",
  "output": "string (optional)",
  "threshold": "string (required)",
  "features": "array (optional)",
  "scale_points": "object (optional)",
  "is_threshold_customized": "boolean (indicates if threshold has been personalized)"
}
```

#### MetricValueUpdate (Enhanced)
```json
{
  "id": "integer (optional - for updates)",
  "output": "string (optional)",
  "threshold": "string (optional)",
  "event_id": "integer (required)",
  "audit_id": "integer (required)",
  "features": "array (optional)",
  "scale_points": "object (optional)",
  "delete": "boolean (optional)"
}
```

#### MetricMappingCreate
```json
{
  "event_id": "integer"
}
```

## Error Handling

All endpoints return appropriate HTTP status codes:

- `200`: Success
- `400`: Bad Request (invalid data, missing required fields)
- `403`: Forbidden (insufficient permissions)
- `404`: Not Found (resource doesn't exist or no access)
- `500`: Internal Server Error

Error responses include a `detail` field with descriptive error messages.

## Authentication & Authorization

- All endpoints require valid JWT authentication
- Access is controlled through the `MappingAuditUser` system
- Users can only access metrics associated with their permitted audits
- Audit instigators (role ID 1 or 3) have additional privileges

## Notes

- Feature IDs must exist in the `UnderlyingFeatures` table
- All database operations use transactions with rollback on error
- Metric types are automatically determined based on presence of formula (quantitative) or definition (qualitative)
- Scale points and features are optional but provide enhanced metric functionality