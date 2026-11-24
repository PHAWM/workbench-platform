# Installation Guide

How to install the PHAWM Workbench from a clean machine — API, database, object
storage, model servers, per-tenant frontends and the docs site — and how to add
a tenant afterwards.

Everything is deployed from the **platform repository**, which pulls the backend
and frontend in as git submodules:

```
workbench-platform-internal/
├── deploy/                  ← the deployment
│   ├── docker-compose.yml   ← the stack
│   ├── caddy/Caddyfile      ← reverse-proxy routes
│   └── .env                 ← you create this
├── backend/                 ← submodule, branch: multi-tenant
├── frontend/                ← submodule, branch: multi-tenant
└── docs/                    ← this documentation
```

The deployment is **multi-tenant**: one Postgres database with a `public` schema
for platform records and one schema per tenant, plus one frontend build per
tenant, all behind a Caddy reverse proxy.

> The backend repository also carries `backend/deploy/docker-compose.yml` and
> `backend/deploy/docker-compose.multi-tenant.yml`, which run the backend alone
> for local development. **Deployments use `deploy/docker-compose.yml` at the
> platform-repository root** — that is what this guide covers.

---

## 1. Prerequisites

| Tool | Version | Notes |
|---|---|---|
| Docker + Docker Compose | any current | Runs the whole stack |
| Git | any | Needed for submodules |
| Node.js | 22+ | Only to run the frontend outside Docker |
| Python | 3.12 | Only to run backend scripts on the host |

```bash
docker --version && git --version
```

Clone the platform repository **with its submodules**:

```bash
git clone <platform-repo-url> workbench-platform-internal
cd workbench-platform-internal
git submodule update --init --recursive
```

If you cloned without `--recursive`, the `backend/` and `frontend/` directories
will be empty and the build will fail. Run the `submodule update` command above
to populate them.

---

## 2. Configuration

Copy the example and edit it. Compose picks `deploy/.env` up automatically — no
`--env-file` flag is needed.

```bash
cp deploy/.env.example deploy/.env
$EDITOR deploy/.env
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
FRONTEND_URL=http://localhost
VITE_API_URL=http://localhost:8080
VITE_DOCS_URL=http://localhost:8001
```

| Variable | What to set it to |
|---|---|
| `POSTGRES_USER` / `POSTGRES_PASSWORD` | Database credentials |
| `POSTGRES_DB` | `phawmdb_mt`; created on first start if absent |
| `POSTGRES_HOST` | `postgres-db-mt` — the container name |
| `RESEND_API_KEY` | Your Resend key, for invitation and password-reset email |
| `FRONTEND_URL` | Base URL used in emailed links |
| `VITE_API_URL` | Externally reachable API URL, baked into each frontend build. No `/api/v1` suffix. |
| `VITE_DOCS_URL` | Where the docs site is reachable |
| `S3_ACCESS_KEY` / `S3_SECRET_KEY` | RustFS credentials (`admin` locally). Change for anything network-reachable. |

> **JWT secrets are not passed through the compose file.** The `api` service
> does not set `JWT_SECRET_KEY` or `JWT_REFRESH_SECRET_KEY`, so the backend
> generates random ones at startup and every API restart logs everyone out. For
> a real deployment, add both to `.env` *and* to the `api` service's
> `environment:` block in `deploy/docker-compose.yml`:
>
> ```bash
> openssl rand -hex 32   # JWT_SECRET_KEY
> openssl rand -hex 32   # JWT_REFRESH_SECRET_KEY (a different value)
> ```

> `IS_DEMO` is dead configuration in the backend — nothing in `src/` reads it.
> Only the frontend's `VITE_IS_DEMO` has any effect.

### Set the domain in the Caddyfile

`deploy/caddy/Caddyfile` starts with a literal `<domain>` placeholder. Caddy
will not start until you replace it:

```caddyfile
example.org {        # or `:80` for local testing without TLS
  handle /api/* {
    reverse_proxy api:8080
  }
  ...
}
```

