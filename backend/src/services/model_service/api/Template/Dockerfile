FROM python:3.12-slim

WORKDIR /app

# Install build dependencies (add more if your model needs them)
RUN apt-get update && apt-get install -y \
    build-essential \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy the entire project for src imports
COPY . /app

# Install requirements
COPY src/services/model_service/api/Template/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

ENV PYTHONPATH=/app

WORKDIR /app/src/services/model_service/api/Template
CMD ["uvicorn", "server:starlette_app", "--host", "0.0.0.0", "--port", "8010"]
