# Model Service APIs Deployment

This directory contains two small servers for the model service:

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

## Stopping Services

```bash
docker-compose down
```

## Troubleshooting

- Check container logs: `docker-compose logs [service-name]`
- Restart specific service: `docker-compose restart [service-name]`
- Rebuild containers: `docker-compose up --build`