With a real, publicly resolvable hostname Caddy obtains TLS certificates from
Let's Encrypt automatically.

---

## 3. Choose your deployment type

Out of the box the stack creates three tenants — `phawm_sam`, `phawm_annif` and
`demo` — with a matching frontend service each. These are **PHAWM's own research
deployments**, not generic scaffolding: their seed data is specific to the SAM
(attachment monitoring) and Annif (subject indexing) applications, down to model
URLs pointing at those model servers. They also ship with shared test accounts.

| | Clean install | PHAWM install |
|---|---|---|
| For | Any organisation setting up its own workbench | Working with PHAWM's SAM / Annif research tenants |
| Built-in tenants | None — you create your own | `phawm_sam`, `phawm_annif`, `demo` |
| Test accounts | None | Two per tenant, shared password |
| Applications & models | You define your own | SAM and Annif pre-seeded |

**If you are setting up your own deployment, take the clean install.** It is the
default path through the rest of this guide; the PHAWM path is noted where it
differs.

### Clean install — skip the built-in tenants

Comment out the last line of the `prestart` command block in
`deploy/docker-compose.yml`:

```yaml
    command:
      - bash
      - -c
      - |
        set -e
        pip install psycopg2-binary --quiet
        python scripts/create_db_if_not_exists.py
        alembic upgrade head
        python scripts/clean_public_schema.py
        # python scripts/migrations/init_default_tenant.py
```

