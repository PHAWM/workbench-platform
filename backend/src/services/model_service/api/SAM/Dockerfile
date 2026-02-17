FROM python:3.12-slim

WORKDIR /app

# Install build dependencies for packages that require compilation and ffmpeg for audio processing
RUN apt-get update && apt-get install -y \
    build-essential \
    gcc \
    g++ \
    curl \
    ffmpeg \
    libavformat-dev \
    libavcodec-dev \
    libavdevice-dev \
    libavutil-dev \
    libswscale-dev \
    libswresample-dev \
    libavfilter-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Copy the entire project to get access to src imports
COPY . /app

# Install SAM-specific requirements
COPY src/services/model_service/api/SAM/requirements-sam.txt /app/requirements-sam.txt
RUN pip install --no-cache-dir -r requirements-sam.txt

# Set Python path to include the project root
ENV PYTHONPATH=/app

# Change to the SAM directory and run the server
WORKDIR /app/src/services/model_service/api/SAM
CMD ["python", "server.py"]

