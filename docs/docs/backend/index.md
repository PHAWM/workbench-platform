# Backend Architecture Overview

The PHAWM Workbench backend is built with **FastAPI** and follows a layered architecture pattern separating concerns between API routes, services, and data models.

## Project Structure

```
src/
├── api/
│   ├── main.py          # Router aggregation
│   ├── deps.py          # Dependency injection
│   └── routes/          # API endpoints
│       ├── login.py
│       ├── users.py
│       ├── application.py
│       ├── events.py
│       ├── metrics.py
│       ├── evaluation.py
│       ├── entities.py
│       └── upload.py
├── core/
│   ├── config.py        # Application settings
│   ├── security.py      # JWT authentication
│   └── enums.py         # Shared enumerations
├── models/
│   ├── users.py         # User models
│   ├── events.py        # Event definitions
│   ├── metrics.py       # Metric definitions
│   ├── audit_setup.py   # Audit configuration
│   └── audit_pipeline.py
├── services/
│   ├── user_service.py
│   ├── email_service.py
│   ├── audit_service/
│   ├── model_service/
│   ├── performance_service/
│   └── utility_service/
└── utils/               # Helper functions
```

## Layer Responsibilities

### API Layer (`api/routes/`)

Handles HTTP requests and responses. Each route module corresponds to a domain:

| Route | Purpose |
|-------|---------|
| `login` | Authentication (JWT tokens) |
| `users` | User management |
| `application` | AI application setup |
| `events` | Event CRUD operations |
| `metrics` | Metric definitions |
| `evaluation` | Audit assessments |
| `entities` | Impacted entities |
| `upload` | File uploads |

### Service Layer (`services/`)

Contains business logic separated from HTTP concerns:

- **audit_service** - Audit workflow management
- **model_service** - ML model integration
- **performance_service** - Metric evaluation
- **user_service** - User operations
- **email_service** - Email notifications
- **utility_service** - Shared utilities

### Data Layer (`models/`)

SQLModel-based database models representing the domain:

- **Users** - Auditors and audit instigators
- **Events** - Potential harms/benefits with likelihood and magnitude
- **Metrics** - Measurable criteria for events
- **Audit Setup** - Application and audit configuration

### Core (`core/`)

Cross-cutting concerns:

- **config.py** - Environment-based settings via Pydantic
- **security.py** - JWT token generation and validation
- **enums.py** - Shared enumeration types

## Database

PostgreSQL with SQLModel ORM. Migrations managed via Alembic.

## Authentication

JWT-based authentication with access and refresh tokens. Token expiration configurable via environment variables.
