# Multi-Tenancy

## Overview

The PHAWM Workbench supports multiple independent organisations (tenants) on a single deployment. Each tenant gets a fully isolated PostgreSQL schema — their users, audits, models, and all application data are stored separately and are never visible to other tenants.

The platform uses a **schema-per-tenant** model backed by PostgreSQL. A single database holds a `public` schema for platform-level records (the tenant registry and the superuser account) and one additional schema per tenant (e.g. `uni_glasgow`, `nhs_scotland`).

---

## Architecture

```
PostgreSQL database
├── public schema
│   ├── tenant          ← registry of all tenants
│   └── user            ← superuser only
│
├── uni_glasgow schema
│   ├── user            ← all users for this tenant
│   ├── audit
│   ├── modelmetadata
│   └── ... (all other tables)
│
└── nhs_scotland schema
    ├── user
    ├── audit
    └── ...
```

Every tenant schema contains the full set of application tables. Data in one schema is never queried when a session is scoped to another.

---

## Permission Hierarchy

There are four distinct permission levels:

```
Superuser  (public schema)
  └── Platform-level only: provision tenants, emergency access.
      Not a day-to-day operational account.

Tenant Admin  (UserRoles.permissions["tenant_admin"] = true)
  └── Within-tenant management: invite users, manage tenant members.
      Automatically assigned to the first user created in a tenant.

Audit Instigator  (AuditRoles via MappingAuditUser)
  └── Audit-level management: configure pipeline, run evaluation,
      invite auditors, manage audit settings.

Auditor  (AuditRoles via MappingAuditUser)
  └── Audit participation: submit responses, view results.
```

### Superuser

Stored in the `public` schema. Created manually by a platform operator. Used only for:
- Registering new tenants (`POST /tenants/`)
- Emergency access when a tenant admin is locked out

The superuser has no `X-Tenant-ID` and their JWT contains no `tid` claim. They operate exclusively on the public schema.

### Tenant Admin

Stored in the tenant schema inside `UserRoles.permissions` as a JSONB field:

```json
{ "tenant_admin": true }
```

