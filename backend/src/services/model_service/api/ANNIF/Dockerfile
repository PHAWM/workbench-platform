FROM python:3.12-slim

WORKDIR /app

# Install dependencies
RUN pip install --no-cache-dir \
    litserve==0.2.15 \
    fastapi==0.116.1 \
    starlette==0.47.3 \
    uvicorn==0.35.0 \
    pydantic==2.11.7 \
    requests==2.32.3 \
    beautifulsoup4

# Copy project files
COPY . /app

ENV PYTHONPATH=/app

WORKDIR /app/src/services/model_service/api/ANNIF

CMD ["python", "server.py"]
