# Multi-Tenant Deployment

Deployment reference for the multi-tenant stack: bringing it up, creating
tenants, running migrations, and connecting to the database.

The deployment lives in the **platform repository**, which pulls the backend and
frontend in as submodules:

```
workbench-platform-internal/
├── deploy/                  ← the deployment (compose, Caddy, Dockerfile)
│   ├── docker-compose.yml
│   ├── caddy/Caddyfile
│   └── .env                 ← you create this
├── backend/                 ← submodule, branch: multi-tenant
├── frontend/                ← submodule, branch: multi-tenant
└── docs/                    ← this documentation
```

`deploy/docker-compose.yml` is the deployment stack. It brings up the API,
database, object storage, the model servers, one frontend per tenant, the docs
site, and a Caddy reverse proxy in front of everything.

> The backend repository also contains `backend/deploy/docker-compose.yml` and
> `backend/deploy/docker-compose.multi-tenant.yml`. Those are backend-only
> stacks kept for local backend development. **Deployments use
> `deploy/docker-compose.yml` in the platform repository** — this guide covers
> that one.

---

## Prerequisites

- Docker and Docker Compose
- Submodules checked out:

```bash
git submodule update --init --recursive
```

---

## Configuration

Compose reads `deploy/.env` automatically — no `--env-file` flag is needed.
Copy the example and edit it:

```bash
cp deploy/.env.example deploy/.env
```

```ini
# --- Database ---
POSTGRES_USER=postgres
POSTGRES_PASSWORD=change-me
POSTGRES_DB=phawmdb_mt
POSTGRES_HOST=postgres-db-mt
POSTGRES_PORT=5432

# --- Email (Resend) ---
RESEND_API_KEY=

# --- Object storage ---
STORAGE_BACKEND=s3
S3_ENDPOINT_URL=http://rustfs-mt:9000
S3_ACCESS_KEY=admin
S3_SECRET_KEY=change-me
S3_BUCKET_NAME=workbench
S3_REGION=us-east-1

# --- URLs ---
FRONTEND_URL=https://example.org
VITE_API_URL=https://example.org/api
VITE_DOCS_URL=https://example.org/workbench/docs
```

| Variable | Description |
|---|---|
| `POSTGRES_USER` / `POSTGRES_PASSWORD` | Database credentials |
| `POSTGRES_DB` | Database name; created on first start if absent |
| `POSTGRES_HOST` | Must be `postgres-db-mt`, the container name |
| `RESEND_API_KEY` | Email delivery for invitations and password resets |
| `FRONTEND_URL` | Base URL used in emailed links |
| `VITE_API_URL` | Externally reachable API base URL, baked into each frontend build. No `/api/v1` suffix. |
| `VITE_DOCS_URL` | Where the docs site is served, used by in-app docs links |
| `STORAGE_BACKEND` | `s3` for this stack (`local` writes to the container filesystem) |
| `S3_ACCESS_KEY` / `S3_SECRET_KEY` | Also become the RustFS root credentials |

> **JWT secrets are not wired through this compose file.** `JWT_SECRET_KEY` and
> `JWT_REFRESH_SECRET_KEY` are absent from the `api` service's `environment:`
> block, so the backend falls back to `secrets.token_urlsafe(32)` at startup.
> Every API restart therefore invalidates all issued tokens. To keep sessions
> across restarts, add both variables to `.env` **and** to the `api` service.

> `IS_DEMO` in the backend settings is dead configuration — nothing in `src/`
> reads it. Only the frontend's `VITE_IS_DEMO` has any effect.

### Set the domain

