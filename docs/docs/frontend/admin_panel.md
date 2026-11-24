# Admin Panel — Frontend Integration Guide

> **Methodology reference:** [Participatory AI Auditing — Methodology V1.2](https://phawm.org/wp-content/uploads/2026/04/Participatory-AI-Auditing_Methodology_V1.2.pdf) (opens in new tab)

All endpoints require a valid JWT token: `Authorization: Bearer <token>`.

---

## Roles

| Role | Capabilities |
|------|-------------|
| `audit_instigator` | Create/update/delete audits, manage applications, invite users, set up models and datasets |
| `auditor` | View assigned audits, submit evaluations |

The user who calls `POST /audits/` is **automatically assigned** `audit_instigator` for that audit.

---

## Audit access types and what they mean for data

| `access_type` | Name | Training data available? | Model accessible? | Typical dataset setup |
|---|---|---|---|---|
| `0` | Black Box | No | No | Pre-computed results.csv only |
| `1` | Gray Box | No | Yes (live inference) | Upload input files + results.csv |
| `2` | White Box | Yes | Yes | Full dataset upload or HuggingFace import |

**Gray-box is the most common real-world case.** The audit instigator has access to the model (it runs inference) but has no training data — only input files and a pre-computed `results.csv`. The system fully supports this: the dataset can be registered with metadata only, files uploaded later, and a `results.csv` provided as output without any training data.

---

## Complete Setup Flow (audit_instigator)

### Step 1: Create Application

```
POST /audits/applications/
Content-Type: application/json

{
  "name": "SAM",
  "description": "Separation Anxiety Measure application",
  "organisation": "NHS Trust",
  "url": "https://example.com/sam",
  "access_type": 1,
  "testing_evaluation": {"test_environment": "staging"},
  "deployment": {"status": "production", "region": "UK"},
  "business_case": "Early intervention for child attachment",
  "legal_framework": "GDPR compliant"
}
```

**`access_type`:** `0` = Black Box, `1` = Gray Box, `2` = White Box

**Response:** Application object with `id`.

---

### Step 2: Select or Register a Model

The audit_instigator should first check what models already exist before creating a new one.

#### 2a: Browse existing models (picker)

```
GET /pipeline/model/
Authorization: Bearer <token>
```

**Auth:** Any authenticated user (not superuser-only).

**Response:**
```json
[
  {
    "id": 1,
    "name": "SAM",
    "model_type": false,
    "location": "http://sam-attachment-monitor:8002",
    "mcp_tool_name": "predict_attachment",
    "task": "classification",
    "acceptable_formats": ["wav", "mp3"]
  }
]
```

**Frontend behaviour:**
- Show as a **selectable list/table** with name, task, type (Predictive / Generative), and MCP status badge
- If the model the user needs is already listed, copy its `id` — skip to Step 3
- If not, create a new model below

**Check if a model's MCP server is reachable:**
```
GET /pipeline/model/{model_id}/mcp-status/
```
Returns `"status": "online"` or `"status": "offline"`. Use this to show a green/red badge.

---

#### 2b: Register an existing MCP model (if not in list)

```
POST /pipeline/model-metadata/
Content-Type: application/json

{
  "name": "SAM",
  "model_type": 0,
  "location": "http://sam-attachment-monitor:8002",
  "mcp_tool_name": "predict_attachment",
  "acceptable_formats": ["wav", "mp3"],
  "task": "classification"
}
```

`model_type`: `0` = Predictive AI, `1` = Generative AI

**Response:** Model object with `id`.

---

#### 2c: Scaffold a new MCP model service (for brand-new models)

```
POST /pipeline/model/scaffold/
Content-Type: application/json

{
  "service_name": "my-classifier",
  "tool_name": "classify_text",
  "port": 8010,
  "description": "Classify text into categories",
  "model_type": 0,
  "acceptable_formats": ["txt", "csv"],
  "task": "classification",
  "needs_s3": false
}
```

**Reserved ports:** 8002 (SAM), 8003 (Universal LLM), 8004 (ANNIF), 8005 (Eval), 8006 (PyTerrier).

Creates the MCP server directory, Dockerfile, and a `Modelmetadata` DB record. Returns a docker-compose snippet to add to `docker-compose.yml`.

---

### Step 3: Create API Key for Model

Required for the evaluation pipeline to authenticate with the model service.

```
POST /pipeline/api-keys/
Content-Type: application/json

{
  "model_api_key": "sk-your-api-key-here",
  "costing_policy": "pay-per-request",
  "model_metadata_id": 1
}
```

---

### Step 4: Select or Set Up a Dataset

The audit_instigator chooses one of three dataset modes depending on the audit's `access_type`.

#### 4a: Browse existing datasets (picker)

Always check first — another instigator may have already registered the dataset you need.

```
GET /pipeline/dataset/
Authorization: Bearer <token>
```

**Auth:** Any authenticated user.

**Response:**
```json
[
  {
    "id": 1,
    "purpose": "SAM evaluation dataset",
    "copyright_agreement": null,
    "has_input": true,
    "has_output": true,
    "input_location": "audits/audit_1/input",
    "output_location": "audits/audit_1/output"
  },
  {
    "id": 2,
    "purpose": "Gray-box audit — model output only",
    "copyright_agreement": null,
    "has_input": false,
    "has_output": true,
    "input_location": null,
    "output_location": "audits/audit_2/output"
  }
]
```

**Frontend behaviour:**
- Show a table with purpose, input/output status badges, and location
- `has_input: false` + `has_output: true` = gray-box / results-only dataset — label it clearly
- If the user selects an existing dataset, copy its `id` — skip to Step 4d
- If they need a new one, choose a mode below

---

#### 4b: Gray-box / Black-box — metadata only + results.csv

Use this when **no training data is available** — only the model and/or a pre-computed `results.csv`.

This is the correct approach for **gray-box audits** where the instigator has model access but no training dataset.

**Step 1 — Register the dataset structure (metadata only, no files yet):**

```
POST /pipeline/dataset/metadata/
Content-Type: application/json

{
  "purpose": "SAM gray-box evaluation",
  "output_metadata": {
    "headers": {"y_pred": "int", "y_actual": "int"},
    "datatypes": {"y_pred": {"type": "int", "range": [0, 1]}, "y_actual": {"type": "int", "range": [0, 1]}},
    "benchmark_dataset": false,
    "location": "audit:1/output"
  }
}
```

- `input_metadata` is **omitted** — we have no training data
- `output_metadata` describes the results file columns
- Location shorthand `audit:1/output` works for both local and S3/RustFS backends

**Step 2 — Upload the results.csv:**

```
POST /upload/audit/{audit_id}/input
Content-Type: multipart/form-data

files: results.csv
```

The `results.csv` must contain at minimum `y_pred` and `y_actual` columns (or the column names you defined in `output_metadata.headers`). Save it to `audits/audit_{id}/output/results.csv` — the evaluation pipeline reads it from there.

**Response from dataset metadata creation:**
```json
{
  "id": 3,
  "purpose": "SAM gray-box evaluation",
  "copyright_agreement": null,
  "input_metadata": null,
  "output_metadata": {
    "id": 5,
    "dataset_metadata_id": 3,
    "headers": {"y_pred": "int", "y_actual": "int"},
    "benchmark_dataset": false,
    "location": "audit:1/output"
  },
  "message": "Dataset created successfully. Underlying features: []. Target features: []."
}
```

Save the dataset `id` for Step 5.

---

#### 4c: Gray-box with live inference — upload input files

Use when the model is accessible and will run inference during the audit, but no training data exists. The instigator uploads the input files the model will receive.

**Upload files + metadata.csv describing them:**

```
POST /upload/audit/{audit_id}/input
Content-Type: multipart/form-data

files: metadata.csv
files: example_1.wav
files: example_2.wav
```

`metadata.csv` format — one row per data file:
```csv
filename,gender,age,true_label
example_1.wav,female,34,1
example_2.wav,male,27,0
```

When `metadata.csv` is present the service automatically:
- Sets `InputDatasetMetadata.location` → `audits/audit_{id}/input`
- Registers each column as an `UnderlyingFeature`
- Creates `DatasetMetadata` + `InputDatasetMetadata` linked to the audit

No `output_metadata` is needed here — it will be created when the model runs.

**Response:**
```json
{
  "message": "Processed 3 file(s) for audit 1",
  "uploaded_files": [...],
  "metadata_processed": true,
  "features_created": ["gender", "age", "filename"],
  "dataset_id": 3
}
```

---

#### 4d: White-box — full dataset (training data available)

Use for transparent-box audits where full training data exists.

**Option 1 — Manual metadata registration (files already in storage):**

```
POST /pipeline/dataset/metadata/
Content-Type: application/json

{
  "purpose": "SAM white-box evaluation dataset",
  "input_metadata": {
    "headers": {"gender": "str", "age": "int", "y_pred": "int", "y_actual": "int"},
    "datatypes": {"gender": {"type": "varchar(20)", "range": ["male", "female"]}, "age": {"type": "int", "range": [0, 100]}},
    "benchmark_dataset": false,
    "location": "audit:1/input"
  },
  "output_metadata": {
    "headers": {"prediction": "int"},
    "datatypes": {"prediction": {"type": "int", "range": [0, 1]}},
    "benchmark_dataset": false,
    "location": "audit:1/output"
  },
  "target_features": ["accuracy", "recall", "f1"]
}
```

**Location shorthand:**

| Backend | What to enter |
|---------|--------------|
| Local | `storage/audits/audit_1/input` |
| S3 / RustFS | `audits/audit_1/input` or `audit:1/input` |

**Option 2 — Import from HuggingFace / PyTorch / URL** (superuser only):

```
POST /pipeline/dataset/import/
Content-Type: application/json

{
  "source_type": "huggingface",
  "dataset_name": "imdb",
  "split": "test",
  "max_samples": 1000,
  "purpose": "Sentiment analysis benchmark"
}
```

`source_type`: `"huggingface"`, `"pytorch"`, or `"file"` (direct URL to CSV/JSON/Parquet).

---

### Step 4e: Select underlying features

After the dataset is created, show available columns so the user can pick which are **underlying features** (attributes used in fairness/performance analysis).

**Fetch available columns:**
```
GET /pipeline/dataset/columns/{dataset_id}
```

**Response:**
```json
{
  "dataset_id": 1,
  "all_columns": ["id", "gender", "age", "text", "true_value"],
  "selectable_as_features": ["gender", "age", "text"],
  "system_columns": ["id", "true_value"],
  "source": null
}
```

**Frontend:** Show `selectable_as_features` as a checkbox list. System columns are greyed out.

**Register each selected feature:**
```
POST /events/features/user
Content-Type: application/json

{"feature_name": "gender", "audit_id": 1}
```

**Verify registered features:**
```
GET /events/features/underlying/{audit_id}
```

---

### Step 4f: Select target features (metrics)

**Fetch available metrics:**
```
GET /pipeline/available-metrics/
```

Returns all metrics grouped by category (`classification`, `regression`, `fairness`, `ranking`, `calibration`, `generative_ai`, `keyword_matching`, `composite`). Common choices:

| Audit type | Recommended metrics |
|---|---|
| Classification (any box) | `accuracy`, `precision`, `recall`, `f1` |
| Fairness | `demographic_parity`, `equalized_odds`, `disparate_impact` |
| Regression | `mse`, `rmse`, `mae`, `r2` |
| Generative AI | `bleu`, `rouge`, `perplexity` |
| Keyword / subject | `keyword_accuracy` |

**Register each selected metric:**
```
POST /events/features/user/target
Content-Type: application/json

{"target_feature": "accuracy", "audit_id": 1}
```

**Verify registered target features:**
```
GET /events/features/target
```

---

### Step 4 — UI flow summary

```
┌──────────────────────────────────────────────────────────────┐
│  Step 4a: Browse existing datasets                           │
│  GET /pipeline/dataset/                                      │
│  → Pick existing dataset (has_input / has_output badges)     │
│  → Or choose a mode below                                    │
│                         │                                    │
│          ┌──────────────┼──────────────────┐                 │
│          ▼              ▼                  ▼                 │
│    Gray/Black-box   Gray-box          White-box              │
│    results.csv      live inference    full dataset           │
│    only (4b)        + input files     (4d)                   │
│                     (4c)                                     │
│          └──────────────┴──────────────────┘                 │
│                         │                                    │
│                         ▼                                    │
│  Step 4e: Select underlying features                         │
│  GET /pipeline/dataset/columns/{dataset_id}                  │
│  → POST /events/features/user for each selected              │
│                         │                                    │
│                         ▼                                    │
│  Step 4f: Select target features (metrics)                   │
│  GET /pipeline/available-metrics/                            │
│  → POST /events/features/user/target for each                │
└──────────────────────────────────────────────────────────────┘
```

---

### Step 5: Create Audit

```
POST /audits/
Content-Type: application/json

{
  "name": "SAM Gray-Box Audit",
  "description": "Auditing SAM with pre-computed results — no training data",
  "application_id": 1,
  "model_ids": [1],
  "dataset_ids": [3]
}
```

**What this creates automatically:**
- `Audit` record
- `MappingAuditUser` with `audit_instigator` role for the creating user
- `MappingAuditOutcomeUser` (initial outcome, status=0)
- `AuditPipeline`
- `MappingAuditPipelineAudit`, `MappingAuditModel`, `MappingModelDatasetAudit`, `MappingAuditApplication`

**Response:**
```json
{
  "id": 1,
  "name": "SAM Gray-Box Audit",
  "description": "Auditing SAM with pre-computed results — no training data",
  "status": 0,
  "recommendation_text": null,
  "application_id": 1,
  "application_name": "SAM",
  "pipeline_created": 1,
  "models_associated": 1,
  "model_association_ids": [1],
  "message": "Audit created successfully"
}
```

---

### Step 5b: View and manage the pipeline (model-dataset wiring)

After audit creation the instigator needs to confirm — and optionally edit — which model-dataset pairs are active in the pipeline. This is particularly important for **gray-box audits** where the model and results dataset are separate and must be explicitly connected.

**View the current pipeline:**
```
GET /audits/{audit_id}/pipeline
Authorization: Bearer <token>
```

**Response:**
```json
{
  "audit_id": 1,
  "pipeline_id": 1,
  "pairs": [
    {
      "mapping_id": 1,
      "model_id": 1,
      "model_name": "SAM",
      "dataset_id": 3,
      "dataset_purpose": "SAM gray-box evaluation",
      "dataset_has_input": false,
      "dataset_has_output": true
    }
  ],
  "total_models": 1,
  "total_datasets": 1
}
```

`dataset_has_input: false` + `dataset_has_output: true` = gray-box / results-only pair. The frontend should label this clearly (e.g. "Results only — no training data").

**Frontend behaviour:**
- Display pairs as a table: Model name | Dataset purpose | Input available | Output available | Remove button
- Show an "Add pair" button that opens a picker using `GET /pipeline/model/` and `GET /pipeline/dataset/`
- Call this endpoint on every add/remove — it returns the full updated state

---

**Add a model-dataset pair to the pipeline:**
```
POST /audits/{audit_id}/pipeline/model-dataset
Authorization: Bearer <token>
Content-Type: application/json

{
  "model_id": 1,
  "dataset_id": 3
}
```

- Only the `audit_instigator` can call this
- Returns the full updated `PipelineOverviewResponse` — no need for a separate GET call
- Returns `409` if this exact pair is already wired in
- Automatically adds `MappingAuditModel` if the model isn't already linked to the audit

**Remove a model-dataset pair from the pipeline:**
```
DELETE /audits/{audit_id}/pipeline/model-dataset/{mapping_id}
Authorization: Bearer <token>
```

`mapping_id` comes from `pairs[*].mapping_id` in the pipeline overview response. Returns the full updated pipeline overview.

---

**Gray-box pipeline wiring example:**

When creating a gray-box audit the instigator:
1. Selects existing model from `GET /pipeline/model/` picker → `model_id: 1`
2. Registers a metadata-only dataset (output only, pointing to results.csv) → `dataset_id: 3`
3. Creates the audit with `model_ids: [1]`, `dataset_ids: [3]`
4. Immediately calls `GET /audits/{audit_id}/pipeline` to confirm the pair is wired
5. If the results dataset wasn't included at creation, calls `POST /audits/{audit_id}/pipeline/model-dataset` to add it

---

### Step 6: Create Events (audit criteria)

After creation, **immediately fetch and display** the event list so the instigator can see what's been added.

**Create:**
```
POST /events/comprehensive
Content-Type: application/json

{
  "name": "Prediction Correctness",
  "description": "How well does SAM predict secure or insecure attachment",
  "cause": "Lack of diversity in data",
  "reason": "Incorrect results could negatively impact children",
  "likelihood": 0.5,
  "magnitude": 0.8,
  "valence": -1.0,
  "audit_id": 1,
  "category_id": 1,
  "entity_ids": [1, 2]
}
```

**Fetch events after creation (show in panel):**
```
GET /events/by-audit/{audit_id}
```

Returns all events for the audit with full details. Use this to render the events list in the admin panel immediately after each create/update/delete.

**Fetch categories (for dropdown):**
```
GET /events/categories
```

**Fetch categories available to this user for this audit:**
```
GET /events/categories/user/{audit_id}
```

---

### Step 7: Create Metrics

After creation, **immediately fetch and display** the metrics list.

**Quantitative metric:**
```
POST /metrics/quantitative/create
Content-Type: application/json

{
  "name": "Accuracy",
  "description": "Overall prediction accuracy",
  "reason": "Core performance metric",
  "audit_id": 1,
  "formula": "(correct predictions) / (total predictions)",
  "metric_values": [
    {
      "threshold": "70",
      "underlying_features": [{"feature_id": 1, "ranges": []}],
      "target_features": [{"feature_id": 1}]
    }
  ],
  "event_mappings": [
    {"event_id": 1}
  ]
}
```

`metric_values` — one entry per threshold/feature combination. `underlying_features[].feature_id` references an `UnderlyingFeatures.id`; `target_features[].feature_id` references a `TargetFeatures.id`. `event_mappings` links the metric to one or more events.

**Qualitative metric:**
```
POST /metrics/qualitative/create
Content-Type: application/json

{
  "name": "Keyword Salience",
  "description": "Value of subject keywords",
  "reason": "Subject quality assessment",
  "audit_id": 2,
  "definition": "Assessment of keyword value",
  "metric_values": [
    {
      "threshold": "Of Worth",
      "scale_points": {
        "Of No Worth": 0,
        "Of Little Worth": 1,
        "Of Worth": 2,
        "Of Great Worth": 3
      }
    }
  ],
  "event_mappings": [
    {"event_id": 3}
  ]
}
```

**Fetch metrics after creation (show in panel):**
```
GET /metrics/?audit_id={audit_id}
```

Returns all metrics for the audit scoped to the current user. Display as a table grouped by linked event.

**Fetch a single metric with full details:**
```
GET /metrics/{metric_id}
```

---

### Step 8: Map Events to Audit Pipeline

```
POST /events/audit-pipeline-mapping/batch
Content-Type: application/json

{
  "audit_pipeline_id": 1,
  "mappings": [
    {"event_id": 1, "metric_id": 1},
    {"event_id": 1, "metric_id": 2},
    {"event_id": 2, "metric_id": 3}
  ]
}
```

---

### Step 9: Invite Auditors

The instigator invites by **email address** — no UUID required. The backend handles two cases automatically:

```
POST /audits/{audit_id}/invite
Authorization: Bearer <token>
Content-Type: application/json

{"email": "auditor@example.com"}
```

**Auth:** `audit_instigator` only.

**Two paths depending on whether the email is registered:**

| Case | What happens | Email sent |
|------|-------------|------------|
| Email **not registered** | Placeholder account created (inactive), linked to audit | Registration email with set-password link |
| Email **already registered** | Linked to audit immediately with `auditor` role | Simple notification — "log in to see your audit" |

**Response — unregistered user:**
```json
{
  "audit_id": 1,
  "audit_name": "SAM Gray-Box Audit",
  "user_id": "...",
  "user_email": "auditor@example.com",
  "role": "auditor",
  "is_new_user": true,
  "invitation_token": "abc123...",
  "invitation_expires": "2026-04-07T10:00:00+00:00",
  "message": "Invitation sent to 'auditor@example.com'. They will receive an email to set their password and join the audit."
}
```

**Response — already registered:**
```json
{
  "audit_id": 1,
  "audit_name": "SAM Gray-Box Audit",
  "user_id": "...",
  "user_email": "auditor@example.com",
  "role": "auditor",
  "is_new_user": false,
  "invitation_token": null,
  "invitation_expires": null,
  "message": "'auditor@example.com' has been added to audit 'SAM Gray-Box Audit' and notified by email."
}
```

**Error cases:**
- `400` — user account exists but is inactive
- `409` — email already assigned to this audit

**Frontend behaviour:**
- Show `is_new_user` to display different confirmation messages
- For `is_new_user: true`: "An invitation has been sent. They need to set a password before logging in."
- For `is_new_user: false`: "User added and notified. They can log in immediately."

**New user acceptance flow:**
1. User clicks set-password link in email
2. `POST /users/accept-invite` `{"token": "..."}` — validates token
3. `POST /users/set-password-with-invite` `{"token": "...", "password": "..."}` — activates account
4. User logs in and sees the audit

---

### Step 10: Audit Timing

The backend records two complementary time signals per user per audit.

| Signal | What it measures | Stored on |
|--------|-----------------|-----------|
| `duration_seconds` | Wall-clock time from first open → submit | `MappingAuditUser` |
| `active_seconds` | Accumulated on-page time sent by the frontend | `MappingAuditUser` |

#### Backend — automatic started_at

`started_at` is set the first time a user calls `GET /audits/{audit_id}`. No frontend action required.

#### Frontend — send active session chunks

When the auditor navigates away from an audit page (or on `visibilitychange`/`beforeunload`), send the seconds the tab was actively open:

```
POST /audits/{audit_id}/session
Authorization: Bearer <token>
Content-Type: application/json

{"duration_seconds": 142}
```

**Response:**
```json
{
  "user_audit_id": 3,
  "audit_id": 1,
  "started_at": "2026-04-24T10:00:00+00:00",
  "submitted_at": null,
  "duration_seconds": null,
  "active_seconds": 142
}
```

#### Submit the audit

```
POST /audits/{audit_id}/submit
Authorization: Bearer <token>
```

No body required. Sets `submitted_at` and computes `duration_seconds = submitted_at − started_at`. Idempotent.

**Response:**
```json
{
  "user_audit_id": 3,
  "audit_id": 1,
  "started_at": "2026-04-24T10:00:00+00:00",
  "submitted_at": "2026-04-24T11:23:45+00:00",
  "duration_seconds": 5025,
  "active_seconds": 3180
}
```

#### Read timing at any point

```
GET /audits/{audit_id}/timing
Authorization: Bearer <token>
```

Returns the same `AuditTimingResponse` shape. Use this to restore a progress indicator when the auditor reopens the audit.

#### Reactivate a submitted audit (instigator)

Reopen a submitted audit so its auditors can edit their answers again — e.g. it was submitted early by mistake, or the instigator changed an event/metric after submission.

```
POST /admin/audits/{audit_id}/reactivate
Authorization: Bearer <token>
```

**Auth:** `audit_instigator` of that audit, or tenant admin.

This is the exact inverse of submit: it clears `submitted_at` and `duration_seconds` while **preserving** `started_at` and `active_seconds`. It does **not** touch any verdict, metric result, outcome, or customisation — it only reopens the edit window.

By default every submitted auditor on the audit is reactivated. Pass `?user_audit_id={id}` to reopen a single auditor's submission. Idempotent — rows that were never submitted are left untouched and not counted.

**Response:**
```json
{
  "audit_id": 1,
  "reactivated_user_audit_ids": [3, 4],
  "count": 2
}
```

- `404` — `user_audit_id` given but no such auditor on this audit

---

## Edit / Update / Delete Operations

### Application
```
PUT  /audits/applications/{application_id}
DELETE /audits/applications/{application_id}
```
Delete fails if audits are still linked — delete audits first.

### Pipeline (model-dataset wiring)
```
GET    /audits/{audit_id}/pipeline                                    ← view current pairs
POST   /audits/{audit_id}/pipeline/model-dataset                      ← add a pair
DELETE /audits/{audit_id}/pipeline/model-dataset/{mapping_id}         ← remove a pair
```
POST and DELETE both return the full updated pipeline overview — no separate GET needed.

### Model
```
PUT    /pipeline/model/{model_id}
DELETE /pipeline/model/{model_id}
```

### API Key
```
PUT    /pipeline/api-keys/{api_key_id}
DELETE /pipeline/api-keys/{api_key_id}
```

### Dataset
```
PUT    /pipeline/dataset/metadata/{dataset_id}
PUT    /pipeline/dataset/metadata/{dataset_id}/all   ← updates input + output in one call
DELETE /pipeline/dataset/metadata/{dataset_id}       ← also deletes input/output records
DELETE /pipeline/dataset/metadata/input/{input_id}
DELETE /pipeline/dataset/metadata/output/{output_id}
```

### Dataset files
```
DELETE /upload/dataset/{audit_id}
Content-Type: application/json

{"filename": "data_abc123.csv"}
```

**List uploaded files:**
```
GET /upload/dataset/{audit_id}        ← files uploaded by current user
GET /upload/audit/{audit_id}/files    ← all input files for audit
```

**View / download a file:**
```
GET /upload/audit/{audit_id}/view/{filename}
```
Also works for `output/results.csv`.

### Events
```
PUT    /events/{event_id}
DELETE /events/{event_id}
```

### Metrics
```
PUT    /metrics/{metric_id}
DELETE /metrics/{metric_id}
```

> **Two edit paths — don't confuse them.** The `PUT /events/{id}` and `PUT /metrics/{id}` endpoints above are the **auditor** path: an auditor edits the event/metric **they** created (authorised by ownership). The **instigator** path below lets the audit instigator edit **any** event/metric/entity used in **their** audit, regardless of who created it. Use the instigator endpoints from the admin panel.

### Underlying / target features
```
DELETE /events/features/user/{feature_id}?audit_id={audit_id}
DELETE /events/features/user/target/{target_feature_id}?audit_id={audit_id}
```

---

## Instigator setup edits (admin panel)

Instigator-scoped edits over an audit's setup, exposed under `/admin`. All require the caller to be the `audit_instigator` of the `audit_id` in the URL (or a tenant admin).

### Shared rows — read this first

`Events`, `Metrics` and `Entities` are **tenant-wide** rows. They carry no `audit_id`; an audit references them through mapping tables. Editing a row that two audits reference changes it for **both**.

Each endpoint therefore:
1. Verifies the row is actually linked to the `audit_id` (else `404`), so you can only edit entities that belong to your audit; and
2. Edits the shared row in place and returns the **bare updated entity** (same JSON shape as the auditor-facing `PUT /events`, `PUT /metrics`). When other audits reference the same row, they're listed in the **`X-Also-Used-By-Audits`** response header (comma-separated audit ids) so the panel can **warn the instigator** the change is not isolated. The header is absent when the row is used only by this audit. There is no copy-on-write.

All edits are **partial** — send only the fields you want to change.

### Edit an event

```
PATCH /admin/audits/{audit_id}/events/{event_id}
Content-Type: application/json

{
  "name": "Prediction Correctness",
  "description": "...",
  "cause": "...",
  "reason": "...",
  "likelihood": 0.5,
  "magnitude": 0.8,
  "valence": -1.0
}
```

**Response:** `200 OK` — the bare updated event object. When other audits share the row:
```
X-Also-Used-By-Audits: 3,7
```

- `400` — `name` empty; `likelihood` outside `[0, 1]`; `valence` outside `[-1, 1]`
- `404` — event not linked to this audit, or does not exist

### Edit a metric

`name` / `description` / `reason` edit the metric. `formula` edits the metric's **quantitative** row; `definition` edits its **qualitative** row — pass only the one that applies.

```
PATCH /admin/audits/{audit_id}/metrics/{metric_id}
Content-Type: application/json

{
  "name": "Accuracy",
  "description": "...",
  "reason": "...",
  "formula": "(correct predictions) / (total predictions)"
}
```

**Response:** `200 OK` — the bare updated metric object. When other audits share the row, they're listed in the `X-Also-Used-By-Audits` header.

- `400` — `name` empty; `formula` sent for a metric with no quantitative row; `definition` sent for a metric with no qualitative row
- `404` — metric not linked to this audit, or does not exist

### Edit an entity

```
PATCH /admin/audits/{audit_id}/entities/{entity_id}
Content-Type: application/json

{ "name": "Students", "num_individuals": 120 }
```

**Response:** `200 OK` — the bare updated entity object. When other audits share the row, they're listed in the `X-Also-Used-By-Audits` header.

- `400` — `name` empty; `num_individuals` negative
- `404` — entity not linked to this audit, or does not exist

### Manage event categories

Event categories are a tenant-wide catalogue. Create them directly from the admin panel (they can also be created as a side effect of the per-audit flow `/events/categories` — both share one catalogue). List / create / edit:

```
GET   /admin/event-categories/
POST  /admin/event-categories/
PATCH /admin/event-categories/{category_id}
```

**Auth:** superuser, tenant admin, or instigator of any audit.

**Create body** (`POST`):
```json
{ "event_name": "Privacy Risks", "description": "Risks to individual privacy" }
```
`description` is optional (defaults to `""`).

**Edit body** (`PATCH`, partial):
```json
{ "event_name": "Privacy Risks", "description": "..." }
```

- `POST` → `201` with the new category
- `400` — `event_name` empty/missing
- `409` — a category with that name already exists (create only)
- `404` — id not in catalogue (patch only)

### Manage taxonomy groups

Taxonomy groups classify event categories. Tenant-wide catalogue — list / create / edit:

```
GET   /admin/taxonomy-groups/
POST  /admin/taxonomy-groups/
PATCH /admin/taxonomy-groups/{taxonomy_id}
```

**Auth:** superuser, tenant admin, or instigator of any audit.

**Create body** (`POST`):
```json
{ "event_name": "Fairness", "description": "Fairness-related concerns", "reason": "Grouping rationale" }
```
`description` and `reason` are optional.

**Edit body** (`PATCH`, partial):
```json
{ "event_name": "Fairness", "description": "...", "reason": "..." }
```

- `POST` → `201` with the new group
- `400` — `event_name` empty/missing
- `409` — a group with that name already exists (create only)
- `404` — id not in catalogue (patch only)

---

## Storage layout reference

| Content | Local path | S3 / RustFS key |
|---------|-----------|-----------------|
| Input files | `storage/audits/audit_{id}/input/` | `audits/audit_{id}/input/` |
| Output / results | `storage/audits/audit_{id}/output/` | `audits/audit_{id}/output/` |
| Shared datasets | `storage/datasets/{name}/` | `datasets/{name}/` |
| User evaluation output | `storage/audits/audit_{id}/users/{user_id}/output_evaluation/` | same without `storage/` prefix |

Shorthand `audit:1/input` resolves to the correct path for whichever backend is active.

---

## Gray-box quick reference

Gray-box audits (access_type=1) are the most common real-world scenario. Training data is not available — only the model and possibly a pre-computed `results.csv`.

**Minimum required setup:**

1. Register application with `access_type: 1`
2. Register or select the model from `GET /pipeline/model/`
3. Register dataset with **output_metadata only** — no input_metadata
4. Upload `results.csv` to `audits/audit_{id}/output/`
5. Create audit linking model + dataset
6. Create events and metrics referencing `y_pred` / `y_actual` columns
7. Map events to pipeline

**What you do NOT need for gray-box:**
- `input_metadata` in the dataset record
- Training data files
- HuggingFace/PyTorch import
- `metadata.csv`

The evaluation pipeline will read `results.csv` directly from the output location and compute the configured metrics against `y_actual` as ground truth.
