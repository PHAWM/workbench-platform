# Performance Analysis

## Overview

The Performance Analysis API provides endpoints for managing audit evaluations, status tracking, outcome submissions, and result generation. This API handles the evaluation of event-metric pairs within audit contexts and manages user-specific audit outcomes and recommendations.

**Base Path:** `/evaluation`

**Authentication:** All endpoints require a valid JWT token via `Depends(get_current_user)`

## Access Control

Access is controlled through the `MappingAuditUser` relationship. Users can only access and modify evaluations for audits they are associated with.

---

## Endpoints

### 1. Get Status Summary

**Endpoint:** `GET /evaluation/status/{audit_id}/summary`

**Description:** Retrieves comprehensive status summary for an audit including all event-metric pair evaluations and user's overall audit outcome.

**Path Parameters:**

- `audit_id` (int): ID of the audit to get status for

**Response:**
```json
{
  "audit_criteria": [
    {
      "event_name": "Model Performance Degradation",
      "metric_name": "Accuracy Score",
      "recommendation": 2,
      "recommendation_text": "Fail",
      "status": 1,
      "status_text": "Evaluated"
    },
    {
      "event_name": "Data Drift Detection",
      "metric_name": "Distribution Variance",
      "recommendation": 1,
      "recommendation_text": "Inconclusive",
      "status": 1,
      "status_text": "Evaluated"
    },
    {
      "event_name": "Security Vulnerability",
      "metric_name": "Risk Assessment",
      "recommendation": 0,
      "recommendation_text": "Not Evaluated",
      "status": 0,
      "status_text": "Not Evaluated"
    }
  ],
  "recommendation": 2,
  "recommendation_text": "Fail",
  "notes": "Multiple critical issues identified requiring immediate attention."
}
```

**Features:**

- **Individual Criteria Status**: Shows evaluation status for each event-metric pair
- **Overall Audit Outcome**: User's consolidated recommendation and notes
- **Automatic Initialisation**: Creates audit outcome record if none exists
- **Human-Readable Labels**: Includes both numeric codes and text descriptions

**Status Codes:**

- `200`: Successfully retrieved
- `401`: Access denied to this audit
- `400`: Database error

---

### 2. Submit Audit

**Endpoint:** `PUT /evaluation/status/{audit_id}/submit`

**Description:** Submit final audit outcome with overall recommendation and notes, marking the audit as completed for the current user.

**Path Parameters:**

- `audit_id` (int): ID of the audit to submit

**Request Body:**
```json
{
  "recommendation": 3,
  "notes": "All security requirements have been thoroughly evaluated. System demonstrates robust performance across all tested scenarios with minimal risk exposure."
}
```

**Response:**
```json
{
  "message": "The Audit Outcome has been successfully submitted"
}
```

**Field Values:**

- **Recommendation**: `0` (Not Evaluated), `1` (Inconclusive), `2` (Fail), `3` (Pass)
- **Notes**: Detailed explanation of the audit findings and reasoning

**Features:**

- **Final Submission**: Automatically sets audit status to "Finished" (2)
- **Comprehensive Documentation**: Allows detailed notes for audit justification
- **Outcome Creation**: Creates audit outcome record if none exists
- **Status Update**: Updates existing outcome with final recommendation

**Status Codes:**

- `200`: Successfully submitted
- `401`: Access denied to this audit
- `400`: Database error

---

### 3. Update Individual Event-Metric Status

**Endpoint:** `PUT /evaluation/status/{audit_id}`

**Description:** Updates the evaluation status and recommendation for a specific event-metric pair within an audit.

**Path Parameters:**

- `audit_id` (int): ID of the audit

**Request Body:**
```json
{
  "event_id": 123,
  "metric_id": 456,
  "recommendation": 2,
  "notes": "Accuracy has dropped below acceptable threshold of 95%. Model requires retraining with updated dataset."
}
```

**Response:**
```json
{
  "message": "Audit Status has been updated",
  "event_id": 123,
  "audit_id": 789,
  "updated_directly": true
}
```

**Field Values:**

- **Event ID**: ID of the event being evaluated
- **Metric ID**: ID of the metric being evaluated
- **Recommendation**: `0` (Not Evaluated), `1` (Inconclusive), `2` (Fail), `3` (Pass)
- **Notes**: Detailed evaluation notes for this specific event-metric pair

**Features:**

- **Granular Control**: Update individual event-metric evaluations
- **Detailed Documentation**: Specific notes per event-metric pair
- **Access Validation**: Ensures user has access to the specific audit
- **Direct Updates**: Immediate update to evaluation status

