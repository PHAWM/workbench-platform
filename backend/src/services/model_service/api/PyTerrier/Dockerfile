FROM python:3.10-slim

WORKDIR /app

# PyTerrier requires Java
RUN apt-get update && apt-get install -y --no-install-recommends \
    default-jdk-headless \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
RUN pip install --no-cache-dir \
    "mcp[cli]>=1.9.0" \
    starlette==0.46.2 \
    uvicorn==0.34.3 \
    python-terrier==0.10.0 \
    pandas \
    boto3>=1.35.0 \
    httpx==0.28.1

# Copy project files
COPY . /app

ENV PYTHONPATH=/app
# Persist PyTerrier JVM downloads inside the image layer
ENV JAVA_HOME=/usr/lib/jvm/default-java
# Index storage directory (override with a volume mount for persistence)
ENV PYTERRIER_INDEX_DIR=/data/indexes

# Create index directory
RUN mkdir -p /data/indexes

WORKDIR /app/src/services/model_service/api/PyTerrier

CMD ["uvicorn", "server:starlette_app", "--host", "0.0.0.0", "--port", "8006"]
