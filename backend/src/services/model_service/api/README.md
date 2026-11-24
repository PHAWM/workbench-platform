# Model Service APIs Deployment

This directory contains the model service APIs and a template for adding custom models.

## Services

### 1. SAM (School Attachment Monitor) API
- **Port**: 8002
- **Purpose**: Attachment style prediction using audio files
- **Endpoints**:
  - `POST /predict` - Predict attachment style from audio files
- **Models**: Audio, Text, Multimodal MC1, Multimodal MC2

### 2. Universal LLM Inference API
- **Port**: 8003
- **Purpose**: Unified interface for various LLM providers
- **Endpoints**:
  - `POST /predict` - Single or batch LLM inference
- **Supported Providers**: OpenAI, Anthropic, Google Gemini, Groq

### 3. ANNIF (Subject Indexing) API
- **Port**: 8004
- **Purpose**: Automated subject indexing using Annif
- **Endpoints**:
  - `POST /predict` - Classify text into subject categories

## Quick Start

1. **Deploy both services**:
   ```bash
   docker-compose up -d
   ```

2. **Check service status**:
   ```bash
   docker-compose ps
   ```

3. **View logs**:
   ```bash
   docker-compose logs -f sam-api
   docker-compose logs -f universal-llm-api
   ```

## Service URLs

- SAM API: http://localhost:8002
- Universal LLM API: http://localhost:8003

## Usage Examples

### SAM API
```bash
curl -X POST http://localhost:8002/predict \
  -H "Content-Type: application/json" \
  -d '{
    "file_location": {"audit_id": "123", "file_name": "audio.wav"},
    "model_type": "all"
  }'
```

### Universal LLM API (Single Request)
```bash
curl -X POST http://localhost:8003/predict \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Hello, how are you?",
    "model_name": "gpt-3.5-turbo",
    "api_key": "your-openai-key",
    "model_provider": "openai"
  }'
```

### Universal LLM API (Batch Request)
```bash
curl -X POST http://localhost:8003/predict \
  -H "Content-Type: application/json" \
  -d '{
    "batch_requests": [
      {
        "prompt": "Hello",
        "model_name": "gpt-3.5-turbo",
        "api_key": "your-openai-key",
        "model_provider": "openai"
      },
      {
        "prompt": "How are you?",
        "model_name": "claude-3-haiku-20240307",
        "api_key": "your-anthropic-key",
        "model_provider": "anthropic"
      }
    ]
  }'
```

## Adding a Custom Model

Use the `Template/` directory to add your own model to the workbench.

### Steps

1. **Copy the template**:
   ```bash
   cp -r Template/ YourModelName/
   ```

2. **Edit `YourModelName/server.py`**:
   - Load your model in `setup()`
   - Parse your input in `decode_request()`
   - Run inference in `predict()` — return `{"success": True, "output": <prediction>}`
   - Set `PORT` to an unused port (SAM=8002, Universal=8003, ANNIF=8004)

3. **Edit `YourModelName/requirements.txt`**:
   - Add your model's Python dependencies

4. **Edit `YourModelName/Dockerfile`** (if needed):
   - Add system packages your model requires (e.g., `libsndfile1` for audio)

5. **Add to `docker-compose.yml`**:
   ```yaml
   your-model-api:
     build:
       context: ../../../../
       dockerfile: src/services/model_service/api/YourModelName/Dockerfile
     container_name: your-model-name
     environment:
       - PYTHONPATH=/app
     restart: unless-stopped
     networks:
       - backend-network
   ```

6. **Register in the database**:
   Create a `Modelmetadata` entry with:
   - `location`: `http://your-model-api:PORT` (Docker service name + port)
   - `model_type`: `0` for Predictive AI, `1` for Generative AI
   - `acceptable_formats`: file types your model accepts (e.g., `["csv", "json"]`)

7. **Deploy**:
   ```bash
   docker-compose up -d your-model-api
   ```

### Key Requirement
Your model must expose a `POST /predict` endpoint that accepts JSON and returns JSON with at least `{"success": true, "output": <result>}`. This is what `run_model_inference()` in the workbench calls.

## Stopping Services

```bash
docker-compose down
```

## Troubleshooting

- Check container logs: `docker-compose logs [service-name]`
- Restart specific service: `docker-compose restart [service-name]`
- Rebuild containers: `docker-compose up --build`