**Status Codes:**

- `200`: Successfully updated
- `401`: Access denied to this audit
- `404`: Event-Metric pair not found or access denied
- `400`: Database error

---

### 4. Batch Update Event-Metric Status

**Endpoint:** `PUT /evaluation/status/{audit_id}/batch`

**Description:** Updates multiple event-metric pair evaluations in a single operation for efficient bulk processing.

**Path Parameters:**

- `audit_id` (int): ID of the audit

**Request Body:**
```json
[
  {
    "event_id": 123,
    "metric_id": 456,
    "user_audit_id": 789,
    "recommendation": 2,
    "notes": "Performance below threshold"
  },
  {
    "event_id": 124,
    "metric_id": 457,
    "user_audit_id": 789,
    "recommendation": 3,
    "notes": "Security measures adequate"
  },
  {
    "event_id": 125,
    "metric_id": 458,
    "user_audit_id": 789,
    "recommendation": 1,
    "notes": "Insufficient data for conclusive assessment"
  }
]
```

**Response:**
```json
{
  "message": "Audit Status has been updated",
  "updated_status": [
    {
      "event_id": 123,
      "metric_id": 456
    },
    {
      "event_id": 124,
      "metric_id": 457
    }
  ],
  "not_updated_status": [
    {
      "event_id": 125,
      "metric_id": 458
    }
  ],
  "updated_directly": true
}
```

**Features:**

- **Bulk Operations**: Process multiple evaluations efficiently
- **Partial Success Handling**: Returns both successful and failed updates
- **Error Resilience**: Continues processing even if some updates fail
- **Detailed Response**: Shows exactly which updates succeeded or failed

**Status Codes:**

- `200`: Batch operation completed (check response for individual results)
- `401`: Access denied to this audit
- `400`: Database error

---

### 5. Get Results Summary

**Endpoint:** `GET /evaluation/results/{audit_id}/summary`

**Description:** Retrieves comprehensive evaluation results summary for an audit including all event-metric pair evaluations with their values, thresholds, and outputs.

**Path Parameters:**

- `audit_id` (int): ID of the audit to get results for

**Response:**
```json
{
  "audit_criteria": [
    {
      "audit_criteria_id": 123,
      "event_id": 456,
      "event_name": "Model Performance Degradation",
      "metric_id": 789,
      "metric_name": "Accuracy Score",
      "metric_type": "quantitative",
      "threshold": 0.95,
      "output": {
        "accuracy": 0.92,
        "evaluation_date": "2024-01-15",
        "additional_metrics": {}
      },
      "recommendation": 2,
      "recommendation_text": "Fail",
      "status": 1,
      "status_text": "Evaluated",
      "notes": "Performance below acceptable threshold",
      "underlying_features": [
        {
          "id": 1,
          "feature_name": "accuracy",
          "ranges": ["0.0-0.5", "0.5-0.95", "0.95-1.0"]
        }
      ],
      "scale_points": null
    },
    {
      "audit_criteria_id": 124,
      "event_id": 457,
      "event_name": "User Experience Issue",
      "metric_id": 790,
      "metric_name": "User Satisfaction",
      "metric_type": "qualitative",
      "threshold": "Good",
      "output": {
        "satisfaction_level": "Poor"
      },
      "recommendation": 2,
      "recommendation_text": "Fail",
      "status": 1,
      "status_text": "Evaluated",
      "notes": "User satisfaction below expectations",
      "underlying_features": [],
      "scale_points": {
        "Excellent": 5,
        "Good": 4,
        "Average": 3,
        "Poor": 2,
        "Very Poor": 1
      }
    }
  ],
  "total_criteria_evaluated": 15,
  "total_criteria": 20
}
```

**Features:**

- **Detailed Results**: Shows evaluation outputs and thresholds for each event-metric pair
- **Metric Type Classification**: Indicates whether metrics are quantitative, qualitative, both, or unclassified
- **Underlying Features**: Provides feature names and ranges for quantitative metrics
- **Scale Points**: Includes scale point definitions for qualitative metrics
- **Progress Tracking**: Displays evaluation completion statistics
- **Comprehensive Data**: Includes all evaluation metadata and outcomes
- **Access Control**: Only shows results for audits accessible to the current user

**Status Codes:**

- `200`: Successfully retrieved
- `401`: Access denied to this audit
- `400`: Database error

---

### 6. Generate Evaluation Results

**Endpoint:** `POST /evaluation/results/{audit_id}/generate/`

