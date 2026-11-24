# Multi-Tenant Deployment

This directory deploys the whole PHAWM Workbench platform — API, database, object
storage, model servers, the per-tenant frontends, and the docs site — as a single
Docker Compose stack behind a Caddy reverse proxy.

The stack is **multi-tenant**: one Postgres database holds a `public` schema for
platform records (the tenant registry) and one schema per tenant. Each tenant
also gets its **own frontend build**, because the tenant id is compiled into the
bundle at build time.

```
                      ┌─────────────┐
   :80 / :443 ───────▶│    caddy    │
                      └──────┬──────┘
         /api/*              │              /workbench/<tenant>*
            ┌────────────────┼────────────────┬──────────────────┐
            ▼                ▼                ▼                  ▼
      ┌──────────┐   ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
      │   api    │   │ phawm-sam-   │  │ phawm-annif- │  │    demo-     │
      │  :8080   │   │  frontend    │  │  frontend    │  │  frontend    │
      └────┬─────┘   └──────────────┘  └──────────────┘  └──────────────┘
           │
    ┌──────┴───────┬─────────────┬──────────────┬───────────────┐
    ▼              ▼             ▼              ▼               ▼
postgres-mt    rustfs-mt     sam-api    universal-llm-api   annif-api
 (schemas)     (S3 store)                                 pyterrier-rag-api
```

---

## 1. Prerequisites

- Docker and Docker Compose (Linux, macOS, or Windows with WSL2)
- The submodules checked out — the stack builds `../backend` and `../frontend`:

```bash
git submodule update --init --recursive
```

Both submodules track their `multi-tenant` branch.

---

## 2. Create `deploy/.env`

Compose reads `deploy/.env` automatically. Start from the example and fill in
your own values:

```bash
cp .env.example .env
```

The full set of variables:

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

