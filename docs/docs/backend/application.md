# Audits & Applications API 

## Overview

The Audits & Applications API provides comprehensive endpoints for managing audits and their associated applications with enhanced user-specific outcomes and collaborative evaluation features. This API handles audit lifecycle management, application registration, and complex relationships between audits, models, pipelines, and datasets.

**Base Path:** `/audits`

**Authentication:** All endpoints require a valid JWT token via `Depends(get_current_user)`

## Access Control

Access is controlled through the `MappingAuditUser` relationship with role-based permissions. Users can only access audits they are associated with based on their assigned roles (auditor, audit_instigator, etc.).

---

## Endpoints

### 1. Get All Audits Overview

**Endpoint:** `GET /audits/`

**Description:** Retrieves an overview of all audits accessible to the current user with status summaries, completion percentages, and **personalized audit outcomes**.

**Response:**
```json
{
  "audits": [
    {
      "id": 123,
      "name": "Q4 ML Model Audit",
      "description": "Comprehensive audit of ML models for Q4 compliance",
      "audit_instigator": "John Smith",
      "status": 1,
      "status_text": "In Progress",
      "completion_percentage": 75.5,
      "recommendation": "Pass",
      "application_id": 456,
      "application_name": "ML Prediction Service",
      "application_description": "Production ML service for customer predictions",
      "application_organisation": "TechCorp Inc",
      "application_url": "https://api.techcorp.com/ml-service",
      "access_type": 1,
      "testing_evaluation": {
        "test_coverage": "95%",
        "performance_metrics": ["accuracy", "precision", "recall"]
      },
      "deployment": {
        "environment": "production",
        "scaling": "auto"
      },
      "business_case": "Improve customer conversion rates through ML predictions",
      "legal_framework": "GDPR compliant"
    }
  ],
  "total_audits": 5,
  "status_summary": {
    "Not Started": 1,
    "In Progress": 3,
    "Finished": 1
  }
}
```

**Enhanced Features:**

 - **User-Specific Outcomes**: Recommendations now reflect individual user assessments via `MappingAuditOutcomeUser`
 - **Detailed Audit Information**: Added audit description field for comprehensive context
 - **Personalized Status Tracking**: Each user has their own completion percentage and status
 - **Outcome-Based Recommendations**: Pass/Fail/Inconclusive/Not Evaluated based on user evaluation