**Description:** Generates evaluation results for audit criteria that haven't been evaluated yet or have errors. Runs the evaluation process for model-dataset pairs using specified metrics.

**Path Parameters:**

- `audit_id` (int): ID of the audit to generate results for

**Response:**
```json
{
  "audit_criteria": [
    {
      "audit_criteria_id": 123,
      "output": {
        "underlying_features": {
          "gender": {
            "male": {
              "accuracy": 0.89,
              "precision": 0.87,
              "recall": 0.91
            },
            "female": {
              "accuracy": 0.92,
              "precision": 0.90,
              "recall": 0.94
            }
          }
        }
      },
      "target_features": "accuracy",
      "threshold": 0.95,
      "requirements": 0
    }
  ]
}
```

**Features:**

- **Automatic Evaluation**: Runs evaluation for criteria with missing or error outputs
- **Model Integration**: Uses stored model metadata and API keys for evaluation
- **Target Feature Support**: Evaluates based on specified target features (metric functions)
- **Underlying Features**: Groups results by underlying features (e.g., gender, age) with their defined ranges
- **Range Filtering**: Only evaluates data matching the defined ranges for each underlying feature
- **Result Persistence**: Stores evaluation results in the database
- **Custom Thresholds**: Supports user-specific custom thresholds per metric
- **Error Reporting**: Returns detailed error information including feature names, ranges, and data samples

**Status Codes:**

- `200`: Successfully generated results
- `401`: Access denied to this audit
- `400`: Database error or evaluation failure

---

### 7. Clear Output Evaluation Results

**Endpoint:** `DELETE /evaluation/results/{audit_id}/clear/output`

**Description:** Clears cached output evaluation results to force re-running inference. This deletes all outcome evaluation values and their mappings for the current user and audit.

**Path Parameters:**

- `audit_id` (int): ID of the audit to clear results for

**Response:**
```json
{
  "message": "Output evaluation results cleared",
  "deleted_count": 15
}
```

**Features:**

- **Cache Invalidation**: Forces fresh evaluation on next generate call
- **User-Specific**: Only clears results for the current user
- **Cascade Deletion**: Removes both outcome values and mappings
- **Audit Isolation**: Only affects the specified audit

**Status Codes:**

- `200`: Successfully cleared results
- `404`: User not associated with this audit
- `400`: Database error

---

### 8. Generate Output Evaluation Results

**Endpoint:** `POST /evaluation/results/{audit_id}/generate/output`

**Description:** Generates output evaluation results specifically for evaluation data sets, using stored output evaluation data rather than model-dataset pairs.

**Path Parameters:**

- `audit_id` (int): ID of the audit to generate output evaluation for

**Response:**
```json
{
  "audit_criteria": [
    {
      "audit_criteria_id": 123,
      "output": {
        "underlying_features": {
          "gender": {
            "male": {
              "demographic_parity": 0.15,
              "statistical_parity": 0.12
            },
            "female": {
              "demographic_parity": 0.18,
              "statistical_parity": 0.14
            }
          },
          "age": {
            "error": "Insufficient data for evaluation",
            "error_type": "ValueError",
            "feature_name": "age",
            "defined_ranges": ["10-15", "16-20"],
            "data_sample_count": 48,
            "unique_values_in_data": [4, 5, 6, 7, 8, 9]
          }
        }
      },
      "target_features": "demographic_parity",
      "threshold": 0.2,
      "requirements": 0
    }
  ]
}
```

**Features:**

- **Output-Specific Evaluation**: Uses pre-stored output evaluation datasets
- **Bias and Fairness Metrics**: Specialised evaluation for model fairness
- **Underlying Features Grouping**: Results structured by underlying features (sensitive attributes)
- **Range-Based Filtering**: Only processes data within defined ranges for each feature
- **Result Caching**: Stores and reuses evaluation results
- **API Integration**: Uses model-specific API keys for evaluation (optional)
- **Custom Thresholds**: Supports user-defined thresholds per metric
- **Efficient Processing**: Groups evaluations by metric to avoid redundant computation
- **Detailed Error Reporting**: Provides comprehensive error information including:
  - Error type and message
  - Feature name causing the error
  - Defined ranges vs actual data values
  - Sample count and unique values in data

**Status Codes:**

- `200`: Successfully generated output evaluation
- `404`: User not associated with audit or no uploaded data found
- `400`: Database error or evaluation failure

---

### 9. Batch Update Outcome Evaluation

**Endpoint:** `PUT /evaluation/outcome/{audit_id}/batch`

