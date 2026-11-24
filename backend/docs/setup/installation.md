# Installation Guide

How to install the PHAWM Workbench — backend, database, storage, model servers,
and frontend — from a clean machine, and how to add a tenant afterwards.

There are two ways to run the workbench:

| | Single-tenant | Multi-tenant |
|---|---|---|
| Schemas | One (`public`) | One schema per tenant |
| Use it for | Local development, a single organisation | Several organisations on one deployment |
| Compose file | `deploy/docker-compose.yml` | `deploy/docker-compose.multi-tenant.yml` |
| Frontend builds | One | **One per tenant** |

**This guide covers the multi-tenant install**, which is what deployments use.
Single-tenant differences are noted at the end.

---

## 1. Prerequisites

| Tool | Version | Notes |
|---|---|---|
| Docker + Docker Compose | any current | Runs the whole backend stack |
| Python | **3.11.9** | Pinned in `.tool-versions`; only needed to run scripts on the host |
| Git | any | |

Check what you have:

```bash
docker --version && python3 --version
```

Everything lives in one platform repository. `frontend/` and `backend/` are git
submodules; `deploy/` and `docs/` are part of the platform repo itself:

```
platform-repo/
├── docs/                     ← documentation
├── deploy/                   ← docker-compose files, .env files
│   └── caddy/
│       └── Caddyfile         ← reverse-proxy routing
├── frontend/                 ← submodule — contains its own Dockerfile
└── backend/                  ← submodule — contains its own Dockerfile
```

Clone it with its submodules:

```bash
git clone --recurse-submodules <platform-repo-url>
cd <platform-repo>
```

If you cloned without `--recurse-submodules`, populate them afterwards:

```bash
git submodule update --init --recursive
```

To pull the latest frontend and backend code later:

```bash
git submodule update --remote
```

> **Where things live.** Each Dockerfile sits in the submodule it builds
> (`frontend/Dockerfile`, `backend/deploy/Dockerfile`), while every compose file,
> `.env` file and the Caddyfile live in the platform repo's `deploy/`. Commands
> in this guide are run **from the platform repo root** unless stated otherwise.

---

## 2. Backend configuration

All settings live in `deploy/.env.multi-tenant`. Create it before starting
anything.

### Step 1 — Generate the two JWT secrets

Run this twice and keep both values — they must be different from each other:

```bash
openssl rand -hex 32
```

### Step 2 — Create the file

From the platform repo root, paste the following into
`deploy/.env.multi-tenant`, substituting the two secrets you just generated:

```bash
# --- Database ---
POSTGRES_USER=postgres
POSTGRES_PASSWORD=change-me
POSTGRES_DB=phawmdb_mt
POSTGRES_HOST=localhost
POSTGRES_PORT=5433

# --- pgAdmin (single-tenant stack only) ---
PGADMIN_EMAIL=admin@example.com
PGADMIN_PASSWORD=change-me

# --- App ---
RESEND_API_KEY=re_xxxxxxxxxxxxxxxxxxxx
FRONTEND_URL=https://your-host.example.org/workbench
IS_DEMO=FALSE
JWT_SECRET_KEY=<first value from step 1>
JWT_REFRESH_SECRET_KEY=<second value from step 1>

# --- Storage ---
STORAGE_BACKEND=s3
S3_ENDPOINT_URL=http://rustfs-mt:9000
S3_ACCESS_KEY=admin
S3_SECRET_KEY=admin
S3_BUCKET_NAME=workbench
S3_REGION=us-east-1

# --- Frontend build values (read by the per-tenant frontend services) ---
VITE_API_URL=https://your-host.example.org/api
VITE_DOCS_URL=https://your-host.example.org/docs
```

Or create it in one go:

```bash
cat > deploy/.env.multi-tenant <<'EOF'
POSTGRES_USER=postgres
POSTGRES_PASSWORD=change-me
POSTGRES_DB=phawmdb_mt
POSTGRES_HOST=localhost
POSTGRES_PORT=5433
PGADMIN_EMAIL=admin@example.com
PGADMIN_PASSWORD=change-me
RESEND_API_KEY=re_xxxxxxxxxxxxxxxxxxxx
FRONTEND_URL=https://your-host.example.org/workbench
IS_DEMO=FALSE
JWT_SECRET_KEY=replace-me
JWT_REFRESH_SECRET_KEY=replace-me
STORAGE_BACKEND=s3
S3_ENDPOINT_URL=http://rustfs-mt:9000
S3_ACCESS_KEY=admin
S3_SECRET_KEY=admin
S3_BUCKET_NAME=workbench
S3_REGION=us-east-1
VITE_API_URL=https://your-host.example.org/api
VITE_DOCS_URL=https://your-host.example.org/docs
EOF
```

