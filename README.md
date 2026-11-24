# PHAWM Workbench Platform

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.23880458.svg)](https://doi.org/10.5281/zenodo.23880458)

A workbench for performing event assessments when AI systems are deployed. Part of
the Participatory Harm Auditing Workbenches and Methodologies (PHAWM) project.

The platform is **multi-tenant**: one Postgres database holds a `public` schema for
platform records (the tenant registry) plus one schema per tenant, and each tenant
gets its own frontend build because the tenant id is compiled into the bundle at
build time.

## Project Structure

```
workbench-platform-internal/
├── backend/     # FastAPI backend server (submodule)
├── frontend/    # React web application (submodule)
├── deploy/      # Docker Compose stack behind a Caddy reverse proxy
└── docs/        # MkDocs Material documentation site
```

`backend/` and `frontend/` are git submodules, both tracking their `multi-tenant`
branch. Check them out before doing anything else:

```bash
git submodule update --init --recursive
```

## Folder Summaries

### [backend/](backend/)

FastAPI-based REST API server providing the core platform functionality.

| | |
|---|---|
| **Tech Stack** | FastAPI, PostgreSQL, SQLModel, Alembic, JWT auth |
| **Python** | 3.11+ |
| **Port** | 8000 (dev) / 8080 (docker) |

Set it up using the following commands:

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn src.main:app --reload
```

---

### [frontend/](frontend/)

React-based web application for AI auditing and performance analysis.

| | |
|---|---|
| **Tech Stack** | React 19, Vite 7, Tailwind CSS, D3.js, Recharts, Radix UI |
| **Node.js** | 24.3.0 (see `.tool-versions`) |
| **Port** | 5173 (Vite dev) / 3000 (docker) |

Set it up using the following commands:

```bash
cd frontend
npm install --force
npm start          # vite dev server
```

The build needs `VITE_TENANT_ID` and `VITE_API_URL`; `deploy/.env.example`
documents both.

---

### [deploy/](deploy/)

Docker Compose configuration for deploying the full platform stack. See
[deploy/README.md](deploy/README.md) for the full deployment guide.

| Service | Published port | Description |
|---------|----------------|-------------|
| `caddy` | 80, 443 | Reverse proxy and TLS termination |
| `api` | 8080 | Backend API |
| `postgres-mt` | 5433 | PostgreSQL database (5432 in-container) |
| `rustfs-mt` | 9002, 9003 | S3-compatible object storage + console |
| `docs` | 8001 | Documentation server |
| `sam-api` | 8002 | SAM ML service |
| `universal-llm-api` | 8003 | LLM inference service |
| `annif-api` | 8004 | Subject indexing service |
| `pyterrier-rag-api` | 8006 | PyTerrier RAG service |
| `phawm-sam-frontend` | 3001 | Frontend build for the `phawm_sam` tenant |
| `phawm-annif-frontend` | 3003 | Frontend build for the `phawm_annif` tenant |
| `demo-frontend` | 3004 | Frontend build for the `demo` tenant |

Set it up using the following commands:

```bash
cd deploy
cp .env.example .env   # Configure credentials
docker compose up -d
```

Caddy routes `/api/*` to the API, `/workbench/docs/*` to the docs site, and
`/workbench/<tenant>*` to that tenant's frontend. Set your own hostname in
[deploy/caddy/Caddyfile](deploy/caddy/Caddyfile), which ships with a `<domain>`
placeholder.

---

### [docs/](docs/)

MkDocs Material documentation site covering both frontend and backend usage.

| | |
|---|---|
| **Framework** | MkDocs with Material theme |
| **Port** | 8080 (local `mkdocs serve`) / 8001 (via docker) |

Set it up using the following commands:

```bash
cd docs
mkdocs serve
```

## Quick Start

1. **Clone the repository with its submodules**
   ```bash
   git clone --recurse-submodules https://github.com/PHAWM/workbench-platform-internal.git
   cd workbench-platform-internal
   ```

2. **Start with Docker** (recommended)
   ```bash
   cd deploy
   cp .env.example .env   # Edit with your credentials
   docker compose up -d
   ```

3. **Access the application**
   - Tenant frontends: http://localhost:3001 (`phawm_sam`), http://localhost:3003 (`phawm_annif`), http://localhost:3004 (`demo`)
   - API docs: http://localhost:8080/docs
   - Documentation: http://localhost:8001

   Behind Caddy with a configured domain these are served as `/workbench/<tenant>`,
   `/api/*` and `/workbench/docs/`.

## License

This project is provided under the [CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/legalcode.en) license.