**Description:** Batch updates outcome evaluation values (meet_requirement status) for multiple event-metric pairs. This is used to update whether output evaluation results meet the specified requirements.

**Path Parameters:**

- `audit_id` (int): ID of the audit

**Request Body:**
```json
[
  {
    "event_id": 123,
    "metric_id": 456,
    "recommendation": 1
  },
  {
    "event_id": 124,
    "metric_id": 457,
    "recommendation": 0
  }
]
```

**Response:**
```json
{
  "message": "Outcome evaluation status has been updated",
  "updated_outcomes": [
    {
      "event_id": 123,
      "metric_id": 456,
      "meet_requirement": 1
    }
  ],
  "not_updated_outcomes": [
    {
      "event_id": 124,
      "metric_id": 457
    }
  ],
  "total_updated": 1,
  "total_not_updated": 1
}
```

**Features:**

- **Bulk Operations**: Update multiple outcome evaluations efficiently
- **Requirement Tracking**: Set whether outputs meet requirements
- **Partial Success**: Returns both successful and failed updates
- **Detailed Response**: Shows update statistics and details

**Status Codes:**

- `200`: Batch operation completed
- `401`: Access denied to this audit
- `400`: Database error

---

## Output Structure

### Underlying Features Format

All evaluation outputs are now structured by underlying features (sensitive attributes). The format is:

```json
{
  "output": {
    "underlying_features": {
      "<feature_name>": {
        "<range_value_1>": {
          "<metric_result_1>": value,
          "<metric_result_2>": value
        },
        "<range_value_2>": {
          "<metric_result_1>": value,
          "<metric_result_2>": value
        }
      }
    }
  }
}
```

**Example with Gender:**
```json
{
  "underlying_features": {
    "gender": {
      "male": {
        "accuracy": 0.89,
        "precision": 0.87,
        "recall": 0.91
      },
      "female": {
        "accuracy": 0.92,
        "precision": 0.90,
        "recall": 0.94
      }
    }
  }
}
```

**Error Format:**
When an error occurs during evaluation of a feature, the output includes diagnostic information:
```json
{
  "underlying_features": {
    "age": {
      "error": "demographic_parity_detailed() missing 1 required positional argument",
      "error_type": "TypeError",
      "feature_name": "age",
      "defined_ranges": ["10-15", "16-20", "21-25"],
      "data_sample_count": 48,
      "unique_values_in_data": [4, 5, 6, 7, 8, 9]
    }
  }
}
```

**Key Points:**
- Only values matching the defined ranges are included in results
- Each range value gets its own evaluation metrics
- Errors include enough context to debug data/configuration mismatches
- All numpy types are converted to JSON-serializable Python types

---

## Data Models

### Core Models

#### AuditOutcomeStatus
```json
{
  "event_name": "string (name of the event)",
  "metric_name": "string (name of the metric)",
  "recommendation": "integer (0-3)",
  "recommendation_text": "string (human-readable recommendation)",
  "status": "integer (0-1)",
  "status_text": "string (human-readable status)"
}
```

#### AuditOutcomeResponse
```json
{
  "audit_criteria": "array of AuditOutcomeStatus objects",
  "recommendation": "integer (0-3, overall audit recommendation)",
  "recommendation_text": "string (human-readable overall recommendation)",
  "notes": "string (overall audit notes)"
}
```

### Request Models

#### AuditSubmit
```json
{
  "recommendation": "integer (0-3, required)",
  "notes": "string (optional, detailed audit findings)"
}
```

#### AuditStatusUpdate
```json
{
  "event_id": "integer (required)",
  "metric_id": "integer (required)",
  "recommendation": "integer (0-3, optional)",
  "notes": "string (optional)"
}
```

#### BatchAuditStatusUpdate
```json
[
  {
    "event_id": "integer (required)",
    "metric_id": "integer (required)",
    "user_audit_id": "integer (required)",
    "recommendation": "integer (0-3, optional)",
    "notes": "string (optional)"
  }
]
```

### Response Models

#### AuditEvaluationStatus
```json
{
  "audit_criteria_id": "integer (unique identifier for the evaluation)",
  "event_id": "integer (event identifier)",
  "event_name": "string (name of the event)",
  "metric_id": "integer (metric identifier)",
  "metric_name": "string (name of the metric)",
  "metric_type": "string (quantitative|qualitative|both|unclassified)",
  "threshold": "string (threshold value for evaluation)",
  "output": "object (evaluation results and metrics)",
  "recommendation": "integer (0-3)",
  "recommendation_text": "string (human-readable recommendation)",
  "status": "integer (0-1)",
  "status_text": "string (human-readable status)",
  "notes": "string (evaluation notes)",
  "underlying_features": "array of objects (feature details with id, feature_name, and ranges)",
  "scale_points": "object (scale point definitions for qualitative metrics, null for quantitative)"
}
```