**Status Calculation:**

 - **Not Started (0)**: No events have been evaluated by this user
 - **In Progress (1)**: Some events evaluated by this user, but not all
 - **Finished (2)**: All events have been evaluated by this user
 - **Completion Percentage**: (User's evaluated events / Total events) × 100

---

### 2. Get Single Audit Overview

**Endpoint:** `GET /audits/{audit_id}`

**Description:** Retrieves detailed overview information for a specific audit including application details, completion status, and **user-specific audit outcome**.

**Path Parameters:**

 - `audit_id` (int): ID of the audit to retrieve

**Response:**
```json
{
  "id": 123,
  "name": "Q4 ML Model Audit",
  "description": "Comprehensive audit of ML models for Q4 compliance",
  "audit_instigator": "John Smith",
  "status": 1,
  "status_text": "In Progress",
  "completion_percentage": 75.5,
  "recommendation": "Pass",
  "application_id": 456,
  "application_name": "ML Prediction Service",
  "application_description": "Production ML service for customer predictions",
  "application_organisation": "TechCorp Inc",
  "application_url": "https://api.techcorp.com/ml-service",
  "access_type": 1,
  "testing_evaluation": {
    "test_coverage": "95%",
    "performance_metrics": ["accuracy", "precision", "recall"],
    "automated_testing": true
  },
  "deployment": {
    "environment": "production",
    "scaling": "auto",
    "load_balancer": "nginx",
    "monitoring": "prometheus"
  },
  "business_case": "Improve customer conversion rates through ML predictions",
  "legal_framework": "GDPR compliant with data retention policies"
}
```

**Enhanced Features:**

 - **User-Specific Outcomes**: Recommendation reflects current user's individual assessment
 - **Comprehensive Context**: Added audit description for detailed background information
 - **Personalized Progress**: Status and completion percentage specific to user's evaluation progress

**Status Codes:**

 - `200`: Successfully retrieved
 - `403`: Access denied to this audit
 - `404`: Audit not found

---

### 3. Create Audit

**Endpoint:** `POST /audits/`

**Description:** Creates a new audit with optional model associations, pipeline setup, and **automatic user outcome initialization** in a single operation.

**Request Body:**
```json
{
  "name": "Q1 Model Security Audit",
  "description": "Comprehensive security assessment of ML models for Q1 compliance",
  "application_id": 456,
  "status": 0,
  "create_pipeline": true,
  "model_ids": [101, 102, 103]
}
```

**Response:**
```json
{
  "id": 124,
  "name": "Q1 Model Security Audit",
  "description": "Comprehensive security assessment of ML models for Q1 compliance",
  "status": 0,
  "recommendation": null,
  "application_id": 456,
  "application_name": "ML Prediction Service",
  "pipeline_created": 55,
  "models_associated": 3,
  "model_association_ids": [301, 302, 303],
  "message": "Audit created successfully with model associations and pipeline"
}
```

**Enhanced Features:**

- **Automatic Outcome Initialization**: Creates initial `MappingAuditOutcomeUser` entry for the creator
- **Comprehensive Context**: Added description field for detailed audit documentation
- **Complete Setup**: All audit relationships established in single transaction

**What Gets Created:**

- Base audit record with description
- Audit-user association for the creator
- Initial audit outcome record (status: 0, recommendation: 0)
- Optional audit pipeline and linking
- Model associations if provided
- Application-audit mapping

**Status Codes:**

- `200`: Successfully created
- `400`: Application not found or invalid data

---

### 4. Get Complete Audit Details

**Endpoint:** `GET /audits/{audit_id}/complete`

**Description:** Retrieves comprehensive audit information including all relationships (models, pipelines, events, datasets) with **user-specific recommendations**.

**Path Parameters:**
- `audit_id` (int or "all"): Specific audit ID or "all" for all user audits

**Response (Single Audit):**
```json
{
  "id": 123,
  "name": "Q4 ML Model Audit",
  "description": "Comprehensive audit of ML models for Q4 compliance",
  "audit_insigator": "John Smith",
  "status": 1,
  "status_text": "In Progress",
  "recommendation": "Pass",
  "application_id": 456,
  "application_name": "ML Prediction Service",
  "associated_models": [
    {
      "model_id": 101,
      "model_name": "Customer Prediction Model",
      "model_type": true,
      "model_type_text": "Generative AI",
      "task": "text-generation"
    },
    {
      "model_id": 102,
      "model_name": "Risk Assessment Model",
      "model_type": false,
      "model_type_text": "Predictive AI",
      "task": "classification"
    }
  ],
  "audit_pipelines": [
    {
      "pipeline_id": 55,
      "associated_events": [
        {
          "event_id": 201,
          "description": "Model drift detected",
          "cause": "Changes in input data distribution",
          "likelihood": 0.7,
          "magnitude": 0.8,
          "valence": -0.9
        }
      ]
    }
  ],
  "model_dataset_mappings": [
    {
      "model_id": 101,
      "model_name": "Customer Prediction Model",
      "dataset_id": 301,
      "dataset_purpose": "Training data for customer behavior prediction"
    }
  ],
  "total_models": 2,
  "total_pipelines": 1,
  "total_mappings": 5
}
```

**Response (All Audits):** Array of the above audit objects

**Enhanced Features:**

- **User-Specific Recommendations**: Each audit shows current user's individual outcome assessment
- **Comprehensive Context**: Added audit description for detailed background
- **Personalized View**: All recommendations reflect user's specific evaluation

**Access Control:**

- Requires "auditor" role for the specific audit
- When requesting "all", returns all audits where user has "auditor" role

---

### 5. Get Audit Summary

**Endpoint:** `GET /audits/{audit_id}/summary`

**Description:** Retrieves audit summary with serialized JSON fields from the application.

**Path Parameters:**
- `audit_id` (int): ID of the audit

**Response:**
```json
{
  "audit_summary": {
    "audit": {
      "id": 123,
      "name": "Q4 ML Model Audit",
      "status": 1,
      "recommendation": "Continue monitoring"
    }
  },
  "application_testing": "{\"testing_evaluation\":{\"test_coverage\":\"95%\",\"performance_metrics\":[\"accuracy\",\"precision\",\"recall\"]}}",
  "application_deployment": "{\"deployment\":{\"environment\":\"production\",\"scaling\":\"auto\"}}"
}
```

**Note:** This endpoint specifically serializes JSON fields for frontend consumption.

---

### 6. Update Audit Outcome

**Endpoint:** `PUT /audits/{audit_id}/outcome`

**Description:** Updates the current user's specific audit outcome including status, recommendation, and notes.

**Path Parameters:**
- `audit_id` (int): ID of the audit to update outcome for

**Request Body:**
```json
{
  "status": 2,
  "recommendation": 3,
  "notes": "All security requirements have been met. Model demonstrates robust performance under adversarial conditions."
}
```

**Response:**
```json
{
  "message": "Audit outcome updated successfully",
  "outcome_id": 789
}
```

**Field Values:**

- **Status**: `0` (Not Started), `1` (In Progress), `2` (Finished)
- **Recommendation**: `0` (Not Evaluated), `1` (Inconclusive), `2` (Fail), `3` (Pass)
- **Notes**: Free-text field for detailed comments and observations

**Features:**

- **User-Specific**: Each user can have their own audit outcome
- **Comprehensive Assessment**: Status tracks progress, recommendation tracks final assessment
- **Detailed Documentation**: Notes field for comprehensive evaluation details
- **Automatic Creation**: Creates new outcome record if none exists

**Status Codes:**

- `200`: Successfully updated
- `403`: Access denied to this audit
- `400`: Database error

---

### 7. Get Audit Outcome

**Endpoint:** `GET /audits/{audit_id}/outcome`

**Description:** Retrieves the current user's specific audit outcome including status, recommendation, and notes.

**Path Parameters:**
- `audit_id` (int): ID of the audit to get outcome for

**Response:**
```json
{
  "status": 2,
  "status_text": "Finished",
  "recommendation": 3,
  "recommendation_text": "Pass",
  "notes": "All security requirements have been met. Model demonstrates robust performance under adversarial conditions."
}
```

**Default Response (No Outcome Yet):**
```json
{
  "status": 0,
  "status_text": "Not Started",
  "recommendation": 0,
  "recommendation_text": "Not Evaluated",
  "notes": null
}
```

**Features:**

 - **User-Specific**: Returns current user's individual assessment
 - **Human-Readable**: Includes both numeric codes and text descriptions
 - **Graceful Defaults**: Returns sensible defaults if no outcome exists yet
 - **Complete Information**: All outcome data in single response

**Status Codes:**

 - `200`: Successfully retrieved
 - `403`: Access denied to this audit

---

---

### 8. Invite Auditor

**Endpoint:** `POST /audits/{audit_id}/invite`

**Access:** Audit instigator only (`get_audit_instigator_access` dependency)

**Description:** Invites a user to participate in an audit as an auditor by email address. Handles two cases automatically:

- **New user** — creates a placeholder account (inactive, no password), assigns them to the audit, and sends an invitation email containing a link to set their password.
- **Existing user** — assigns them to the audit directly and sends a notification email. They log in with their existing credentials.

**Path Parameters:**
- `audit_id` (int): ID of the audit to invite the auditor to

**Request Body:**
```json
{
  "email": "auditor@example.com"
}
```

**Response:**
```json
{
  "audit_id": 123,
  "audit_name": "Q4 ML Model Audit",
  "user_id": "550e8400-e29b-41d4-a716-446655440000",
  "user_name": "Jane Auditor",
  "user_email": "auditor@example.com",
  "is_new_user": true,
  "invitation_token": "abc123...",
  "invitation_expires": "2026-04-27T10:00:00+00:00",
  "message": "User Jane Auditor successfully invited to audit 'Q4 ML Model Audit'"
}
```

**What gets created:**
- `User` record (if new) — `is_active=False`, `is_verified=False` until they accept the invite
- `MappingAuditUser` — links user to audit with the `auditor` role
- `MappingAuditOutcomeUser` — initial outcome row (status `0`, recommendation `0`) so progress tracking works immediately
- `UserInvitation` — 7-day token for the set-password flow (new users only)

**Auditor onboarding flow** (after receiving the invitation email):

1. `POST /users/accept-invite` — validate the token, check whether password still needs to be set
2. `POST /users/set-password-with-invite` — set password and activate the account
3. Login normally with `POST /login/access-token`

**Status Codes:**
- `200`: Invited successfully
- `403`: Caller is not the audit instigator
- `404`: Audit not found
- `409`: That email is already assigned to this audit

---

## Application Management Endpoints

### 9. Create Application

**Endpoint:** `POST /audits/applications/`

**Description:** Creates a new application with comprehensive metadata.

**Query Parameters:**

 - `name` (str): Application name
 - `description` (str): Application description
 - `url` (str): Application URL (must be valid HTTP/HTTPS)
 - `access_type` (int): Access type (0: Black Box, 1: Grey Box, 2: White Box)
 - `testing_evaluation` (dict): Testing and evaluation configuration
 - `deployment` (dict): Deployment configuration
 - `business_case` (str): Business justification
 - `legal_framework` (str): Legal compliance information

**Example Request:**
```
POST /audits/applications/?name=ML%20Service&description=Production%20ML%20service&url=https://api.example.com&access_type=1&testing_evaluation={"coverage":"95%"}&deployment={"env":"prod"}&business_case=Revenue%20growth&legal_framework=GDPR
```

**Response:**
```json
{
  "id": 456,
  "name": "ML Service",
  "description": "Production ML service",
  "organisation": "TechCorp",
  "url": "https://api.example.com",
  "access_type": 1,
  "testing_evaluation": {"coverage": "95%"},
  "deployment": {"env": "prod"},
  "business_case": "Revenue growth",
  "legal_framework": "GDPR"
}
```

---

### 10. Update Application

**Endpoint:** `PUT /audits/applications/{application_id}`

**Description:** Updates an existing application with partial data.

**Path Parameters:**
- `application_id` (int): ID of the application to update

**Request Body:**
```json
{
  "name": "Updated ML Service",
  "description": "Updated description",
  "url": "https://newapi.example.com",
  "access_type": 2,
  "organisation": "TechCorp Inc",
  "testing_evaluation": {
    "test_coverage": "98%",
    "performance_metrics": ["accuracy", "precision", "recall", "f1-score"],
    "automated_testing": true,
    "ci_cd_integration": true
  },
  "deployment": {
    "environment": "production",
    "scaling": "kubernetes",
    "load_balancer": "ingress-nginx",
    "monitoring": "prometheus + grafana",
    "logging": "elk-stack"
  },
  "business_case": "Enhanced customer experience and revenue growth",
  "legal_framework": "GDPR and CCPA compliant with audit trails"
}
```

**Response:** Updated application object

---

## Data Models

### Core Models

#### Audit
```json
{
  "id": "integer",
  "name": "string (required)",
  "description": "string (optional, added for context)",
  "status": "integer (0-2, default: 0)",
  "application_id": "integer (required)"
}
```

#### Application
```json
{
  "id": "integer",
  "name": "string (required)",
  "description": "string (required)",
  "organisation": "string (required)",
  "url": "string (required, valid URL)",
  "access_type": "integer (0-2, required)",
  "testing_evaluation": "object (required)",
  "deployment": "object (required)",
  "business_case": "string (required)",
  "legal_framework": "string (required)"
}
```

#### MappingAuditOutcomeUser
```json
{
  "id": "integer",
  "user_audit_id": "integer (foreign key)",
  "audit_id": "integer (foreign key)",
  "status": "integer (0-2)",
  "recommendation": "integer (0-3)",
  "notes": "string (optional)"
}
```

### Request Models

#### AuditCompleteCreate
```json
{
  "name": "string (required)",
  "description": "string (optional, for context)",
  "application_id": "integer (required)",
  "status": "integer (default: 0)",
  "create_pipeline": "boolean (default: false)",
  "model_ids": "array of integers (optional)"
}
```

#### ApplicationUpdate
```json
{
  "name": "string (optional)",
  "description": "string (optional)",
  "url": "string (optional, must be valid URL)",
  "access_type": "integer (optional, 0-2)",
  "organisation": "string (optional)",
  "testing_evaluation": "object (optional)",
  "deployment": "object (optional)",
  "business_case": "string (optional)",
  "legal_framework": "string (optional)"
}
```

### Response Models

#### AuditOverviewResponse
 - Combines audit data with application details
 - Includes calculated status and completion percentage
 - Shows audit instigator information
 - **NEW**: User-specific recommendation from `MappingAuditOutcomeUser`
 - **NEW**: Audit description for comprehensive context
 
#### AuditCompleteResponse
 - Comprehensive audit information
 - Associated models with type classification
 - Pipeline details with events
 - Model-dataset mappings
 - Aggregated counts
 - **NEW**: User-specific recommendations throughout

## Key System Features

### User-Specific Audit Outcomes System

The audit system implements a sophisticated outcome management system that allows individual users to maintain their own assessments while preserving collaborative audit data:

**How It Works:**

1. **Individual Assessments**: Each user can provide their own audit outcome via `MappingAuditOutcomeUser`
2. **Personalized Recommendations**: Audit recommendations are specific to each user's evaluation
3. **Collaborative Framework**: Multiple users can work on the same audit with different conclusions
4. **Progress Tracking**: Each user has their own completion status and progress metrics

**Benefits:**

- **Independent Evaluation**: Users can reach different conclusions on the same audit
- **Comprehensive Documentation**: Status, recommendation, and detailed notes per user
- **Audit Trail**: All individual assessments preserved for transparency
- **Flexibility**: Supports both individual and collaborative audit processes

### Audit Outcome Schema

**Status Levels:**

- `0`: Not Started - User hasn't begun evaluation
- `1`: In Progress - User is actively evaluating events
- `2`: Finished - User has completed their evaluation

**Recommendation Types:**

- `0`: Not Evaluated - No assessment provided yet
- `1`: Inconclusive - Insufficient evidence for clear determination
- `2`: Fail - Audit reveals significant issues requiring remediation
- `3`: Pass - Audit demonstrates compliance and acceptable risk levels

### Enhanced Audit Context

**Comprehensive Documentation:**

- **Audit Description**: Detailed context and scope for each audit
- **Application Integration**: Full application metadata including business case and legal framework
- **Model Associations**: Direct linking to specific models under evaluation
- **Pipeline Integration**: Workflow management through audit pipelines

### Advanced Status Calculation

**Dynamic Progress Tracking:**

- **Event-Based Completion**: Progress calculated from individual event evaluations
- **User-Specific Metrics**: Each user's completion percentage tracked independently  
- **Real-Time Updates**: Status automatically updates as events are evaluated
- **Role-Based Access**: Different progress views based on user roles

### Multi-User Collaboration Features

**Collaborative Audit Management:**

- **Role Differentiation**: Audit instigators vs. regular auditors
- **Independent Outcomes**: Each user maintains separate evaluation results
- **Shared Resources**: Common access to events, metrics, and application data
- **Coordinated Workflow**: Pipeline management for structured audit processes

### Access Control and Security

**Multi-Level Permission System:**

- **Audit-User Mapping**: Base access through `MappingAuditUser` with role assignments
- **Outcome Isolation**: User outcomes are private and separate
- **Application Security**: URL validation and access type management
- **Data Integrity**: Transactional operations with comprehensive error handling

## Status Codes and Access Types

### Audit Status Codes
- `0`: Not Started
- `1`: In Progress  
- `2`: Finished

### Audit Recommendation Codes
- `0`: Not Evaluated
- `1`: Inconclusive
- `2`: Fail
- `3`: Pass

### Application Access Types
- `0`: Black Box (no internal access)
- `1`: Grey Box (limited internal access)
- `2`: White Box (full internal access)

### Model Types
- `false` (0): Predictive AI
- `true` (1): Generative AI

## Error Handling

All endpoints return appropriate HTTP status codes:

- `200`: Success
- `400`: Bad Request (invalid data, missing application)
- `403`: Forbidden (no access to audit)
- `404`: Not Found (audit/application not found)
- `500`: Internal Server Error

Error responses include a `detail` field with descriptive error messages.

## Authentication & Authorization

- All endpoints require valid JWT authentication
- Access is controlled through `MappingAuditUser` with role verification
- Only users with appropriate roles can access specific audits
- Application operations may have additional permission checks
- User outcomes are isolated per user-audit combination

## Notes

- Audit completion is calculated based on user-specific event evaluation status
- All database operations use transactions with rollback on error
- JSON fields in applications are properly serialized for frontend consumption
- The API supports both single audit retrieval and bulk operations
- Model associations are validated before creation
- Pipeline creation is optional and can be done during audit creation
- User outcomes enable independent collaborative evaluation
- Each user can have different recommendations for the same audit