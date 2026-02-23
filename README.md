# PHAWM Workbench Platform

A workbench for performing event assessments when AI systems are deployed. Part of the Participatory Harm Auditing Workbenches and Methodologies (PHAWM) project.

## Project Structure

```
workbench-platform/
├── backend/     # FastAPI backend server
├── frontend/    # React web application
├── deploy/      # Docker deployment configuration
└── docs/        # Documentation
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
pip install -r requirements.txt
uvicorn src.main:app --reload
```

---

### [frontend/](frontend/)

React-based web application for AI auditing and performance analysis.

| | |
|---|---|
| **Tech Stack** | React 19, Vite, Tailwind CSS, D3.js, Recharts, Radix UI |
| **Node.js** | 18+ |
| **Port** | 3000 |

Set it up using the following commands:

```bash
cd frontend
npm install --force
npm start
```

---

### [deploy/](deploy/)

Docker Compose configuration for deploying the full platform stack.

| Service | Port | Description |
|---------|------|-------------|
| `app` | 3000 | Frontend application |
| `api` | 8080 | Backend API |
| `postgres` | 5432 | PostgreSQL database |
| `docs` | 8001 | Documentation server |
| `sam-api` | internal | SAM ML service |
| `universal-llm-api` | internal | LLM inference service |
| `annif-api` | internal | Subject indexing service |


Set it up using the following commands:

```bash
cd deploy
cp .env.example .env  # Configure credentials
docker-compose up -d
```

---

### [docs/](docs/)

MkDocs Material documentation site covering both frontend and backend usage.

| | |
|---|---|
| **Framework** | MkDocs with Material theme |
| **Port** | 8001 (via docker) / 8080 (local) |

Set it up using the following commands

```bash
cd docs
mkdocs serve
```

## Quick Start

1. **Clone the repository**
   ```bash
   git clone https://github.com/PHAWM/workbench-platform.git
   cd workbench-platform
   ```

2. **Start with Docker** (recommended)
   ```bash
   cd deploy
   cp .env.example .env  # Edit with your credentials
   docker-compose up -d
   ```

3. **Access the application**
   - Frontend: http://localhost:3000
   - API Docs: http://localhost:8080/docs
   - Documentation: http://localhost:8001

## License

This project is provided under the [CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/legalcode.en) license.