One tenant admin is created automatically when a tenant is provisioned (see [Provisioning a Tenant](#provisioning-a-tenant)). They can:
- Invite new users to the tenant
- Manage existing tenant users

Checked in code via the `TenantAdmin` FastAPI dependency (`src/api/deps.py`).

### Audit Instigator / Auditor

Unchanged from the single-tenant design. Roles are stored in `MappingAuditUser` linked to `AuditRoles` and are scoped to a specific audit. See [authentication.md](authentication.md) for the full login flow.

---

## Login Flow

Tenant users supply `X-Tenant-ID` **only on login**. After that, the issued JWT embeds the tenant schema in a `tid` claim and all subsequent requests are routed automatically.

### Tenant user login

```
POST /login/access-token
Content-Type: application/x-www-form-urlencoded
X-Tenant-ID: uni_glasgow

username=user@uni-glasgow.ac.uk&password=...
```

Server steps:
1. Look up `uni_glasgow` in `public.tenant` — reject if missing or inactive.
2. Open a session on the `uni_glasgow` schema.
3. Authenticate the user (email + bcrypt password check).
4. Issue a JWT: `{ sub: "<user_uuid>", tid: "uni_glasgow", exp: ... }`.

All subsequent requests only need:
```
Authorization: Bearer <token>
```

The `tid` claim in the token tells every dependency which schema to use. No `X-Tenant-ID` header is needed after login.

### Superuser login

```
POST /login/access-token
Content-Type: application/x-www-form-urlencoded

username=admin@platform.com&password=...
```

No `X-Tenant-ID` header. The server verifies `is_superuser=True` and issues a JWT with no `tid` claim. All queries run against the public schema.

---

## Session Routing

`SessionDep` (used by route handlers) resolves the correct schema in this order:

1. **`X-Tenant-ID` header** — for unauthenticated routes (`/signup`, `/verify-email`) where no token exists yet.
2. **`tid` claim in the Bearer token** — for all authenticated routes. Schema is read directly from the token; no header is required.
3. **Public schema fallback** — for superuser routes and any request with no tenant context.

This means existing route handlers (`session: SessionDep`) work without any changes — the session automatically targets the right schema.

---

## Provisioning a Tenant

Only a superuser can create a tenant. The `POST /tenants/` endpoint is atomic: it registers the tenant, provisions the Postgres schema (running all Alembic migrations), and creates the first tenant admin user in one request.

**Request:**
```http
POST /tenants/
Authorization: Bearer <superuser_token>
Content-Type: application/json

{
  "tenant": {
    "id": "uni_glasgow",
    "display_name": "University of Glasgow",
    "contact_email": "admin@uni-glasgow.ac.uk"
  },
  "admin": {
    "email": "jane.smith@uni-glasgow.ac.uk",
    "full_name": "Jane Smith",
    "username": "jsmith",
    "password": "SecurePassword1!",
    "organisation": "University of Glasgow"
  }
}
```

**Response:**
```json
{
  "tenant": {
    "id": "uni_glasgow",
    "display_name": "University of Glasgow",
    "db_schema": "uni_glasgow",
    "is_active": true,
    "contact_email": "admin@uni-glasgow.ac.uk"
  },
  "admin": {
    "email": "jane.smith@uni-glasgow.ac.uk",
    "full_name": "Jane Smith",
    "username": "jsmith",
    "organisation": "University of Glasgow",
    "is_superuser": false
  }
}
```

What happens internally:
1. A `Tenant` record is inserted into `public.tenant`.
2. `CREATE SCHEMA IF NOT EXISTS "uni_glasgow"` is executed.
3. Alembic migrations run against the new schema, creating all tables.
4. A `User` is created in `uni_glasgow.user` with `is_verified=True`.
5. A `UserRoles` record is created: `permissions = {"tenant_admin": true}`.

If schema provisioning fails, the `Tenant` registry entry is rolled back. If the admin user creation fails after the schema is provisioned, the schema remains (it is still usable) and a `500` error is returned describing the failure.

---

## Inviting Users to a Tenant

The tenant admin invites additional users via the existing user invitation flow. The session is automatically scoped to the tenant schema from the admin's token, so invited users are created in the correct schema.

The invitation flow is unchanged:
1. Tenant admin calls the invite endpoint with the new user's email.
2. If the user does not exist, a placeholder account is created and a 7-day invitation token is emailed.
3. The invitee calls `POST /users/set-password-with-invite` with their token and chosen password.
4. On their first login they supply `X-Tenant-ID: uni_glasgow` to get a tenant-scoped JWT.

---

## Tenant Deactivation

```http
DELETE /tenants/{tenant_id}
Authorization: Bearer <superuser_token>
```

Sets `Tenant.is_active = False`. The schema and all its data are preserved — no data is deleted. Deactivated tenants cannot be logged into (the login endpoint rejects them with `400 Tenant is inactive`).

---

## Data Models

### Tenant (public schema)

| Field | Type | Description |
|---|---|---|
| `id` | string (PK) | Slug identifier, e.g. `uni_glasgow` |
| `display_name` | string | Human-readable name |
| `db_schema` | string | Postgres schema name (derived from `id`) |
| `is_active` | bool | Whether tenant can log in |
| `contact_email` | string (optional) | Contact for the tenant |

### UserRoles (tenant schema)

| Field | Type | Description |
|---|---|---|
| `id` | int (PK) | |
| `user_id` | UUID (FK → user.id) | |
| `permissions` | JSONB | e.g. `{"tenant_admin": true}` |

### JWT Payload

| Claim | Description |
|---|---|
| `sub` | User UUID |
| `tid` | Tenant schema name (absent for superusers) |
| `exp` | Expiry timestamp |

---

## FastAPI Dependencies

| Dependency | Location | Purpose |
|---|---|---|
| `SessionDep` | `deps.py` | Tenant-scoped DB session (auto-resolved from token or header) |
| `CurrentUser` | `deps.py` | Authenticated user from JWT, session opened on correct schema |
| `TenantAdmin` | `deps.py` | Requires `permissions["tenant_admin"] == true` or superuser |
| `get_current_active_superuser` | `deps.py` | Requires `is_superuser == true` |
| `get_audit_instigator_access` | `deps.py` | Requires `audit_instigator` role on a specific audit |
| `get_audit_access` | `deps.py` | Requires any role on a specific audit |

---

## Frontend Integration

Each tenant gets its **own frontend build**, served at its own path prefix:

- `https://example.org/workbench/uni_glasgow/`
- `https://example.org/workbench/demo/`

The tenant id is a **build-time constant**, not derived from the URL at runtime.
`VITE_TENANT_ID` is passed as a Docker build arg and inlined by Vite into the
bundle, where it sets two things: the `X-Tenant-ID` login header, and the app's
base path (`vite.config.js` sets `base` to `/workbench/<tenantId>/`, and
`App.jsx` uses the same value as the router basename). An empty value means the
root path and no tenant header — used for superuser access and local
development.

Because the value is compiled in, **changing a tenant id requires rebuilding the
frontend image**; setting the environment variable on a running container has no
effect on the bundle. Serving several tenants from one host means a reverse proxy
routing each `/workbench/<tenant_id>/` path to that tenant's build — see
[Multi-Tenant Deployment](../setup/multi_tenant_deployment.md).

The frontend sends `X-Tenant-ID` **only on the login request**. After receiving
the JWT it stores it and includes it as `Authorization: Bearer <token>` on all
subsequent requests; the `X-Tenant-ID` header is not needed again until the next
login. The backend lowercases the header before use, since clients and
invitation links have been observed sending mixed-case values.

```javascript
// Baked in at build time via VITE_TENANT_ID — null for superuser builds
const tenantId = import.meta.env.VITE_TENANT_ID || null;

// Login
const response = await fetch('/login/access-token', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/x-www-form-urlencoded',
    'X-Tenant-ID': tenantId,        // only needed here
  },
  body: new URLSearchParams({ username, password }),
});
const { access_token } = await response.json();

// All subsequent calls — no X-Tenant-ID needed
await fetch('/users/me', {
  headers: { 'Authorization': `Bearer ${access_token}` },
});
```