# --- URLs baked into the frontends / used in emailed links ---
FRONTEND_URL=https://example.org
VITE_API_URL=https://example.org/api
VITE_DOCS_URL=https://example.org/workbench/docs
```

Notes on individual variables:

| Variable | Notes |
|---|---|
| `POSTGRES_HOST` | Must be `postgres-db-mt` (the container name) for the `api` service. The `prestart` service overrides it anyway. |
| `POSTGRES_DB` | Created automatically on first start if it does not exist. |
| `FRONTEND_URL` | Base URL used in invitation and password-reset emails. |
| `VITE_API_URL` | Baked into each frontend build. Must be the externally reachable API URL, with no `/api/v1` suffix. |
| `VITE_DOCS_URL` | Where the docs site is reachable, used by the in-app docs links. |
| `S3_ACCESS_KEY` / `S3_SECRET_KEY` | Also become the RustFS root credentials. Change them for anything network-reachable. |

> `JWT_SECRET_KEY` and `JWT_REFRESH_SECRET_KEY` are **not** passed through by this
> compose file. The backend generates random secrets at startup instead, which
> means every API restart invalidates all existing tokens and users must log in
> again. If that matters, add both to the `.env` and to the `api` service's
> `environment:` block.

**Do not commit `.env`.** Keep credentials out of git.

---

## 3. Configure the domain

The Caddyfile ships with a literal placeholder on its first line. Edit
[caddy/Caddyfile](caddy/Caddyfile) and replace `<domain>` with your hostname
before starting the stack, or Caddy will fail to load its config:

```caddyfile
example.org {
  handle /api/* {
    reverse_proxy api:8080
  }
  ...
}
```

For local testing without TLS, use `:80` instead of a hostname. Caddy requests
certificates from Let's Encrypt automatically for a real, publicly resolvable
domain.

---

## 3b. Preflight — what you must change before the first start

A fresh clone is **not** ready to start. Exactly two things must be edited by
hand; everything else has a working default. Both fail quietly rather than
loudly, so check them before `docker compose up`.

| # | What | Where | Why it must change |
|---|---|---|---|
| 1 | Create `.env` | `deploy/.env` (copy of `.env.example`) | Only `.env.example` is committed. Without `.env`, Compose expands every `${VAR}` to an **empty string** — it prints a warning and carries on, giving you a Postgres with a blank password and frontends built with `VITE_API_URL=""`. |
| 2 | Replace `<domain>` | `deploy/caddy/Caddyfile`, line 1 | `<domain>` is not a valid Caddy address, so the `caddy` container **exits immediately** on config load. The rest of the stack still starts, so nothing is reachable on `:80`/`:443` while `docker compose ps` looks healthy apart from Caddy. |

Inside `.env`, these have no usable default and must be set:

| Variable | Set it to |
|---|---|
| `POSTGRES_PASSWORD` | Any non-empty password (ships as `change-me`) |
| `S3_SECRET_KEY` | Any non-empty secret — also becomes the RustFS root password (ships as `change-me`) |
| `FRONTEND_URL` | Externally reachable base URL, used in emailed links |
| `VITE_API_URL` | Externally reachable API URL, **no** `/api/v1` suffix — baked into each frontend at build time |
| `VITE_DOCS_URL` | Where the docs site is reachable |
| `RESEND_API_KEY` | A Resend key, or leave empty to disable invitation / password-reset email |

Run both checks in one go:

```bash
cd deploy
test -f .env || echo "MISSING: deploy/.env - run: cp .env.example .env"
grep -q '<domain>' caddy/Caddyfile && echo "MISSING: replace <domain> in caddy/Caddyfile"
```

No output means you are ready to start.

> `VITE_*` values are compiled into the frontend bundles at **build** time, not
> read at run time. Changing one later needs
> `docker compose up -d --build <frontend-service>`, not a restart.

### Everything else is already correct

These are common failure points that need **no** action — verified on a clean
clone:

- **Migrations** resolve to a single Alembic head, so `alembic upgrade head`
  applies cleanly despite the merge revisions in the history.
- **Seed data** — all 13 CSVs in `backend/storage/seed_data/` are committed.
- **Dependencies** — `psycopg2-binary`, `alembic`, `sqlmodel`, `boto3` and
  `uvicorn` are all pinned in `backend/requirements.txt`.
- **Submodules** — `backend/` and `frontend/` both track `multi-tenant`; all
  four model-server Dockerfiles are present.
- **`prestart` is idempotent** in all four steps, so it is safe on every start.

Two things to be aware of rather than fix:

- `rustfs/rustfs:latest` is the one unpinned image, so it can change between
  deploys. Pin a digest for a reproducible deployment.
- The `api` service bind-mounts `../backend:/app` over the image, so it runs
  your working tree rather than the built code. Convenient for development;
  remove the mount for a real deployment.

---

## 4. Start the stack

```bash
cd deploy
docker compose up -d --build
```

The first run takes several minutes — it builds the backend, three frontend
bundles, and four model-server images, then runs migrations.

The `prestart` service runs once and exits. Watch it to confirm the database is
ready:

```bash
docker compose logs -f prestart
```

It performs four steps in order:

1. `create_db_if_not_exists.py` — creates `POSTGRES_DB` if absent
2. `alembic upgrade head` — applies migrations to `public`
3. `clean_public_schema.py` — drops app tables from `public`, keeping only
   `tenant`, `user`, and `alembic_version`
4. `init_default_tenant.py` — provisions the three built-in tenants

Expected tail of the output:

```
→ PHAWM-SAM (phawm_sam)
  [phawm_sam] Registered in tenant registry.
  [phawm_sam] Schema provisioned and migrations applied.
  [phawm_sam] S3 bucket ensured.
  [phawm_sam] Seed data loaded.
...
3 tenant(s) ready.
```

All four steps are idempotent, so `prestart` is safe to re-run on every start.

### Services and ports

| Service | Container | Host port | Purpose |
|---|---|---|---|
| `caddy` | `caddy` | `80`, `443` | Reverse proxy and TLS |
| `api` | — | `8080` | FastAPI backend |
| `postgres-mt` | `postgres-db-mt` | `5433` → 5432 | PostgreSQL (all tenant schemas) |
| `rustfs-mt` | `rustfs-mt` | `9002` → 9000, `9003` → 9001 | S3-compatible object storage + console |
| `prestart` | `prestart-mt` | — | One-shot DB setup; exits when done |
| `docs` | — | `8001` → 8000 | MkDocs site |
| `sam-api` | `sam-attachment-monitor` | `8002` | SAM model server |
| `universal-llm-api` | `universal-llm-inference` | `8003` | Universal LLM server |
| `annif-api` | `annif-subject-indexing` | `8004` | ANNIF subject indexing |
| `pyterrier-rag-api` | `pyterrier-rag` | `8006` | PyTerrier retrieval / RAG |
| `phawm-sam-frontend` | — | `3001` → 3000 | Frontend for `phawm_sam` |
| `phawm-annif-frontend` | — | `3003` → 3000 | Frontend for `phawm_annif` |
| `demo-frontend` | — | `3004` → 3000 | Frontend for `demo` |

Postgres (`5433`) and RustFS (`9002`/`9003`) are deliberately offset so this
stack can run alongside the backend repo's single-tenant stack.

Verify everything is up:

```bash
docker compose ps
curl http://localhost:8080/openapi.json | head -c 200
```

> API endpoints are served at the **root** — `/login/access-token`, not
> `/api/v1/login/access-token`. `API_V1_STR` is empty by default. Caddy strips
> nothing from `/api/*`, so the public path is `https://<domain>/api/...` only if
> your backend expects that prefix; otherwise route `/api/*` with `handle_path`.

---

## 5. The built-in tenants

`init_default_tenant.py` provisions three tenants, each with its own schema, S3
bucket, and seed data:

| Tenant id | Display name | Seeded apps | Frontend | Path |
|---|---|---|---|---|
| `phawm_sam` | PHAWM-SAM | SAM | `phawm-sam-frontend` | `/workbench/phawm_sam` |
| `phawm_annif` | PHAWM-ANNIF | Annif | `phawm-annif-frontend` | `/workbench/phawm_annif` |
| `demo` | PHAWM Demo | SAM + Annif | `demo-frontend` | `/workbench/demo` |

Re-provision a subset without touching the others:

```bash
docker compose run --rm prestart \
  python scripts/migrations/init_default_tenant.py --only demo
```

> **The seeded tenants ship with shared test accounts** —
> `test-audit-instigator@company.com` and `test-auditor@company.com`, both with
> the password `password123`. Delete or disable them before exposing a
> deployment to a network.

### Setting up your own deployment instead

These three tenants are PHAWM's own research deployments; their seed data is
specific to the SAM and Annif applications. For an unrelated organisation,
comment out the last line of the `prestart` command block in
[docker-compose.yml](docker-compose.yml):

```yaml
        python scripts/clean_public_schema.py
        # python scripts/migrations/init_default_tenant.py
```

Prestart still creates the database, migrates, and prepares `public` — it just
creates no tenants. Then add your own as in §6. Also replace the three frontend
services with one per tenant of your own.

---

## 6. Add a tenant

Adding a tenant is two steps: create it in the backend, then build a frontend
for it and give it a route.

### Step 1 — Create the tenant and its first admin

```bash
docker compose run --rm prestart python scripts/create_tenant.py \
  --id uni_glasgow \
  --name "University of Glasgow" \
  --email contact@uni-glasgow.ac.uk \
  --admin-email jane.smith@uni-glasgow.ac.uk \
  --admin-name "Jane Smith" \
  --admin-username jsmith \
  --admin-password "SecurePassword1!"
```

`--id` becomes the Postgres schema name. It is lowercased with hyphens converted
to underscores, and must match `^[a-z][a-z0-9_]{0,62}$`. Omit `--admin-password`
to be prompted (minimum 8 characters).

The script runs four steps: registers the tenant in `public.tenant`, creates the
schema and runs every migration inside it, seeds baseline reference data (2 audit
roles, 23 event categories, 6 taxonomy groups, 23 taxonomy mappings), and creates
the admin user with `tenant_admin` permissions. No verification email is sent —
the admin can log in immediately.

A tenant created this way has the full table structure and reference data but
**no applications, models, datasets, events, metrics, or audits**. The admin
defines those through the UI.

Only step 2 self-cleans on failure. If seeding or admin creation fails, the
schema and registry row remain, and re-running reports `Tenant '<id>' already
exists` — drop both and retry, or add the admin with `create_user.py --admin`.

### Step 2 — Build a frontend for the tenant

Add a service mirroring the existing ones, passing the tenant id as a build arg:

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
variable: Vite inlines it into the bundle at build time, and it also sets the
app's base path to `/workbench/uni_glasgow/`.

Then add a route to [caddy/Caddyfile](caddy/Caddyfile):

```caddyfile
  handle_path /workbench/uni_glasgow* {
    reverse_proxy uni-glasgow-frontend:3000
  }
```

Bring it up and reload the proxy:

```bash
docker compose up -d --build uni-glasgow-frontend
docker compose restart caddy
```

### Step 3 — Verify

```bash
# the tenant is registered
docker compose exec postgres-mt \
  psql -U postgres -d phawmdb_mt -c "SELECT id, display_name, db_schema FROM public.tenant;"

# login works
curl -X POST http://localhost:8080/login/access-token \
  -H "X-Tenant-ID: uni_glasgow" \
  -d "username=jane.smith@uni-glasgow.ac.uk&password=SecurePassword1!"
```

A token in the response means the tenant is live.

### Add more users to a tenant

```bash
docker compose run --rm prestart python scripts/create_user.py \
  --tenant   uni_glasgow \
  --email    john@uni-glasgow.ac.uk \
  --name     "John Roe" \
  --username jroe \
  --password "SecurePassword1!"
```

Add `--admin` to grant `tenant_admin`.

---

## 7. How tenant routing works

Each tenant is one Postgres schema; the `public` schema holds only the `tenant`
registry, superuser accounts, and `alembic_version`.

**At login**, the client sends `X-Tenant-ID: <tenant_id>`. The backend
authenticates the user inside that tenant's schema and issues a JWT carrying the
schema in its `tid` claim.

**On later requests** no header is needed — `get_tenant_db` resolves the schema
in this order:

1. the `X-Tenant-ID` header, for unauthenticated flows (signup, email
   verification), lowercased before use
2. the `tid` claim of the bearer token, for all authenticated routes
3. the `public` schema, for superuser operations

The resolved name is validated against `^[a-z][a-z0-9_]{0,62}$` and applied as a
Postgres `search_path` on a per-tenant connection pool, so a query can never
reach another tenant's tables.

Superusers send no `X-Tenant-ID` and their token has no `tid` claim; they operate
on `public` and own the `/tenants/` endpoints.

See [Multi-Tenancy Architecture](../docs/docs/backend/multi_tenancy.md) for the
permission model.

---

## 8. Connect to the database

| Field | Value |
|---|---|
| Host | `127.0.0.1` |
| Port | `5433` |
| Database | value of `POSTGRES_DB` (e.g. `phawmdb_mt`) |
| User / Password | `POSTGRES_USER` / `POSTGRES_PASSWORD` |

```bash
psql -h 127.0.0.1 -p 5433 -U postgres -d phawmdb_mt

\dn                            -- list schemas, one per tenant plus public
SET search_path TO phawm_sam;  -- switch into a tenant
\dt
```

Every tenant schema should have an identical table count; `public` has fewer
(only `tenant`, `user`, `alembic_version`). A short tenant schema means its
migrations did not finish — re-run `init_default_tenant.py`.

```sql
SELECT table_schema, count(*)
FROM information_schema.tables
WHERE table_schema NOT IN ('pg_catalog', 'information_schema')
GROUP BY table_schema ORDER BY table_schema;
```

> `postgres-mt` runs with `POSTGRES_HOST_AUTH_METHOD=trust`, so any connection
> reaching the port is accepted without a password. Port `5433` must not be
> exposed beyond localhost; remove the `ports:` mapping in production.

The RustFS console is at <http://localhost:9003>, using `S3_ACCESS_KEY` /
`S3_SECRET_KEY`.

---

## 9. Migrations

Migrations are written once and applied to each schema separately. After adding
a migration, re-run prestart to apply it to `public` and every built-in tenant:

```bash
docker compose run --rm prestart
```

For a tenant not listed in `init_default_tenant.py`, re-run migrations against
its schema via `provision_tenant_schema`, which is idempotent:

```bash
docker compose run --rm prestart python -c \
  "from src.database import provision_tenant_schema; provision_tenant_schema('uni_glasgow')"
```

Each tenant schema carries its own `alembic_version` table, so tenants track
migration state independently.

---

## 10. Stop and restart

```bash
docker compose stop     # stop, keep containers and data
docker compose down     # remove containers, keep volumes
docker compose down -v  # remove volumes too — destroys all tenant data
```

Data lives in the `postgres-mt-data`, `rustfs-mt-data`, `pyterrier-indexes`,
`caddy_data`, and `caddy_config` volumes.

---

## 11. Troubleshooting

**Caddy exits immediately.** The Caddyfile still contains the literal
`<domain>`. Replace it with your hostname or `:80` (§3).

**Only `public` exists after startup.** If you commented out
`init_default_tenant.py`, that is correct. Otherwise prestart failed — check
`docker compose logs prestart`. The command uses `set -e`, so one failing step
stops the rest; the usual cause is RustFS not being ready, and re-running
succeeds.

**Everyone is logged out after an API restart.** Expected: the JWT secrets are
randomly generated at startup because this compose file does not pass them in
(§2).

**Login returns "X-Tenant-ID header required for non-superuser login".** The
frontend build being served has an empty `VITE_TENANT_ID`. It must be passed as a
*build arg*, not only as an environment variable — the value is inlined at build
time, so rebuild the image after changing it.

**A frontend loads but its assets 404.** `handle_path` strips the
`/workbench/<tenant>` prefix before proxying, while the bundle requests assets
under that same prefix because Vite's `base` is `/workbench/<tenant>/`. Use
`handle` instead of `handle_path` for the frontend routes so the prefix is
preserved.

**Login fails with tenant not found.** The id in the build does not match the
registry. List what exists:

```bash
docker compose exec postgres-mt psql -U postgres -d phawmdb_mt \
  -c "SELECT id FROM public.tenant;"
```

**Model calls fail from the API container.** A model's `location` still points at
`localhost`, which inside the container is the API itself. Use the model server's
container name, e.g. `http://universal-llm-inference:8003`.

**Ports already in use.** If the backend repo's single-tenant stack is running,
stop it first — it binds `5432`, `8000`, and `9000`/`9001`.

---

## Related documentation

- [Installation Guide](../docs/docs/setup/installation.md) — full install from a clean machine
- [Multi-Tenancy Architecture](../docs/docs/backend/multi_tenancy.md) — isolation and permission model
- [Backend Configuration](../docs/docs/backend/configuration.md) — every environment variable