[`deploy/caddy/Caddyfile`](https://github.com/PHAWM/workbench-platform-internal/blob/main/deploy/caddy/Caddyfile)
begins with a literal `<domain>` placeholder. Replace it with your hostname, or
with `:80` for local testing without TLS, before starting the stack — Caddy will
not load an unedited config.

```caddyfile
example.org {
  handle /api/* {
    reverse_proxy api:8080
  }

  handle_path /workbench/phawm_sam* {
    reverse_proxy phawm-sam-frontend:3000
  }
  ...
}
```

---

## Starting the Stack

```bash
cd deploy
docker compose up -d --build
```

| Service | Container | Host port | Purpose |
|---|---|---|---|
| `caddy` | `caddy` | `80`, `443` | Reverse proxy, automatic TLS |
| `api` | — | `8080` | FastAPI backend |
| `postgres-mt` | `postgres-db-mt` | `5433` → 5432 | PostgreSQL, all tenant schemas |
| `rustfs-mt` | `rustfs-mt` | `9002` → 9000, `9003` → 9001 | Object storage + console |
| `prestart` | `prestart-mt` | — | One-shot DB setup, then exits |
| `docs` | — | `8001` → 8000 | MkDocs site |
| `sam-api` | `sam-attachment-monitor` | `8002` | SAM model server |
| `universal-llm-api` | `universal-llm-inference` | `8003` | Universal LLM server |
| `annif-api` | `annif-subject-indexing` | `8004` | ANNIF subject indexing |
| `pyterrier-rag-api` | `pyterrier-rag` | `8006` | PyTerrier retrieval / RAG |
| `phawm-sam-frontend` | — | `3001` → 3000 | Frontend for `phawm_sam` |
| `phawm-annif-frontend` | — | `3003` → 3000 | Frontend for `phawm_annif` |
| `demo-frontend` | — | `3004` → 3000 | Frontend for `demo` |

Postgres (`5433`) and RustFS (`9002`/`9003`) are offset so this stack can run
alongside the backend repo's single-tenant stack, which uses `5432` and
`9000`/`9001`.

All services share the `platform-network` bridge and reach each other by
container name — e.g. `http://rustfs-mt:9000`,
`http://universal-llm-inference:8003`.

### What prestart does

`prestart` runs once and exits. Follow it on the first start:

```bash
docker compose logs -f prestart
```

1. `create_db_if_not_exists.py` — creates `POSTGRES_DB` if it does not exist
2. `alembic upgrade head` — applies migrations to the `public` schema
3. `clean_public_schema.py` — drops the application tables Alembic created in
   `public`, keeping only `tenant`, `user`, and `alembic_version`
4. `init_default_tenant.py` — provisions the three built-in tenants

Expected output on a first run:

```
Database 'phawmdb_mt' created.
INFO  [alembic.runtime.migration] Running upgrade ...
Provisioning default PHAWM tenants...

→ PHAWM-SAM (phawm_sam)
  [phawm_sam] Registered in tenant registry.
  [phawm_sam] Schema provisioned and migrations applied.
  [phawm_sam] S3 bucket ensured.
  [phawm_sam] Seed data loaded.
→ PHAWM-ANNIF (phawm_annif)
  ...
→ PHAWM Demo (demo)
  ...
3 tenant(s) ready.
```

Every step is idempotent, so prestart is safe to re-run on each `up`.

### Verify

```bash
docker compose ps
curl http://localhost:8080/openapi.json | head -c 200
```

> Endpoints are served at the **root** — `/login/access-token`, not
> `/api/v1/login/access-token`. `API_V1_STR` is empty by default.

---

## Model Services

The four model servers are part of the stack and start with everything else. The
evaluation MCP server (port `8005`) is **not** a compose service — start it
separately when you need MCP-based metric runs, from the backend directory with
the project venv active:

```bash
python -m src.services.performance_service.mcp_server
```

### Pointing models at the right URL

Each model's `location` (in its model-metadata row) must be a URL the **API
container** can reach:

| Where the API runs | Where the model server runs | `location` to use |
|---|---|---|
| Docker (`api`) | Docker, same stack | `http://sam-attachment-monitor:8002` |
| Docker (`api`) | Host machine | `http://host.docker.internal:8002` |
| Host | Host | `http://localhost:8002` |

Since the model servers run inside the stack, the **container-name form is the
default** — seeded `location` values must use it, not `localhost`. A `location`
of `localhost` inside the API container resolves to the API itself.

Models that use the Universal LLM API set `location = with_api_key` instead of a
URL. See [Model Service → MCP Integration](../backend/model_service.md#mcp-integration)
for how `location` and `mcp_tool_name` select the MCP vs. HTTP path.

---

## The Default Tenants

`scripts/migrations/init_default_tenant.py` provisions the three built-in
tenants, each with a schema, an S3 bucket, and seed data:

| Tenant id | Display name | Seeded apps | Frontend service | Path |
|---|---|---|---|---|
| `phawm_sam` | PHAWM-SAM | SAM | `phawm-sam-frontend` | `/workbench/phawm_sam` |
| `phawm_annif` | PHAWM-ANNIF | Annif | `phawm-annif-frontend` | `/workbench/phawm_annif` |
| `demo` | PHAWM Demo | SAM + Annif | `demo-frontend` | `/workbench/demo` |

`allowed_apps` controls which applications, models, and audits are seeded from
the CSV data. Re-run a subset:

```bash
docker compose run --rm prestart \
  python scripts/migrations/init_default_tenant.py --only demo
```

> **These tenants ship with shared test accounts** —
> `test-audit-instigator@company.com` and `test-auditor@company.com`, both with
> the password `password123`, in **every** seeded tenant. Delete or disable them
> before exposing a deployment to a network.

Editing the `TENANTS` list in that script changes the defaults that ship with a
deployment. For one-off tenants prefer `create_tenant.py`, which also creates an
admin user.

### Deploying without the PHAWM tenants

The three tenants are PHAWM's own research deployments — their seed data is
specific to the SAM and Annif applications, down to model URLs. For an unrelated
organisation, comment out the last line of the `prestart` command block in
`deploy/docker-compose.yml`:

```yaml
        python scripts/clean_public_schema.py
        # python scripts/migrations/init_default_tenant.py
```

Prestart still creates the database, migrates, and prepares `public`. Create
your own tenants as below, and replace the three frontend services with one per
tenant of your own.

Also unregister the demo router for a non-demo deployment: in
`backend/src/api/main.py`, remove `demo` from the imports and delete
`api_router.include_router(demo.router)`. `POST /demo/reset` drops a tenant's
schema and re-seeds it, and is gated only by which tenant the caller belongs to
— not by any demo flag.

---

## Creating Additional Tenants

Use `scripts/create_tenant.py`, run inside the stack so the database
credentials and host are already set:

```bash
docker compose run --rm prestart python scripts/create_tenant.py \
  --id uni_glasgow \
  --name "University of Glasgow" \
  --email admin@uni-glasgow.ac.uk \
  --admin-email jane.smith@uni-glasgow.ac.uk \
  --admin-name "Jane Smith" \
  --admin-username jsmith \
  --admin-password "SecurePassword1!"
```

To run it from the host instead, point it at the published port:

```bash
cd backend
ENV_FILE=../deploy/.env POSTGRES_HOST=127.0.0.1 POSTGRES_PORT=5433 \
python scripts/create_tenant.py --id uni_glasgow ...
```

### What actually happens

**[1/4] Registers the tenant in `public.tenant`** — a row with `id`,
`display_name`, `db_schema`, and `contact_email`. The schema name is derived as
`id.lower().replace("-", "_")` and must match `^[a-z][a-z0-9_]{0,62}$`:
lowercase, starting with a letter, at most 63 characters. If the id already
exists the script aborts without touching anything.

**[2/4] Creates the Postgres schema and runs every Alembic migration inside it.**
`CREATE SCHEMA IF NOT EXISTS "<schema>"`, then `alembic upgrade head` scoped to
that schema. The Alembic version table lives in the tenant's own schema, so each
tenant tracks its migration state separately.

**[3/4] Seeds baseline reference data:**

| Seeded | Source | Rows |
|---|---|---|
| Audit roles | hardcoded | 2 — `audit_instigator`, `auditor` |
| Event categories | `storage/seed_data/categories.csv` | 23 |
| Taxonomy groups | `storage/seed_data/taxonomy_groups.csv` | 6 |
| Taxonomy mappings | `storage/seed_data/taxonomy_mappings.csv` | 23 |

Order matters — categories and taxonomy groups must exist before the mapping
rows can reference their ids.

**[4/4] Creates the first admin user** inside the tenant schema with
`is_active=True`, `is_verified=True`, `is_superuser=False`, and a `UserRoles` row
granting `{"tenant_admin": true}`. **No verification email is sent** — the admin
can log in immediately.

### What you get — and what you don't

A tenant created this way is **empty of content**. It has the full table
structure and the reference data above, but **no applications, models, datasets,
events, metrics, or audits** — unlike the built-in tenants, which
`init_default_tenant.py` seeds from the full CSV set.

| | `create_tenant.py` | `init_default_tenant.py` |
|---|---|---|
| Schema + migrations | ✅ | ✅ |
| Audit roles, categories, taxonomies | ✅ | ✅ |
| Applications, models, datasets, events, metrics, audits | ❌ | ✅ (filtered by `allowed_apps`) |
| First admin user | ✅ | ❌ |
| S3 bucket created up front | ❌ | ✅ |

Two consequences worth planning for:

- **The admin logs into an empty workbench.** They create applications and
  audits through the UI, or you seed the schema separately.
- **No S3 bucket is created up front.** `init_default_tenant.py` calls
  `_ensure_tenant_s3_bucket()`; `create_tenant.py` does not. With
  `STORAGE_BACKEND=s3` the bucket is created lazily on first storage access — if
  you hit bucket errors, create it via `get_storage_manager("<tenant_id>")`.

### Failure behaviour

The steps are **not** wrapped in a single transaction, so where it fails
determines what is left behind:

| Fails at | State left behind | What to do |
|---|---|---|
| [1/4] registry | Nothing | Fix and re-run |
| [2/4] schema/migrations | Registry row **rolled back automatically** | Fix and re-run |
| [3/4] seed | Registry row **and** schema exist, reference data incomplete | Drop the schema and registry row, then re-run |
| [4/4] admin | Tenant fully provisioned but **has no admin** | Don't re-run — add the admin with `create_user.py --admin` |

Only step 2 self-cleans. After a step 3 or 4 failure, re-running fails with
`Tenant '<id>' already exists`, so clean up first or use `create_user.py`.

> **Do not create a tenant with a raw `CREATE SCHEMA`.** Audit creation
> hardcodes `AuditRoles.id == 1 == audit_instigator`, so the audit-roles seed is
> required before the schema sees traffic.

### Options

- `--id` becomes the Postgres schema name (lowercased, hyphens → underscores)
- Omit `--admin-password` to be prompted securely; minimum 8 characters
- `--organisation` is optional, defaulting to the tenant display name
- `--email`, the tenant contact address, is optional

### Build a frontend for the tenant

`VITE_TENANT_ID` is compiled into the bundle, so each tenant needs its own build
and its own route. Add a service to `deploy/docker-compose.yml`:

```yaml
  uni-glasgow-frontend:
    build:
      context: ../frontend
      dockerfile: Dockerfile
      args:
        - VITE_TENANT_ID=uni_glasgow
        - VITE_IS_DEMO=false
    ports:
      - "3005:3000"
    environment:
      - NODE_ENV=production
      - VITE_DOCS_URL=${VITE_DOCS_URL}
      - VITE_API_URL=${VITE_API_URL}
      - VITE_IS_DEMO=false
      - VITE_TENANT_ID=uni_glasgow
    networks:
      - platform-network
    restart: unless-stopped
```

`VITE_TENANT_ID` must be passed **both** as a build arg and as an environment
variable — Vite inlines it at build time, and it also sets the app's base path to
`/workbench/uni_glasgow/`. Then add a route to the Caddyfile:

```caddyfile
  handle_path /workbench/uni_glasgow* {
    reverse_proxy uni-glasgow-frontend:3000
  }
```

```bash
docker compose up -d --build uni-glasgow-frontend
docker compose restart caddy
```

### After creation

The tenant is reachable immediately. Clients send `X-Tenant-ID: uni_glasgow` on
**login**; the returned JWT carries the schema in its `tid` claim and later
requests need no header.

```bash
curl -X POST http://localhost:8080/login/access-token \
  -H "X-Tenant-ID: uni_glasgow" \
  -d "username=jane.smith@uni-glasgow.ac.uk&password=SecurePassword1!"
```

Add more users to an existing tenant with `scripts/create_user.py` (add
`--admin` to grant `tenant_admin`):

```bash
docker compose run --rm prestart python scripts/create_user.py \
  --tenant   uni_glasgow \
  --email    user@uni-glasgow.ac.uk \
  --name     "John Roe" \
  --username jroe \
  --password "SecurePassword1!"
```

---

## Connecting to the Database

### TablePlus / DBeaver / psql

| Field | Value |
|---|---|
| Host | `127.0.0.1` |
| Port | `5433` |
| Database | value of `POSTGRES_DB`, e.g. `phawmdb_mt` |
| User | value of `POSTGRES_USER` |
| Password | value of `POSTGRES_PASSWORD` |

After connecting you should see the public schema plus one schema per tenant:

```
phawmdb_mt
├── public        ← tenant registry, superuser accounts
├── phawm_annif   ← PHAWM-ANNIF tenant
├── demo          ← PHAWM Demo tenant
└── phawm_sam     ← PHAWM-SAM tenant
```

### psql from the terminal

```bash
psql -h 127.0.0.1 -p 5433 -U postgres -d phawmdb_mt

\dn                            -- list schemas
SET search_path TO phawm_sam;  -- switch into a tenant
\dt
```

Or without a local psql client:

```bash
docker compose exec postgres-mt psql -U postgres -d phawmdb_mt -c "\dn"
```

> **`postgres-mt` runs with `POSTGRES_HOST_AUTH_METHOD=trust`** — any connection
> reaching the port is accepted without a password. Port `5433` must not be
> reachable beyond localhost; remove the `ports:` mapping in production.

The RustFS console is at <http://localhost:9003> with `S3_ACCESS_KEY` /
`S3_SECRET_KEY`.

---

## Running Migrations

Migrations are written once and applied to every schema individually — `public`
first, then each tenant schema.

### Through the stack

Re-running prestart applies pending migrations to `public` and to every tenant
in `TENANTS`, and is idempotent:

```bash
docker compose run --rm prestart
```

### From your local machine

The database is published on `5433`. Set the env file and host first:

```bash
cd backend
export ENV_FILE=../deploy/.env
export POSTGRES_HOST=127.0.0.1
export POSTGRES_PORT=5433
```

Then use Alembic as normal:

```bash
alembic upgrade head                                  # apply to public
alembic current                                       # current revision
alembic revision --autogenerate -m "describe_change"  # new migration
alembic downgrade -1                                  # roll back one step
```

### Applying a migration to a tenant not in `TENANTS`

`provision_tenant_schema` is idempotent and applies only pending migrations:

```bash
docker compose run --rm prestart python -c \
  "from src.database import provision_tenant_schema; provision_tenant_schema('uni_glasgow')"
```

### Schema layout after a correct setup

Every tenant schema should report an **identical** table count. `public` holds
only `tenant`, `user`, and `alembic_version`. If a tenant schema is short, its
migrations did not finish — re-run the provisioning for it.

```sql
SELECT table_schema, count(*)
FROM information_schema.tables
WHERE table_schema NOT IN ('pg_catalog', 'information_schema')
GROUP BY table_schema
ORDER BY table_schema;
```

---

## How Tenant Isolation Works

Each tenant schema is a complete, independent copy of the application schema.
The `public` schema holds only:

- `tenant` — the registry of all tenants (`id`, `display_name`, `db_schema`, `is_active`)
- `user` — superuser accounts for platform-level administration
- `alembic_version` — migration state for `public`

At login the client supplies `X-Tenant-ID`. The backend checks the tenant exists
and is active, authenticates the user inside that tenant's schema, and issues a
JWT with the schema name in the `tid` claim. Afterwards `get_tenant_db` resolves
the schema in this order:

1. the `X-Tenant-ID` header — for unauthenticated routes (signup, email
   verification) where no token exists yet; lowercased before use
2. the `tid` claim of the bearer token — for all authenticated routes
3. the `public` schema — superuser operations and requests with no tenant context

The resolved name is validated against `^[a-z][a-z0-9_]{0,62}$` and applied as a
Postgres `search_path` on a per-tenant connection pool, so a query cannot reach
another tenant's tables.

See [Multi-Tenancy Architecture](../backend/multi_tenancy.md) for the permission
model and the provisioning API.

---

## Stopping and Restarting

```bash
docker compose stop     # stop, keep containers and data
docker compose down     # remove containers, keep volumes
docker compose down -v  # remove volumes too — destroys all tenant data
```

Data lives in the `postgres-mt-data`, `rustfs-mt-data`, `pyterrier-indexes`,
`caddy_data`, and `caddy_config` volumes. On later starts prestart runs again but
skips provisioned tenants and applied migrations.

---

## Troubleshooting

### Caddy exits immediately on startup

The Caddyfile still contains the literal `<domain>` placeholder. Replace it with
your hostname, or `:80` for local testing.

### A frontend loads but its assets 404

`handle_path` strips the `/workbench/<tenant>` prefix before proxying, while the
bundle requests its assets *under* that prefix because Vite's `base` is
`/workbench/<tenant>/`. Use `handle` instead of `handle_path` for the frontend
routes so the prefix reaches the upstream.

### Everyone is logged out after an API restart

Expected with the shipped compose file: the JWT secrets are randomly generated at
startup because they are not passed in. See [Configuration](#configuration).

### Only the `public` schema exists after prestart

```bash
docker compose logs prestart
```

Common causes:

- **Deliberate** — you commented out `init_default_tenant.py`.
- **S3 / RustFS connection error** — `rustfs-mt` was not ready. The command uses
  `set -e`, so one failure stops the remaining steps. Re-run compose; the second
  run usually succeeds.
- **`alembic upgrade head` failed** — look for migration errors in the logs and
  reproduce it manually with `ENV_FILE` and the Postgres variables set.

### Login returns "X-Tenant-ID header required for non-superuser login"

The frontend build being served has an empty `VITE_TENANT_ID`. It must be passed
as a **build arg** — the value is inlined at build time, so rebuild the image
after changing it.

### Login fails with tenant not found, or 403

The id baked into the frontend does not match the registry:

```bash
docker compose exec postgres-mt psql -U postgres -d phawmdb_mt \
  -c "SELECT id, is_active FROM public.tenant;"
```

The build's `VITE_TENANT_ID` must match one of those ids exactly, and the tenant
must be active — login rejects a deactivated tenant with `400 Tenant is
inactive`.

### The built-in tenants came back after you removed them

`prestart` re-runs `init_default_tenant.py` on every `up` unless you commented
that line out. Removing the tenants from the database alone is not enough.

### Cannot connect to the database on 5433

```bash
docker ps --format "table {{.Names}}\t{{.Ports}}" | grep 543
```

Make sure nothing else binds `5433`, and that `postgres-mt` passed its
healthcheck.

### Port already in use

The backend repo's single-tenant stack binds `5432`, `8000`, and `9000`/`9001`.
This stack deliberately uses `5433` and `9002`/`9003`, but stop the other stack
if its ports collide with anything here.

### Model calls fail with connection errors from the API

The model's `location` is still `http://localhost:PORT`, which inside the API
container points at the container itself. Use the model server's container name
— see [Pointing models at the right URL](#pointing-models-at-the-right-url).

### Prestart exits with "invalid interpolation syntax"

A fixed bug where URL-encoded characters in the Alembic search_path URL triggered
configparser interpolation. Ensure the backend submodule is up to date —
`src/database.py` passes the connection via `alembic_cfg.attributes` rather than
`set_main_option`.
