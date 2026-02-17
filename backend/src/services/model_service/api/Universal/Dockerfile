FROM python:3.12-slim

WORKDIR /app

# Install build dependencies for packages that require compilation
RUN apt-get update && apt-get install -y \
    build-essential \
    gcc \
    g++ \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy the entire project to get access to src imports
COPY . /app

# Install Universal-specific requirements
COPY src/services/model_service/api/Universal/requirements-uni.txt /app/requirements-uni.txt
RUN pip install --no-cache-dir -r requirements-uni.txt

# Set Python path to include the project root
ENV PYTHONPATH=/app

# Change to the Universal directory and run the server
WORKDIR /app/src/services/model_service/api/Universal
CMD ["python", "server.py"]