Then replace the two `replace-me` values with your generated secrets.

### What each value does

| Variable | What to set it to |
|---|---|
| `POSTGRES_USER` / `POSTGRES_PASSWORD` | Database credentials |
| `POSTGRES_DB` | `phawmdb_mt` (keep distinct from the single-tenant `phawmdb`) |
| `POSTGRES_HOST` | Leave as `localhost` — see the note below |
| `POSTGRES_PORT` | `5433` for the multi-tenant database |
| `JWT_SECRET_KEY` | First value from step 1 |
| `JWT_REFRESH_SECRET_KEY` | Second value from step 1 — must **differ** from the above |
| `RESEND_API_KEY` | Your Resend key, for invitation and password-reset email |
| `FRONTEND_URL` | Public URL of the frontend; used in emailed links |
| `IS_DEMO` | `FALSE`. Dead config — the backend never reads it; only the frontend's `VITE_IS_DEMO` has any effect. |
| `S3_ACCESS_KEY` / `S3_SECRET_KEY` | RustFS credentials (`admin`/`admin` locally) |
| `VITE_API_URL` | Public API URL, passed as a **build arg** to each frontend ([§4](#4-frontend-installation)) |
| `VITE_DOCS_URL` | Public docs URL, likewise |

> **Never commit this file.** It holds your signing secrets and API key. Add
> `deploy/.env.multi-tenant` to the platform repo's `.gitignore` and share the
> values through whatever secret store your team uses.

> Leave `POSTGRES_HOST=localhost` in the file. Compose overrides it to
> `postgres-mt` inside the containers; the file's value is used only when you run
> scripts directly on your machine.

> For a purely local install, use `http://localhost:3000`, `http://127.0.0.1:8001`
> and `http://127.0.0.1:8080` for `FRONTEND_URL`, `VITE_API_URL` and
> `VITE_DOCS_URL` instead of the public URLs shown above.

---

## 3. Start the backend stack

### Choose your deployment type first

Out of the box, the `prestart` container creates three tenants — `phawm_sam`,
`phawm_annif` and `demo`. These are **PHAWM's own research deployments**, not
generic scaffolding: their seed data is specific to the SAM (attachment
monitoring) and Annif (subject indexing) applications, down to model URLs
pointing at those model servers. They also ship with shared test accounts.

| | Clean install | PHAWM install |
|---|---|---|
| For | Any organisation setting up their own workbench | Working with PHAWM's SAM / Annif research tenants |
| Built-in tenants | None — you create your own | `phawm_sam`, `phawm_annif`, `demo` |
| Test accounts | None | Two per tenant, shared password |
| Applications & models | You define your own | SAM and Annif pre-seeded |

**If you are setting up your own deployment, take the clean install.** It is the
default path through the rest of this guide; the PHAWM path is noted where it
differs.

### Clean install — skip the built-in tenants

Edit `deploy/docker-compose.multi-tenant.yml` and comment out the last line of
the `prestart` command block:

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
[§6](#6-add-a-tenant), which seeds everything a tenant actually requires.

Two more things to turn off for a non-demo deployment:

- **Optionally unregister the demo router.** `POST /demo/reset` drops a tenant's
  schema and re-seeds it, but only for the two tenants hardcoded in
  `RESETTABLE_TENANTS` (`demo` and `phawm_sam`), and only ever the caller's own
  tenant. **Tenants you create yourself can never be reset by it**, so on a clean
  install it is inert. Remove it anyway if you would rather not ship a
  destructive endpoint: in `backend/src/api/main.py`
  ([src/api/main.py](../../src/api/main.py) within the backend repo), drop `demo`
  from the imports and delete the `api_router.include_router(demo.router)` line.
- **Set `VITE_IS_DEMO=false`** in the frontend `.env` ([§4](#4-frontend-installation)).

> `IS_DEMO` in the backend env file is dead configuration — nothing in `src/`
> reads it. Only the frontend's `VITE_IS_DEMO` has any effect.

### Start it

```bash
docker compose -f deploy/docker-compose.multi-tenant.yml \
               --env-file deploy/.env.multi-tenant \
               up --build
```

This starts:

| Service | Host port | Purpose |
|---|---|---|
| `postgres-db-mt` | `5433` | PostgreSQL |
| `rustfs-mt` | `9000`, `9001` | Object storage (API, console) |
| `prestart-mt` | — | One-shot: creates the DB, migrates, prepares the public schema (and seeds the built-in tenants unless you disabled it above) |
| `api-mt` | `8001` | The backend API |
| `sam-attachment-monitor` | `8002` | SAM model server |
| `universal-llm-inference` | `8003` | Universal LLM server |
| `annif-subject-indexing` | `8004` | ANNIF classifier |
| `pyterrier-rag` | `8006` | PyTerrier retrieval / RAG |

> **`sam-api` currently fails to build** — its build context points outside the
> repo. To bring the stack up without it, list the services explicitly:
>
> ```bash
> docker compose -f deploy/docker-compose.multi-tenant.yml \
>                --env-file deploy/.env.multi-tenant \
>                up --build postgres-mt rustfs-mt prestart api-mt \
>                           universal-llm-api annif-api pyterrier-rag-api
> ```
>
> See [Multi-Tenant Deployment](multi_tenant_deployment.md#model-evaluation-services).

> **Stop the single-tenant stack first if it is running** — both bind RustFS on
> `9000`/`9001`.

The first run takes several minutes (image builds + migrations). Wait for
`prestart-mt` to finish and exit — on a PHAWM install it prints
`All PHAWM tenants ready.`; on a clean install it ends after the public schema
step.

### Verify the backend

```bash
curl http://localhost:8001/openapi.json | head -c 200
```

Interactive API docs: **<http://localhost:8001/docs>**

> Endpoints are served at the **root** — `/login/access-token`, not
> `/api/v1/login/access-token`. `API_V1_STR` is empty by default.

**Clean install:** no tenants exist yet — create yours in [§6](#6-add-a-tenant),
then come back to the frontend.

**PHAWM install:** three tenants are provisioned automatically — `phawm_sam`,
`phawm_annif`, `demo`.

Check which tenants exist:

```bash
docker exec -it postgres-db-mt psql -U postgres -d phawmdb_mt \
  -c "SELECT id, display_name FROM public.tenant;"
```

---

## 4. Frontend installation

The frontend runs as part of the compose stack. There is nothing to install by
hand — no `npm install`, no separate build. You add a service to the compose
file and a route to the Caddyfile, and `docker compose up` does the rest.

**`VITE_TENANT_ID` is compiled into the bundle at build time**, so there is one
frontend service per tenant.

### Step 1 — Add a service to `deploy/docker-compose.yml`

One block per tenant. Copy it, change the two names and the tenant id:

```yaml
  phawm-test-frontend:
    build:
      context: ../frontend          # the frontend submodule
      dockerfile: Dockerfile
      args:
        - VITE_TENANT_ID=phawm_test
        - VITE_IS_DEMO=false
        - VITE_API_URL=${VITE_API_URL}
        - VITE_DOCS_URL=${VITE_DOCS_URL}
    container_name: phawm-test-frontend
    restart: unless-stopped
    networks: [platform-network]
```

> **The tenant id uses underscores** (`phawm_test`) because it is a Postgres
> schema name. Service and container names use hyphens by convention.

> **Every `VITE_*` value must be under `args:`, not `environment:`.** Vite
> substitutes `import.meta.env.*` when the bundle is compiled, so a value set
> only at runtime never reaches the JavaScript — `VITE_API_URL` would compile to
> `undefined` and every API call would fail. The frontend `Dockerfile` must
> declare a matching `ARG` for each one; a build arg with no `ARG` is silently
> ignored.

No `ports:` entry is needed — Caddy reaches the container by name on
`platform-network`.

### Step 2 — Add a route to `deploy/caddy/Caddyfile`

```caddy
handle_path /workbench/phawm_test* {
  reverse_proxy phawm-test-frontend:3000
}
```

The path must match the tenant id, because the build sets its base path to
`/workbench/<tenant_id>/`.

### Step 3 — Bring it up

```bash
docker compose -f deploy/docker-compose.yml up -d --build phawm-test-frontend
docker compose -f deploy/docker-compose.yml restart caddy
```

That is the whole process. The frontend values come from
`deploy/.env.multi-tenant` ([§2](#2-backend-configuration)):

| Variable | Meaning |
|---|---|
| `VITE_API_URL` | Public API URL. No `/api/v1` suffix. |
| `VITE_DOCS_URL` | Where these docs are served |
| `VITE_IS_DEMO` | Leave `false`. `true` only enables the demo-reset button on the profile page. |
| `VITE_TENANT_ID` | Set per service in the compose block above, not in the env file. |

> **One image per environment.** Because the API URL is compiled in, a staging
> image cannot be promoted to production by changing environment variables —
> each environment needs its own build.

---

## 5. First login

**Clean install:** log in at <http://localhost:3000> with the admin account you
created in [§6](#6-add-a-tenant). The frontend sends
`X-Tenant-ID: <your tenant>` on the login request; the returned JWT carries the
tenant in its `tid` claim, so later requests need no header.

**PHAWM install:** the three seeded tenants each ship with two test accounts,
created by the seed migration:

| Email | Role | Password |
|---|---|---|
| `test-audit-instigator@company.com` | audit instigator | `password123` |
| `test-auditor@company.com` | auditor | `password123` |

> **Remove the test accounts before exposing a deployment.** They exist in
> **every seeded tenant** with the same well-known password. Delete or disable
> them on anything reachable from a network — see
> [Creating & Managing Tenants](managing_tenants.md). A clean install never
> creates them.

To add another account to an existing tenant:

```bash
cd ../workbench-backend
ENV_FILE=deploy/.env.multi-tenant \
POSTGRES_HOST=127.0.0.1 POSTGRES_PORT=5433 \
python scripts/create_user.py \
  --tenant   phawm_test \
  --email    you@phawm.org \
  --name     "Your Name" \
  --username you \
  --password "SecurePassword1!" \
  --admin
```

---

## 6. Add a tenant

Adding a tenant is **two steps**: create it in the backend, then build a frontend
for it. On a clean install this is how you create your *first* tenant too —
there is nothing special about it.

### Step 1 — Create the tenant and its admin

```bash
cd backend      # the scripts and their env file live in the backend submodule
ENV_FILE=deploy/.env.multi-tenant \
POSTGRES_HOST=127.0.0.1 POSTGRES_PORT=5433 \
python scripts/create_tenant.py \
  --id phawm_test \
  --name "PHAWM Test" \
  --email contact@phawm.org \
  --admin-email admin@phawm.org \
  --admin-name "Your Name" \
  --admin-username admin \
  --admin-password "SecurePassword1!"
```

This registers the tenant, creates its Postgres schema, runs every migration
inside it, seeds reference data, and creates the first admin user. `--id` becomes
the schema name and must be lowercase (`^[a-z][a-z0-9_]{0,62}$`).

Run it from the host with the venv active, or inside the container:

```bash
docker exec -it api-mt python scripts/create_tenant.py --id ... # (env already set)
```

**What the tenant gets:** audit roles (`audit_instigator`, `auditor` — required,
since audit creation depends on them), 23 event categories, 6 taxonomy groups,
23 taxonomy mappings, and the admin user.

**What it does not get:** applications, models, datasets, events, metrics or
audits. That is deliberate — the built-in tenants' seed data is specific to the
SAM and Annif applications, including model URLs pointing at those servers.
Your admin defines your own applications and audits through the UI. See
[What you get — and what you don't](multi_tenant_deployment.md#what-you-get-and-what-you-dont).

### Step 2 — Build a frontend for the tenant

Because `VITE_TENANT_ID` is compiled in, each tenant needs its own frontend
service. Add one to `deploy/docker-compose.yml`:

```yaml
  phawm-test-frontend:
    build:
      context: ../frontend
      dockerfile: Dockerfile
      args:
        - VITE_TENANT_ID=phawm_test
        - VITE_IS_DEMO=false
        - VITE_API_URL=${VITE_API_URL}
        - VITE_DOCS_URL=${VITE_DOCS_URL}
    container_name: phawm-test-frontend
    restart: unless-stopped
    networks: [platform-network]
```

And a route to `deploy/caddy/Caddyfile`:

```caddy
handle_path /workbench/phawm_test* {
  reverse_proxy phawm-test-frontend:3000
}
```

Then bring it up:

```bash
docker compose -f deploy/docker-compose.yml up -d --build phawm-test-frontend
docker compose -f deploy/docker-compose.yml restart caddy
```

The app is then served under `/workbench/phawm_test/`. See
[§4](#4-frontend-installation) for the details.

### Step 3 — Verify

```bash
# tenant is registered
PGPASSWORD=password psql -h localhost -p 5433 -U postgres -d phawmdb_mt \
  -c "SELECT id, display_name, db_schema FROM public.tenant;"

# login works
curl -X POST http://localhost:8001/login/access-token \
  -H "X-Tenant-ID: phawm_test" \
  -d "username=admin@phawm.org&password=SecurePassword1!"
```

A token in the response means the tenant is live.

### Adding more users

```bash
ENV_FILE=deploy/.env.multi-tenant \
POSTGRES_HOST=127.0.0.1 POSTGRES_PORT=5433 \
python scripts/create_user.py \
  --tenant   phawm_test \
  --email    john@phawm.org \
  --name     "John Roe" \
  --username jroe \
  --password "SecurePassword1!"
```

Add `--admin` to grant `tenant_admin`. See
[Creating & Managing Tenants](managing_tenants.md) for removal, promotion, and
psql recipes.

---

## 7. Single-tenant install

For local development against one schema:

```bash
cd <platform-repo>
docker compose -f deploy/docker-compose.yml --env-file deploy/.env up --build
```

Differences from multi-tenant:

| | Single-tenant | Multi-tenant |
|---|---|---|
| API | `8000` | `8001` |
| Postgres | `5432` / `phawmdb` | `5433` / `phawmdb_mt` |
| pgAdmin | `5050` | not included |
| `VITE_TENANT_ID` | leave empty | set per tenant |
| `VITE_API_URL` | `http://127.0.0.1:8000` | `http://127.0.0.1:8001` |

> **Known issue.** `deploy/docker-compose.yml` maps `8000:80`, but the Dockerfile
> now runs uvicorn on **8080**, so nothing answers on port 8000. Until it is
> fixed, change the mapping to `"8000:8080"`.

---

## 8. Troubleshooting

**Frontend loads but every request fails.** Check `VITE_API_URL` — the port must
match the stack you started (`8001` multi-tenant, `8000` single-tenant), with no
`/api/v1` suffix. Vite only reads `.env` at startup, so restart after editing.

**Login returns "X-Tenant-ID header required".** `VITE_TENANT_ID` is empty in the
build being served. Set it and rebuild.

**The frontend image fails to build.** The frontend `Dockerfile` runs
`npm install --force` itself; the `--force` flag is required because of
peer-dependency conflicts under React 19. If you have removed it, put it back.

**A tenant's frontend returns 404 through Caddy.** The `handle_path` route must
match the tenant id exactly, and the `reverse_proxy` target must be the
container name from the compose file. After editing the Caddyfile, restart
Caddy — it does not reload on its own.

**Only the `public` schema exists after startup.** On a **clean install this is
correct** — no tenants exist until you create one in [§6](#6-add-a-tenant). On a
PHAWM install it means `prestart-mt` failed; check `docker logs prestart-mt`.
Usually RustFS was not ready, and re-running compose succeeds.

**Login fails with "tenant not found" or 403.** The tenant in `VITE_TENANT_ID`
does not exist in the registry. List what does exist:

```bash
docker exec -it postgres-db-mt psql -U postgres -d phawmdb_mt \
  -c "SELECT id FROM public.tenant;"
```

The value in the frontend `.env` must match one of those ids exactly.

**The built-in tenants came back after you removed them.** The `prestart`
container re-runs `init_default_tenant.py` on every `up` unless you commented
that line out of the compose file — see [§3](#3-start-the-backend-stack).
Removing the tenants from the database alone is not enough.

**Port already in use.** The single-tenant and multi-tenant stacks share RustFS
ports `9000`/`9001`. Stop one before starting the other.

**Model calls fail from the API container.** A model's `location` still says
`localhost`. Inside Docker it must be the container name, e.g.
`http://universal-llm-inference:8003`.

---

## Where to go next

- [Multi-Tenant Deployment](multi_tenant_deployment.md) — the full deployment reference
- [Creating & Managing Tenants](managing_tenants.md) — day-to-day tenant administration
- [Configuration](../backend/configuration.md) — every backend environment variable
- [Multi-Tenancy Architecture](../backend/multi_tenancy.md) — how isolation and permissions work
