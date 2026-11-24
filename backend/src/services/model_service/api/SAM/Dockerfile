FROM --platform=$BUILDPLATFORM python:3.12-slim

WORKDIR /app

# Fix pkg-config: Install COMPLETE FFmpeg dev packages
RUN apt-get update && apt-get install -y \
    build-essential \
    pkg-config \
    python3-dev \
    cython3 \
    ffmpeg \
    libavformat-dev \
    libavcodec-dev \
    libavdevice-dev \
    libavutil-dev \
    libswscale-dev \
    libswresample-dev \
    libavfilter-dev \
    && rm -rf /var/lib/apt/lists/*

COPY . /app
COPY src/services/model_service/api/SAM/requirements-sam.txt /app/requirements-sam.txt
RUN pip install --no-cache-dir -r /app/requirements-sam.txt

ENV PYTHONPATH=/app
WORKDIR /app/src/services/model_service/api/SAM
CMD ["uvicorn", "server:starlette_app", "--host", "0.0.0.0", "--port", "8002"]