#### AuditEvaluationResponse
```json
{
  "audit_criteria": "array of AuditEvaluationStatus objects",
  "total_criteria_evaluated": "integer (number of evaluated criteria)",
  "total_criteria": "integer (total number of criteria)"
}
```

#### OutputEvaluationItem
```json
{
  "audit_criteria_id": "integer (unique identifier for the evaluation)",
  "output": "object (evaluation results and outputs)",
  "target_features": "string (target feature being evaluated)",
  "threshold": "number (threshold value for evaluation)"
}
```

#### OutputEvaluationResponse
```json
{
  "audit_criteria": "array of OutputEvaluationItem objects"
}
```

## Status and Recommendation Codes

### Evaluation Status Codes
- `0`: Not Evaluated - No assessment has been performed
- `1`: Evaluated - Assessment has been completed

### Recommendation Codes
- `0`: Not Evaluated - No recommendation provided
- `1`: Inconclusive - Insufficient evidence for clear determination
- `2`: Fail - Significant issues identified requiring remediation
- `3`: Pass - Meets requirements and acceptable risk levels

### Status Text Mapping
The system provides human-readable text for all numeric codes through `STATUS_TEXT_MAP` and `RECOMMENDATION_TEXT_MAP` enumerations.

## Key Features

### Comprehensive Audit Evaluation

**Event-Metric Pair Assessment:**

- Individual evaluation of each event-metric combination
- Granular recommendation tracking per pair
- Detailed notes capability for each evaluation
- Status tracking for evaluation completion

**Overall Audit Outcome:**

- Consolidated user recommendation for entire audit
- Comprehensive notes field for overall findings
- Automatic status management (Not Started/In Progress/Finished)
- User-specific outcome isolation

### Efficient Batch Processing

**Bulk Update Capabilities:**

- Process multiple event-metric evaluations simultaneously
- Partial success handling with detailed error reporting
- Efficient database operations with transaction management
- Resilient error handling for large datasets

### Automatic Management

**Smart Initialisation:**

- Automatic creation of audit outcome records when needed
- Default status assignment for new evaluations
- Seamless user experience without manual setup
- Consistent state management across operations

### Access Control and Security

**Audit-Scoped Access:**

- All operations validated against user audit permissions
- Event-metric pair access verification
- User-specific outcome isolation
- Comprehensive authorisation checks

## Error Handling

All endpoints return appropriate HTTP status codes:

- `200`: Success
- `400`: Bad Request (database errors, invalid data)
- `401`: Unauthorized (access denied to audit)
- `404`: Not Found (event-metric pair not found)
- `500`: Internal Server Error

Error responses include a `detail` field with descriptive error messages.

## Authentication & Authorisation

- All endpoints require valid JWT authentication
- Access is controlled through `MappingAuditUser` relationship
- Users can only evaluate audits they are associated with
- Event-metric pair access is validated per operation
- Outcome modifications are user-specific and isolated

## Usage Workflow

### Typical Audit Evaluation Process

1. **Get Status Summary**: Review current evaluation state
   ```
   GET /evaluation/status/{audit_id}/summary
   ```

2. **Evaluate Individual Pairs**: Assess each event-metric combination
   ```
   PUT /evaluation/status/{audit_id}
   ```

3. **Bulk Updates** (Optional): Process multiple evaluations efficiently
   ```
   PUT /evaluation/status/{audit_id}/batch
   ```

4. **Final Submission**: Submit overall audit outcome
   ```
   PUT /evaluation/status/{audit_id}/submit
   ```

### Best Practices

- **Progressive Evaluation**: Use individual updates for detailed assessment
- **Batch Processing**: Use batch updates for efficiency with large datasets
- **Comprehensive Documentation**: Include detailed notes for audit transparency
- **Status Monitoring**: Regular status summary checks for progress tracking
- **Final Review**: Thorough review before final submission

## Notes

- All evaluation operations are user-specific and isolated
- Audit outcomes are automatically initialized when first accessed
- Batch operations provide partial success handling for resilience
- Status and recommendation codes have human-readable text mappings
- All database operations use transactions with comprehensive error handling
- Event-metric pair evaluations support detailed per-pair documentation