Prestart still creates the database, applies all migrations and prepares the
public schema — it just does not create PHAWM's tenants. You create your own in
[§7](#7-add-a-tenant).

Also, for a clean install:

- **Remove the three frontend services** (`phawm-sam-frontend`,
  `phawm-annif-frontend`, `demo-frontend`) and their Caddyfile routes, replacing
  them with one per tenant of your own ([§7](#7-add-a-tenant)).
- **Unregister the demo router.** In `backend/src/api/main.py`, remove `demo`
  from the imports and delete the `api_router.include_router(demo.router)` line.
  `POST /demo/reset` drops a tenant's schema and re-seeds it; it is gated only by
  which tenant the caller belongs to, **not** by any demo flag, so it stays live
  otherwise.
- **Set `VITE_IS_DEMO=false`** on your frontend services.

---

## 4. Preflight — what you must change

A fresh clone is **not** ready to start. Exactly two things must be edited by
hand; everything else has a working default. Both fail *quietly*, so confirm
them before starting.

| # | What | Where | If you skip it |
|---|---|---|---|
| 1 | Create `.env` | `deploy/.env` (copy of `.env.example`) | Only `.env.example` is committed. Compose expands every `${VAR}` to an **empty string**, warns, and carries on — you get a Postgres with a blank password and frontends built with `VITE_API_URL=""`. |
| 2 | Replace `<domain>` | `deploy/caddy/Caddyfile`, line 1 | `<domain>` is not a valid Caddy address, so `caddy` **exits immediately**. Every other service starts, so `docker compose ps` looks fine but nothing is reachable on `:80`/`:443`. |

These `.env` variables have no usable default:

| Variable | Set it to |
|---|---|
| `POSTGRES_PASSWORD` | Any non-empty password (ships as `change-me`) |
| `S3_SECRET_KEY` | Any non-empty secret — also the RustFS root password (ships as `change-me`) |
| `FRONTEND_URL` | Externally reachable base URL, used in emailed links |
| `VITE_API_URL` | Externally reachable API URL, **no** `/api/v1` suffix |
| `VITE_DOCS_URL` | Where this docs site is reachable |
| `RESEND_API_KEY` | A Resend key, or empty to disable invitation / password-reset email |

Check both at once:

```bash
cd deploy
test -f .env || echo "MISSING: deploy/.env - run: cp .env.example .env"
grep -q '<domain>' caddy/Caddyfile && echo "MISSING: replace <domain> in caddy/Caddyfile"
```

No output means you are ready.

!!! warning "`VITE_*` are build-time, not run-time"
    They are compiled into each frontend bundle during the image build. Changing
    one later requires `docker compose up -d --build <frontend-service>` — a
    plain restart keeps the old value.

!!! note "What needs no action"
    Verified on a clean clone: migrations resolve to a **single** Alembic head;
    all 13 seed CSVs in `backend/storage/seed_data/` are committed; every Python
    dependency is pinned; both submodules track `multi-tenant`; and `prestart`
    is idempotent, so it is safe on every start. Be aware, though, that
    `rustfs/rustfs:latest` is unpinned, and the `api` service bind-mounts
    `../backend:/app` over the image so it runs your working tree.

---

## 5. Start the stack

```bash
cd deploy
docker compose up -d --build
```

The first run takes several minutes — it builds the backend, the frontend
bundles, and four model-server images, then runs migrations.

| Service | Container | Host port | Purpose |
|---|---|---|---|
| `caddy` | `caddy` | `80`, `443` | Reverse proxy, automatic TLS |
| `api` | — | `8080` | FastAPI backend |
| `postgres-mt` | `postgres-db-mt` | `5433` | PostgreSQL |
| `rustfs-mt` | `rustfs-mt` | `9002`, `9003` | Object storage (API, console) |
| `prestart` | `prestart-mt` | — | One-shot: creates the DB, migrates, prepares `public` (and seeds built-in tenants unless disabled) |
| `docs` | — | `8001` | This documentation |
| `sam-api` | `sam-attachment-monitor` | `8002` | SAM model server |
| `universal-llm-api` | `universal-llm-inference` | `8003` | Universal LLM server |
| `annif-api` | `annif-subject-indexing` | `8004` | ANNIF classifier |
| `pyterrier-rag-api` | `pyterrier-rag` | `8006` | PyTerrier retrieval / RAG |
| `phawm-sam-frontend` | — | `3001` | Frontend for `phawm_sam` |
| `phawm-annif-frontend` | — | `3003` | Frontend for `phawm_annif` |
| `demo-frontend` | — | `3004` | Frontend for `demo` |

Postgres (`5433`) and RustFS (`9002`/`9003`) are offset from the backend repo's
single-tenant stack (`5432`, `9000`/`9001`), so both can run at once.

Wait for `prestart-mt` to finish and exit:

```bash
docker compose logs -f prestart
```

On a PHAWM install it ends with `3 tenant(s) ready.`; on a clean install it ends
after the public-schema step.

### Verify the backend

```bash
docker compose ps
curl http://localhost:8080/openapi.json | head -c 200
```

Interactive API docs: **<http://localhost:8080/docs>**

> Endpoints are served at the **root** — `/login/access-token`, not
> `/api/v1/login/access-token`. `API_V1_STR` is empty by default.

**Clean install:** no tenants exist yet — create yours in
[§7](#7-add-a-tenant).

**PHAWM install:** three tenants are provisioned automatically. Check:

```bash
docker compose exec postgres-mt psql -U postgres -d phawmdb_mt \
  -c "SELECT id, display_name FROM public.tenant;"
```

---

## 6. First login

Each tenant is served at its own path, `/workbench/<tenant_id>/`, by its own
frontend build. Through Caddy that is `http://localhost/workbench/demo/`; the
containers also publish direct ports (`3001`, `3003`, `3004`) for testing
without the proxy.

**Clean install:** log in with the admin account you create in
[§7](#7-add-a-tenant). The frontend sends `X-Tenant-ID: <your tenant>` on login;
the returned JWT carries the tenant in its `tid` claim, so later requests need no
header.

**PHAWM install:** each seeded tenant ships with two test accounts:

| Email | Role | Password |
|---|---|---|
| `test-audit-instigator@company.com` | audit instigator | `password123` |
| `test-auditor@company.com` | auditor | `password123` |

> **Remove the test accounts before exposing a deployment.** They exist in
> **every seeded tenant** with the same well-known password. A clean install
> never creates them.

Add another account to an existing tenant:

```bash
docker compose run --rm prestart python scripts/create_user.py \
  --tenant   demo \
  --email    you@example.com \
  --name     "Your Name" \
  --username you \
  --password "SecurePassword1!" \
  --admin
```

---

## 7. Add a tenant

Adding a tenant is **two steps**: create it in the backend, then build a frontend
for it. On a clean install this is also how you create your *first* tenant —
there is nothing special about it.

### Step 1 — Create the tenant and its admin

```bash
docker compose run --rm prestart python scripts/create_tenant.py \
  --id acme_corp \
  --name "ACME Corporation" \
  --email contact@acme.com \
  --admin-email admin@acme.com \
  --admin-name "Your Name" \
  --admin-username admin \
  --admin-password "SecurePassword1!"
```

This registers the tenant, creates its Postgres schema, runs every migration
inside it, seeds reference data, and creates the first admin user with
`tenant_admin` permissions. No verification email is sent — the admin can log in
immediately.

`--id` becomes the schema name: lowercase, matching `^[a-z][a-z0-9_]{0,62}$`
(hyphens are converted to underscores). Omit `--admin-password` to be prompted.

To run it from the host instead of inside the stack:

```bash
cd backend
ENV_FILE=../deploy/.env POSTGRES_HOST=127.0.0.1 POSTGRES_PORT=5433 \
python scripts/create_tenant.py --id acme_corp ...
```

**What the tenant gets:** 2 audit roles (`audit_instigator`, `auditor` —
required, since audit creation depends on them), 23 event categories, 6 taxonomy
groups, 23 taxonomy mappings, and the admin user.

**What it does not get:** applications, models, datasets, events, metrics or
audits. That is deliberate — the built-in tenants' seed data is specific to the
SAM and Annif applications, including model URLs pointing at those servers. Your
admin defines your own applications and audits through the UI. See
[What you get — and what you don't](multi_tenant_deployment.md#what-you-get-and-what-you-dont).

### Step 2 — Build a frontend for the tenant

`VITE_TENANT_ID` is compiled into the bundle, so each tenant needs its own build
served at its own path. Add a service to `deploy/docker-compose.yml`:

```yaml
  acme-frontend:
    build:
      context: ../frontend
      dockerfile: Dockerfile
      args:
        - VITE_TENANT_ID=acme_corp
        - VITE_IS_DEMO=false
    ports:
      - "3005:3000"
    environment:
      - NODE_ENV=production
      - VITE_DOCS_URL=${VITE_DOCS_URL}
      - VITE_API_URL=${VITE_API_URL}
      - VITE_IS_DEMO=false
      - VITE_TENANT_ID=acme_corp
    networks:
      - platform-network
    restart: unless-stopped
```

`VITE_TENANT_ID` must be passed **both** as a build arg and as an environment
variable: Vite inlines it into the bundle at build time, and it also sets the
app's base path to `/workbench/acme_corp/`.

Add a matching route in `deploy/caddy/Caddyfile`:

```caddyfile
  handle_path /workbench/acme_corp* {
    reverse_proxy acme-frontend:3000
  }
```

```bash
docker compose up -d --build acme-frontend
docker compose restart caddy
```

### Step 3 — Verify

```bash
# the tenant is registered
docker compose exec postgres-mt psql -U postgres -d phawmdb_mt \
  -c "SELECT id, display_name, db_schema FROM public.tenant;"

# login works
curl -X POST http://localhost:8080/login/access-token \
  -H "X-Tenant-ID: acme_corp" \
  -d "username=admin@acme.com&password=SecurePassword1!"
```

A token in the response means the tenant is live.

### Adding more users

```bash
docker compose run --rm prestart python scripts/create_user.py \
  --tenant   acme_corp \
  --email    john@acme.com \
  --name     "John Roe" \
  --username jroe \
  --password "SecurePassword1!"
```

Add `--admin` to grant `tenant_admin`.

---

## 8. Running the frontend outside Docker

For frontend development against the running stack:

```bash
cd frontend
npm install --force
```

> `--force` is required — the project has peer-dependency conflicts under
> React 19.

Create `frontend/.env`:

```ini
VITE_API_URL="http://127.0.0.1:8080"
VITE_DOCS_URL="http://127.0.0.1:8001"
VITE_IS_DEMO=false
# Tenant slug for this build. Leave empty for superuser / local dev.
VITE_TENANT_ID=acme_corp
```

| Variable | Meaning |
|---|---|
| `VITE_API_URL` | Backend base URL, no `/api/v1` suffix |
| `VITE_DOCS_URL` | Where the docs are served |
| `VITE_IS_DEMO` | `true` only enables the demo-reset button on the profile page |
| `VITE_TENANT_ID` | Tenant slug. Sets the `X-Tenant-ID` login header **and** the app's base path. |

```bash
npm start
```

The app opens at **<http://localhost:3000>**. With `VITE_TENANT_ID` set it is
served from `/workbench/<tenant_id>/` rather than `/`; an empty value means the
root path and no tenant header — use that only for superuser work or local
development.

Vite reads `.env` only at startup, so restart after editing it.

```bash
npm run build      # production build into dist/
```

---

## 9. Troubleshooting

**Build fails: no such file or directory `../backend` or `../frontend`.** The
submodules are not checked out. Run
`git submodule update --init --recursive`.

**Caddy exits immediately.** The Caddyfile still contains the literal
`<domain>`. Replace it with your hostname or `:80`.

**Everyone is logged out whenever the API restarts.** The JWT secrets are
randomly generated at startup because the compose file does not pass them in —
see [§2](#2-configuration).

**Frontend loads but every request fails.** Check `VITE_API_URL` — it must be
the externally reachable API URL with no `/api/v1` suffix, and it is baked in at
build time, so rebuild after changing it.

**A frontend loads but its assets 404.** `handle_path` strips the
`/workbench/<tenant>` prefix, while the bundle requests assets under that prefix
because Vite's `base` is `/workbench/<tenant>/`. Use `handle` rather than
`handle_path` for the frontend routes.

**Login returns "X-Tenant-ID header required for non-superuser login".**
`VITE_TENANT_ID` is empty in the build being served. It must be passed as a
*build arg*; rebuild the image after setting it.

**Login fails with tenant not found or 403.** The id in the build does not match
the registry, or the tenant is deactivated:

```bash
docker compose exec postgres-mt psql -U postgres -d phawmdb_mt \
  -c "SELECT id, is_active FROM public.tenant;"
```

**`npm install` fails with peer-dependency errors.** Use `npm install --force`.

**Only the `public` schema exists after startup.** On a **clean install this is
correct** — no tenants exist until you create one in [§7](#7-add-a-tenant). On a
PHAWM install it means prestart failed; check `docker compose logs prestart`.
Usually RustFS was not ready, and re-running compose succeeds.

**The built-in tenants came back after you removed them.** `prestart` re-runs
`init_default_tenant.py` on every `up` unless you commented that line out of the
compose file — see [§3](#3-choose-your-deployment-type). Removing the tenants
from the database alone is not enough.

**Port already in use.** The backend repo's single-tenant stack binds `5432`,
`8000`, and `9000`/`9001`. Stop it if its ports collide.

**Model calls fail from the API container.** A model's `location` still says
`localhost`, which inside Docker points at the API container itself. Use the
model server's container name, e.g. `http://universal-llm-inference:8003`.

---

## Where to go next

- [Multi-Tenant Deployment](multi_tenant_deployment.md) — the full deployment reference
- [Multi-Tenancy Architecture](../backend/multi_tenancy.md) — how isolation and permissions work
- [Configuration](../backend/configuration.md) — every backend environment variable
