FROM python:3.12-slim

WORKDIR /app

# Install dependencies
RUN pip install --no-cache-dir \
    "mcp[cli]>=1.9.0" \
    fastapi==0.116.1 \
    starlette==0.41.3 \
    uvicorn==0.35.0 \
    pydantic==2.11.7 \
    requests==2.32.3 \
    beautifulsoup4

# Copy project files
COPY . /app

ENV PYTHONPATH=/app

WORKDIR /app/src/services/model_service/api/ANNIF

CMD ["uvicorn", "server:starlette_app", "--host", "0.0.0.0", "--port", "8004"]
