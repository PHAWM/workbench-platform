# PHAWM Workbench Backend

Backend API for the Participatory Harm Auditing Workbenches and Methodologies (PHAWM) project. A workbench for performing event assessments when AI systems are deployed.

## Tech Stack

- **Framework**: FastAPI
- **Database**: PostgreSQL with SQLModel ORM
- **Migrations**: Alembic
- **Authentication**: JWT

## Getting Started

### Prerequisites

- Python 3.11+
- PostgreSQL
- Docker (optional, for local database)

### Installation

1. Clone the repository
2. Create a virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Copy `.env.example` to `.env` and configure your environment variables

### Running Locally

Start the development server:
```bash
uvicorn src.main:app --reload
```

### Database Setup

Use Docker Compose to spin up a local PostgreSQL instance:
```bash
cd deploy
docker-compose up -d
```

Run migrations:
```bash
alembic upgrade head
```

## Project Structure

```
src/
├── api/
│   └── routes/      # API endpoints
├── core/            # Configuration and settings
├── models/          # Database models
├── services/        # Business logic
└── utils/           # Helper functions
```

## API Documentation

Once running, access the interactive API docs at:
- Swagger UI: `http://localhost:8000/api/v1/docs`
- ReDoc: `http://localhost:8000/api/v1/redoc`

For detailed API documentation, see the [docs/](docs/) folder.

## Environment Variables

```
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
SMTP_TLS=True
EMAILS_FROM_EMAIL=noreply@phawm.org
EMAILS_FROM_NAME=PHAWM Workbench
FRONTEND_URL=http://localhost:3000
```

## License

This tool is provided under the [CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/legalcode.en) licence.
