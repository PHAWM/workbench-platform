# Setup Guides

Step-by-step guides for deploying and configuring the PHAWM Workbench.

The deployment is multi-tenant: one PostgreSQL database with a `public` schema
for platform records and one schema per tenant, one frontend build per tenant,
all behind a Caddy reverse proxy. It is deployed from `deploy/docker-compose.yml`
in the platform repository, which pulls the backend and frontend in as git
submodules.

## Getting Started

- [Installation Guide](installation.md) — Install the whole workbench (API, database, storage, model servers, frontends) from a clean machine, and add your first tenant

## Deployment

- [Multi-Tenant Deployment](multi_tenant_deployment.md) — Deployment reference: configuration, services and ports, creating tenants, migrations, connecting to the database, and troubleshooting

## Architecture

- [Multi-Tenancy Architecture](../backend/multi_tenancy.md) — How schema-per-tenant isolation, tenant routing and the permission model work
- [Configuration](../backend/configuration.md) — Every backend environment variable
