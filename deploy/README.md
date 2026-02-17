# Deployment

This folder contains Docker configuration files to deploy the entire workbench platform stack.

## Services Overview

The `docker-compose.yml` defines the following services:

| Service | Port | Description |
|---------|------|-------------|
| `app` | 3000 | Frontend Next.js application |
| `api` | 8080 | Backend FastAPI server |
| `postgres` | 5432 | PostgreSQL 15 database |
| `docs` | 8001 | MkDocs documentation server |
| `sam-api` | internal | SAM (Attachment Monitor) ML service |
| `universal-llm-api` | internal | Universal LLM inference service |
| `annif-api` | internal | ANNIF subject indexing service |
| `prestart` | - | One-time database migration runner |

## Requirements

- Docker and Docker Compose
- Sufficient resources for ML model services

## Quick Start

1. **Configure environment variables**

   Copy the example below into a `.env` file in this directory:

   ```env
   POSTGRES_USER=postgres
   POSTGRES_PASSWORD=your_secure_password
   POSTGRES_DB=phawmdb
   POSTGRES_HOST=postgres
   POSTGRES_PORT=5432
   ```

2. **Start all services**

   ```bash
   cd deploy
   docker-compose up -d
   ```

3. **Verify services are running**

   ```bash
   docker ps
   ```

4. **Access the applications**

   - Frontend: http://localhost:3000
   - API: http://localhost:8080
   - API Docs: http://localhost:8080/docs
   - Documentation: http://localhost:8001

## Folder Structure

```
deploy/
├── .env                    # Environment variables (not committed)
├── Dockerfile              # Backend API Dockerfile
├── docker-compose.yml      # Main orchestration file
├── README.md
└── db/
    ├── init.sql            # Initial database schema
    ├── data-sources.json   # CloudBeaver connection config
    └── .cloudbeaver.runtime.conf
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `POSTGRES_USER` | Database username | - |
| `POSTGRES_PASSWORD` | Database password | - |
| `POSTGRES_DB` | Database name | `phawmdb` |
| `POSTGRES_HOST` | Database host | `postgres` |
| `POSTGRES_PORT` | Database port | `5432` |

> **Note:** The `.gitignore` excludes `.env` files. Never commit credentials to the repository.

## Common Commands

```bash
# Start all services
docker-compose up -d

# Stop all services
docker-compose down

# View logs
docker-compose logs -f

# View logs for a specific service
docker-compose logs -f api

# Rebuild and restart a service
docker-compose up -d --build api

# Remove all containers and volumes
docker-compose down -v
```

## Network

All services communicate over the `platform-network` Docker network. Internal ML services (SAM, Universal LLM, ANNIF) are not exposed externally and can only be accessed by other services on this network.