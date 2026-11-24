# Model Service

The Model Service provides AI/ML inference capabilities through separate microservice APIs. It supports multiple model types including LLMs, audio analysis models, and subject classification.

The backend talks to model services in **two ways**:

1. **MCP (Model Context Protocol) over SSE** — the preferred path. Each model
   server exposes one or more named tools; the backend calls them through
   `MCPClientManager`. Selected when a model's metadata has an `mcp_tool_name`
   and an `http(s)://` `location`.
2. **Legacy HTTP `POST /predict`** — fallback for model servers (or generative
   LLMs via the Universal API) that do not advertise an MCP tool.

Which path is taken is decided per model in
[`run_model_inference()`](../../src/services/performance_service/inference_engine.py)
— see [MCP Integration](#mcp-integration) below.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    PHAWM Backend API                         │
│         (FastAPI — 8000 single-tenant / 8001 multi-tenant)  │
└───────┬─────────────────────────────────────────┬───────────┘
        │  MCP (SSE) preferred  /  HTTP fallback   │  MCP (SSE)
        ▼                                           ▼
  ┌─────────────────────────────────┐      ┌─────────────────────┐
  │        Model servers            │      │  Evaluation MCP      │
  │  SAM 8002 · Universal 8003 ·    │      │  server  (8005)      │
  │  ANNIF 8004  (LitServe + MCP)   │      │  evaluate_metric,    │
  └─────────────────────────────────┘      │  list_available_…    │
                                            └─────────────────────┘
```

Each model service runs as a standalone [LitServe](https://github.com/Lightning-AI/LitServe) server. Model servers and the evaluation MCP server are **not** part of either Docker Compose file — they are started separately (see [Running All Services](#running-all-services)).

> **Hostnames vs. ports.** Inside Docker the backend reaches the Universal LLM
> server at the hostname `universal-llm-api:8003` (hardcoded fallback). For other
> models the target is whatever is stored in the model's `location` field
> (e.g. `http://sam-attachment-monitor:8002`). When running everything on the
> host, use `localhost:<port>` in `location`.

---

## Available Model Services

### 1. SAM (School Attachment Monitor)

**Port:** `8002`

**Description:** Predicts attachment styles from audio and text data using multiple model types.

**Endpoint:** `POST /predict`

#### Request Format

```json
{
  "file_location": "path/to/audio/file.wav",
  "model_type": "audio"
}
```

#### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `file_location` | string | Yes | Path to the audio file for analysis |
| `model_type` | string | Yes | Model to use: `"audio"`, `"text"`, `"mc1"`, `"mc2"`, or `"all"` |

#### Model Types

| Type | Description |
|------|-------------|
| `audio` | Audio-only model for attachment prediction |
| `text` | Text-based model using transcription |
| `mc1` | Multimodal Classifier 1 (audio + text) |
| `mc2` | Multimodal Classifier 2 (audio + text) |
| `all` | Run all models and return combined results |

#### Response Format

**Single Model Response:**
```json
{
  "output": {
    "success": true,
    "model_type": "Audio Model",
    "prediction": "secure",
    "secure_probability": 0.85,
    "insecure_probability": 0.15,
    "confidence": 0.85
  }
}
```

**All Models Response (`model_type: "all"`):**
```json
{
  "output": {
    "audio_model": {
      "success": true,
      "model_type": "Audio Model",
      "prediction": "secure",
      "secure_probability": 0.85,
      "insecure_probability": 0.15,
      "confidence": 0.85
    },
    "text_model": { ... },
    "mc1_model": { ... },
    "mc2_model": { ... }
  }
}
```

#### Usage Example

```python
import requests

response = requests.post(
    "http://localhost:8002/predict",
    json={
        "file_location": "storage/audits/audit_1/input/audio.wav",
        "model_type": "all"
    }
)
print(response.json())
```

#### Running SAM Server

```bash
python -m src.services.model_service.api.SAM.server
```

---

### 2. Universal LLM Inference API

**Port:** `8003`

**Description:** Unified API for running inference on multiple LLM providers (OpenAI, Anthropic, Google, Groq) using [LiteLLM](https://github.com/BerriAI/litellm).

**Endpoint:** `POST /predict`

#### Supported Providers & Models

| Provider | Example model ids |
|----------|--------|
| OpenAI | `gpt-4o`, `gpt-4o-mini`, `gpt-4-turbo` |
| Anthropic | `claude-opus-4-8`, `claude-sonnet-4-6`, `claude-haiku-4-5-20251001` |
| Google/Gemini | `gemini-1.5-pro`, `gemini-1.5-flash` |
| Groq | `llama-3.1-70b-versatile`, `mixtral-8x7b-32768` |

> Any model id LiteLLM understands works — the lists above are illustrative.
> The provider is resolved from the model name by `_resolve_provider()`
> (`gpt`/`openai` → openai, `claude`/`anthropic` → anthropic, `gemini`/`google`
> → gemini, else openai), so name your models accordingly.

#### Single Request Format

```json
{
  "prompt": "Explain machine learning in simple terms",
  "model_name": "gpt-3.5-turbo",
  "api_key": "sk-your-api-key",
  "model_provider": "openai",
  "system_prompt": "You are a helpful assistant",
  "temperature": 0.7,
  "max_tokens": 1000
}
```

#### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `prompt` | string | Yes | - | The input prompt/message |
| `model_name` | string | Yes | - | Model identifier |
| `api_key` | string | Yes | - | API key for the provider |
| `model_provider` | string | No | `"openai"` | Provider: `"openai"`, `"anthropic"`, `"gemini"`, `"groq"` |
| `system_prompt` | string | No | - | System prompt for context |
| `temperature` | float | No | `0.7` | Sampling temperature (0-2) |
| `max_tokens` | integer | No | `1000` | Maximum tokens to generate |

#### Single Request Response

```json
{
  "success": true,
  "output": "Machine learning is a type of artificial intelligence...",
  "model_name": "gpt-3.5-turbo",
  "model_provider": "openai",
  "error": null,
  "usage": {
    "prompt_tokens": 15,
    "completion_tokens": 150,
    "total_tokens": 165
  },
  "cost": 0.000245
}
```

#### Batch Request Format

```json
{
  "batch_requests": [
    {
      "prompt": "What is Python?",
      "model_name": "gpt-3.5-turbo",
      "api_key": "sk-your-api-key",
      "model_provider": "openai"
    },
    {
      "prompt": "What is JavaScript?",
      "model_name": "claude-3-haiku-20240307",
      "api_key": "sk-ant-your-api-key",
      "model_provider": "anthropic"
    }
  ]
}
```

#### Batch Response

```json
{
  "is_batch": true,
  "batch_results": [
    {
      "success": true,
      "output": "Python is a high-level programming language...",
      "model_name": "gpt-3.5-turbo",
      "model_provider": "openai",
      "error": null,
      "usage": { ... },
      "cost": 0.000123
    },
    {
      "success": true,
      "output": "JavaScript is a scripting language...",
      "model_name": "claude-3-haiku-20240307",
      "model_provider": "anthropic",
      "error": null,
      "usage": { ... },
      "cost": 0.000089
    }
  ],
  "total_requests": 2,
  "successful_requests": 2,
  "failed_requests": 0,
  "total_cost": 0.000212,
  "total_usage": {
    "prompt_tokens": 30,
    "completion_tokens": 300,
    "total_tokens": 330
  }
}
```

#### Usage Example

```python
import requests

# Single request
response = requests.post(
    "http://localhost:8003/predict",
    json={
        "prompt": "Write a haiku about coding",
        "model_name": "gpt-3.5-turbo",
        "api_key": "sk-your-api-key",
        "model_provider": "openai",
        "temperature": 0.9
    }
)
print(response.json())

# Batch request
response = requests.post(
    "http://localhost:8003/predict",
    json={
        "batch_requests": [
            {"prompt": "Hello", "model_name": "gpt-3.5-turbo", "api_key": "sk-..."},
            {"prompt": "World", "model_name": "gpt-3.5-turbo", "api_key": "sk-..."}
        ]
    }
)
print(response.json())
```

#### Running Universal LLM Server

```bash
python -m src.services.model_service.api.Universal.server
```

---

### 3. ANNIF (Subject Classification)

**Port:** `8004`

**Description:** Subject/topic prediction using the [Finto AI](https://ai.finto.fi) service (ANNIF). Predicts relevant subjects for given text using Finnish vocabulary services.

**Endpoint:** `POST /predict`

#### Available Projects

| Project ID | Name | Language | Backend |
|------------|------|----------|---------|
| `yso-en` | YSO English (2025.2.Kant) | English | nn_ensemble |
| `ykl-en` | PLC English | English | ensemble |

#### Single Request Format

```json
{
  "text": "Machine learning algorithms for natural language processing",
  "project_id": "yso-en",
  "limit": 10,
  "threshold": 0.0
}
```

#### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `text` | string | Yes* | - | Single text to classify |
| `documents` | array | Yes* | - | Batch of texts to classify |
| `project_id` | string | No | `"yso-en"` | Vocabulary project to use |
| `limit` | integer | No | `10` | Maximum number of subjects to return |
| `threshold` | float | No | `0.0` | Minimum confidence threshold |

*Either `text` (single) or `documents` (batch) is required.

#### Single Response

```json
{
  "output": {
    "success": true,
    "subjects": [
      {
        "uri": "http://www.yso.fi/onto/yso/p1001",
        "label": "machine learning",
        "score": 0.92
      },
      {
        "uri": "http://www.yso.fi/onto/yso/p2002",
        "label": "natural language processing",
        "score": 0.87
      }
    ]
  }
}
```

#### Batch Request Format

```json
{
  "documents": [
    "Machine learning for image recognition",
    "Climate change impact on agriculture"
  ],
  "project_id": "yso-en",
  "limit": 5
}
```

#### Batch Response

```json
{
  "output": {
    "success": true,
    "results": [
      {
        "subjects": [
          {"uri": "...", "label": "machine learning", "score": 0.91},
          {"uri": "...", "label": "image recognition", "score": 0.85}
        ]
      },
      {
        "subjects": [
          {"uri": "...", "label": "climate change", "score": 0.93},
          {"uri": "...", "label": "agriculture", "score": 0.88}
        ]
      }
    ]
  }
}
```

#### Usage Example

```python
import requests

# Single text classification
response = requests.post(
    "http://localhost:8004/predict",
    json={
        "text": "Deep learning approaches for computer vision",
        "project_id": "yso-en",
        "limit": 5
    }
)
print(response.json())

# Batch classification
response = requests.post(
    "http://localhost:8004/predict",
    json={
        "documents": [
            "Artificial intelligence in healthcare",
            "Renewable energy sources"
        ],
        "limit": 3
    }
)
print(response.json())
```

#### Running ANNIF Server

```bash
python -m src.services.model_service.api.ANNIF.server
```

---

## MCP Integration

The backend prefers MCP (over SSE) for model inference. MCP lets a model server
expose **named tools** with declared input schemas, instead of a single opaque
`POST /predict`.

### How a model is routed to MCP vs. HTTP

`run_model_inference()` decides per model, in this order:

1. **MCP** — if the model's metadata has a non-empty `mcp_tool_name` **and** its
   `location` starts with `http://` / `https://`. The backend calls
   `mcp_tool_name` on the server at `location` via
   `MCPClientManager.call_tool()`.
2. **Universal LLM (HTTP)** — if `location == "with_api_key"` and the model is
   generative (`model_type` set). Posts to `http://universal-llm-api:8003/predict`.
3. **Legacy HTTP** — otherwise. Posts to `<location>/predict` (a `http://`
   prefix is added if missing).

The relevant model metadata fields:

| Field | Meaning |
|---|---|
| `location` | MCP/HTTP base URL (`http://host:port`), or the sentinel `with_api_key` for the Universal LLM API |
| `mcp_tool_name` | Name of the MCP tool to call (e.g. `predict_attachment`, `llm_inference`, `predict_subjects`). Empty ⇒ HTTP path |
| `model_type` | Truthy ⇒ treated as a generative model (LLM) |
| `task` / `output_context` | Used to special-case attachment (SAM) input shaping |

For tenant-scoped runs the backend also injects `s3_bucket` (the tenant's bucket)
and, for generative models, `api_key` + `model_provider` into the tool arguments.

### Calling an MCP tool (client)

The backend wraps the MCP SSE client in
[`MCPClientManager`](../../src/services/utility_service/mcp_client.py):

```python
from src.services.utility_service.mcp_client import MCPClientManager

client = MCPClientManager()
result = await client.call_tool(
    server_url="http://sam-attachment-monitor:8002",   # NO /sse suffix — added internally
    tool_name="predict_attachment",
    arguments={"s3_key": "audits/audit_1/input/file.wav", "model_type": "all"},
)
# result is a parsed dict. On failure: {"success": False, "error": "..."}
```

- The client connects to `<server_url>/sse`, initialises the session, calls the
  tool, and parses the first `TextContent` item as JSON.
- Default timeout is 60s. Connection/timeout errors are caught and returned as
  `{"success": False, "error": ...}` rather than raised.
- `list_tools(server_url)` returns the tools a server advertises — useful for
  discovery/debugging.

From synchronous code (e.g. the evaluation loop) use the bridge
`run_mcp_tool_sync(server_url, tool_name, arguments)` in `inference_engine.py`,
which runs the async call on a worker thread when an event loop is already running.

### Exposing a tool from a model server

A model server advertises tools via the MCP `list_tools` / `call_tool` handlers
and serves them over SSE. The minimal shape (mirrors the evaluation MCP server,
[`mcp_server.py`](../../src/services/performance_service/mcp_server.py)):

```python
from mcp.server import Server
from mcp.server.sse import SseServerTransport
from mcp.types import Tool, TextContent
from starlette.applications import Starlette
from starlette.routing import Route, Mount

app = Server("my-model-service")

@app.list_tools()
async def list_tools():
    return [Tool(
        name="predict_attachment",
        description="Predict attachment style from audio/text.",
        inputSchema={
            "type": "object",
            "properties": {
                "s3_key": {"type": "string"},
                "model_type": {"type": "string"},
            },
            "required": ["s3_key"],
        },
    )]

@app.call_tool()
async def call_tool(name: str, arguments: dict):
    result = run_prediction(arguments)        # your logic
    import json
    return [TextContent(type="text", text=json.dumps(result, default=str))]

# SSE transport — the backend client connects to /sse
sse = SseServerTransport("/messages/")

async def handle_sse(request):
    async with sse.connect_sse(request.scope, request.receive, request._send) as streams:
        await app.run(streams[0], streams[1], app.create_initialization_options())

starlette_app = Starlette(routes=[
    Route("/sse", endpoint=handle_sse),
    Mount("/messages/", app=sse.handle_post_message),
])
```

> **Output contract.** Tools must return a list with a single `TextContent`
> whose `text` is JSON. The backend's `merge_mcp_output()` flattens that JSON
> into the result row (dropping `raw_output`, `raw_model_output`,
> `subject_scores`), so emit flat, evaluation-ready keys
> (`y_pred`, `y_pred_proba`, `predicted_subjects`, …).

---

## ML Pipeline API (Main Backend)

The main backend provides endpoints for managing model metadata, API keys, and datasets.

**Base Path:** `/pipeline`

### API Key Management

#### Create API Key

**Endpoint:** `POST /pipeline/api-keys/`

```json
{
  "user_id": "uuid-string",
  "model_api_key": "sk-your-model-api-key",
  "costing_policy": "per-token",
  "model_metadata_id": 1
}
```

#### Update API Key

**Endpoint:** `PUT /pipeline/api-keys/{api_key_id}`

#### Delete API Key

**Endpoint:** `DELETE /pipeline/api-keys/{api_key_id}`

---

### Model Metadata Management

#### Create Model Metadata

**Endpoint:** `POST /pipeline/model-metadata/`

```json
{
  "name": "GPT-4 Production",
  "model_type": "llm",
  "location": "openai",
  "acceptable_formats": ["text"],
  "output_context": "classification",
  "task": "text-generation"
}
```

#### Get Model Metadata

**Endpoint:** `GET /pipeline/model-metadata/{model_id}`

#### List All Models

**Endpoint:** `GET /pipeline/model/`

**Query Parameters:**
- `skip` (int, default: 0): Pagination offset
- `limit` (int, default: 100): Maximum results

#### Update Model Metadata

**Endpoint:** `PUT /pipeline/model/{model_id}`

#### Delete Model

**Endpoint:** `DELETE /pipeline/model/{model_id}`

---

### Dataset Metadata Management

#### Create Dataset with Input/Output

**Endpoint:** `POST /pipeline/dataset/metadata/`

```json
{
  "purpose": "training",
  "copyright_agreement": true,
  "input_metadata": {
    "headers": {"col1": "string", "col2": "float"},
    "benchmark_dataset": false,
    "datatypes": {"col1": "text", "col2": "numeric"},
    "location": "storage/datasets/input/"
  },
  "output_metadata": {
    "headers": {"prediction": "string"},
    "benchmark_dataset": false,
    "datatypes": {"prediction": "label"},
    "location": "storage/datasets/output/"
  }
}
```

#### Get Complete Dataset

**Endpoint:** `GET /pipeline/dataset/metadata/{dataset_id}`

#### Get Input Dataset

**Endpoint:** `GET /pipeline/dataset/input/{input_id}`

#### Get Output Dataset

**Endpoint:** `GET /pipeline/dataset/output/{output_id}`

#### Update Dataset

**Endpoint:** `PUT /pipeline/dataset/metadata/{dataset_id}`

#### Update Full Dataset (with Input/Output)

**Endpoint:** `PUT /pipeline/dataset/metadata/{dataset_id}/all`

#### Delete Dataset

**Endpoint:** `DELETE /pipeline/dataset/metadata/{dataset_id}`

*Note: This cascades and deletes associated input/output metadata.*

#### Delete Input Dataset

**Endpoint:** `DELETE /pipeline/dataset/metadata/input/{input_id}`

#### Delete Output Dataset

**Endpoint:** `DELETE /pipeline/dataset/metadata/output/{output_id}`

---

## Running All Services

The model servers and the evaluation MCP server run **outside** Docker Compose —
start the ones you need in separate terminals alongside the backend.

```bash
# Terminal 1: Main API
#   single-tenant:
uvicorn src.api.main:app --host 0.0.0.0 --port 8000
#   multi-tenant (uses the multi-tenant DB/env — see the setup guide):
ENV_FILE=deploy/.env.multi-tenant uvicorn src.api.main:app --host 0.0.0.0 --port 8001

# Terminal 2: SAM model server (port 8002)
python -m src.services.model_service.api.SAM.server

# Terminal 3: Universal LLM (port 8003)
python -m src.services.model_service.api.Universal.server

# Terminal 4: ANNIF (port 8004)
python -m src.services.model_service.api.ANNIF.server

# Terminal 5: Evaluation MCP server (port 8005) — needed for MCP-based metric runs
python -m src.services.performance_service.mcp_server
```

A model's `location` field must point at wherever its server is actually
reachable from the backend:

- **All on the host:** `http://localhost:8002` (SAM), `http://localhost:8004`
  (ANNIF), etc.
- **Backend in Docker, servers on host:** `http://host.docker.internal:8002`.
- **Everything in Docker (separate compose/network):** the service hostname,
  e.g. `http://sam-attachment-monitor:8002`.

---

## Adding New Models

The model service uses [LitServe](https://github.com/Lightning-AI/LitServe) to create standalone inference servers. To add a new model:

### Step 1: Create Model Directory Structure

```
src/services/model_service/
├── api/
│   └── YourModel/
│       └── server.py          # LitServe API server
└── models/
    └── YourModel/
        ├── __init__.py        # Export your predictor class
        ├── your_predictor.py  # Model loading & inference logic
        └── weights/           # Model weights (optional)
```

### Step 2: Create the Predictor Class

```python
# src/services/model_service/models/YourModel/your_predictor.py

class YourModelPredictor:
    def __init__(self):
        self.model = None

    def load_model(self):
        """Load your model weights/configuration"""
        # Load from HuggingFace, local weights, or API
        self.model = ...

    def predict(self, input_data) -> dict:
        """Run inference and return results"""
        result = self.model(input_data)
        return {
            "success": True,
            "prediction": result,
            "confidence": 0.95
        }
```

### Step 3: Create the LitServe API Server

```python
# src/services/model_service/api/YourModel/server.py

import litserve as ls
from starlette.middleware.cors import CORSMiddleware

class YourModelAPI(ls.LitAPI):
    def setup(self, device):
        """Load model on startup"""
        from src.services.model_service.models.YourModel import YourModelPredictor
        self.model = YourModelPredictor()
        self.model.load_model()

    def decode_request(self, request):
        """Parse incoming request"""
        return request.get("input_data"), request.get("options", {})

    def predict(self, inputs):
        """Run inference"""
        input_data, options = inputs
        return self.model.predict(input_data)

    def encode_response(self, output):
        """Format response"""
        return {"output": output}

def run_your_model_api(port=8005):
    api = YourModelAPI()
    cors_middleware = (
        CORSMiddleware,
        {
            "allow_origins": ["*"],
            "allow_methods": ["GET", "POST"],
            "allow_headers": ["*"],
        }
    )
    server = ls.LitServer(
        api,
        middlewares=[cors_middleware],
        workers_per_device=1
    )
    server.run(port=port, generate_client_file=False)

if __name__ == "__main__":
    run_your_model_api()
```

### Step 4: Run Your Model Server

```bash
python -m src.services.model_service.api.YourModel.server
```

### Key LitServe Methods

| Method | Purpose |
|--------|---------|
| `setup(device)` | Load models, called once on startup |
| `decode_request(request)` | Parse JSON request into model inputs |
| `predict(inputs)` | Run inference, return results |
| `encode_response(output)` | Format output as JSON response |

---

## Evaluation Metrics (run_functions.py)

The performance service provides a comprehensive set of evaluation metrics through `METRICS_REGISTRY`. These are used to evaluate model outputs against ground truth.

### Using Metrics

```python
from src.services.performance_service.run_functions import evaluate_function, get_metric_function

# Evaluate a metric
result = evaluate_function(
    "accuracy",
    y_true=[1, 0, 1, 1, 0],
    y_pred=[1, 0, 0, 1, 0]
)
```

### Available Metrics

#### Classification Metrics

| Metric Name | Aliases | Description |
|-------------|---------|-------------|
| `accuracy` | `confusion_matrix_analysis` | Overall accuracy with confusion matrix |
| `confusion_matrix` | - | Raw confusion matrix |
| `precision` | - | Precision score |
| `recall` | - | Recall/sensitivity score |
| `f1` | `f1_score` | F1 score (harmonic mean of precision & recall) |
| `fbeta` | - | F-beta score with custom beta |
| `roc_auc` | - | ROC Area Under Curve |
| `pr_auc` | `average_precision` | Precision-Recall AUC |
| `balanced_accuracy` | - | Balanced accuracy for imbalanced data |
| `mcc` | `matthews_correlation` | Matthews Correlation Coefficient |
| `cohen_kappa` | - | Cohen's Kappa score |
| `log_loss` | `cross_entropy` | Logarithmic loss |
| `brier_score` | - | Brier score for probabilistic predictions |
| `hamming_loss` | - | Hamming loss for multi-label |
| `jaccard` | `iou` | Jaccard index / IoU |
| `specificity` | - | True negative rate |
| `classification_report` | - | Full sklearn classification report |

#### Fairness Metrics

| Metric Name | Aliases | Description |
|-------------|---------|-------------|
| `equalized_odds` | - | Equalized odds across groups |
| `equal_opportunity` | - | Equal opportunity metric |
| `demographic_parity` | - | Demographic parity with details |
| `statistical_parity` | - | Statistical parity analysis |
| `disparate_impact` | - | Disparate impact ratio |
| `calibration` | - | Calibration across groups |

#### Regression Metrics

| Metric Name | Aliases | Description |
|-------------|---------|-------------|
| `mse` | `mean_squared_error` | Mean Squared Error |
| `rmse` | `root_mean_squared_error` | Root Mean Squared Error |
| `mae` | `mean_absolute_error` | Mean Absolute Error |
| `mape` | `mean_absolute_percentage_error` | Mean Absolute Percentage Error |
| `r2` | `r_squared` | R-squared coefficient |
| `explained_variance` | - | Explained variance score |
| `max_error` | - | Maximum prediction error |
| `median_absolute_error` | - | Median absolute error |

#### Ranking Metrics

| Metric Name | Aliases | Description |
|-------------|---------|-------------|
| `ndcg` | `normalized_dcg` | Normalized Discounted Cumulative Gain |
| `top_k_accuracy` | - | Top-K accuracy for ranking |

#### Calibration Metrics

| Metric Name | Aliases | Description |
|-------------|---------|-------------|
| `ece` | `expected_calibration_error` | Expected Calibration Error |

#### Generative AI Metrics

| Metric Name | Aliases | Description |
|-------------|---------|-------------|
| `bleu` | - | BLEU score for text generation |
| `rouge` | - | ROUGE score for summarization |
| `perplexity` | - | Perplexity for language models |

#### Keyword/Text Metrics

| Metric Name | Description |
|-------------|-------------|
| `keyword_accuracy` | Single document keyword matching |
| `batch_keyword_accuracy` | Batch keyword accuracy (for ANNIF) |

#### Summary Metrics

| Metric Name | Aliases | Description |
|-------------|---------|-------------|
| `performance_summary` | `classification_summary` | Comprehensive classification summary |
| `regression_summary` | - | Comprehensive regression summary |

### Adding Custom Metrics

To add a new metric:

1. Create a function in the appropriate file under `src/services/performance_service/functions/`
2. Register it in `__init__.py`:

```python
# In src/services/performance_service/functions/__init__.py

from src.services.performance_service.functions.your_metrics import your_custom_metric

METRICS_REGISTRY = {
    # ... existing metrics ...
    'your_metric': your_custom_metric,
    'your_metric_alias': your_custom_metric,  # optional alias
}
```

3. Your metric function signature:

```python
def your_custom_metric(y_true, y_pred, **kwargs) -> dict:
    """
    Calculate your custom metric.

    Args:
        y_true: Ground truth values
        y_pred: Predicted values
        **kwargs: Additional parameters

    Returns:
        Dictionary with metric results
    """
    # Calculate metric
    score = ...

    return {
        "metric_name": "your_metric",
        "score": score,
        "details": {...}
    }
```

---

## Error Handling

All model services return consistent error responses:

```json
{
  "success": false,
  "output": null,
  "error": "Error description here",
  "model_name": "model-name",
  "model_provider": "provider"
}
```

Common error scenarios:
- **Missing required parameters**: Returns validation error
- **Invalid model name**: Returns list of available models
- **API key issues**: Returns authentication error from provider
- **Model not found**: Returns 404 for metadata endpoints
