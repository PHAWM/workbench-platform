# Setup and Configuration

This document describes all configuration options for the PHAWM Workbench Backend.

## Overview

The application uses Pydantic Settings for configuration management. Settings can be provided via:
1. Environment variables
2. `.env` file in the project root
3. Default values in code

**Configuration File:** `src/core/config.py`

---

## Environment Variables

### API Configuration

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `API_V1_STR` | string | `/api/v1` | Base path prefix for all API endpoints |
| `PROJECT_NAME` | string | `PHAWM workbench` | Application name used in responses and logs |

### JWT Authentication

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `JWT_SECRET_KEY` | string | Auto-generated | Secret key for signing access tokens. **Must be set in production** |
| `JWT_REFRESH_SECRET_KEY` | string | Auto-generated | Secret key for signing refresh tokens. **Must be set in production** |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | integer | `60` | Access token expiration time in minutes (1 hour) |
| `REFRESH_TOKEN_EXPIRE_MINUTES` | integer | `10080` | Refresh token expiration time in minutes (7 days) |

**Security Warning:** In production, always set `JWT_SECRET_KEY` and `JWT_REFRESH_SECRET_KEY` explicitly. The auto-generated keys change on every application restart, which will invalidate all existing tokens.

### Email Configuration

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `RESEND_API_KEY` | string | `""` | API key for [Resend](https://resend.com) email service |
| `EMAIL_FROM_NAME` | string | `PHAWM team` | Sender name for outgoing emails |
| `EMAIL_FROM_ADDRESS` | string | `noreply@workbench.phawm.org` | Sender email address |
| `EMAIL_RESET_TOKEN_EXPIRE_HOURS` | integer | `48` | Password reset token expiration in hours |

### Frontend & CORS Configuration

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `FRONTEND_URL` | string | `http://company.com` | Frontend application URL (used for email links) |
| `BACKEND_CORS_ORIGINS` | list | `["http://localhost:3000"]` | Allowed CORS origins |

---

## Example `.env` File

Create a `.env` file in the project root with your configuration:

```env
# API Settings
API_V1_STR=/api/v1
PROJECT_NAME=PHAWM Workbench

# JWT Settings (REQUIRED in production)
JWT_SECRET_KEY=your-super-secret-key-change-in-production
JWT_REFRESH_SECRET_KEY=your-refresh-secret-key-change-in-production
ACCESS_TOKEN_EXPIRE_MINUTES=60
REFRESH_TOKEN_EXPIRE_MINUTES=10080

# Email Settings
RESEND_API_KEY=re_your_resend_api_key
EMAIL_FROM_NAME=PHAWM Team
EMAIL_FROM_ADDRESS=noreply@yourdomain.com
EMAIL_RESET_TOKEN_EXPIRE_HOURS=48

# Frontend URL (for email links and redirects)
FRONTEND_URL=https://your-frontend-domain.com
```

---

## CORS Configuration

Cross-Origin Resource Sharing (CORS) is configured to allow requests from specified origins.

**Default Configuration:**
```python
BACKEND_CORS_ORIGINS: List[AnyHttpUrl] = [
    "http://localhost:3000",
]
```

**To add additional origins**, modify the `BACKEND_CORS_ORIGINS` in `config.py` or set them via environment variables:

```python
# Example: Multiple origins
BACKEND_CORS_ORIGINS = [
    "http://localhost:3000",
    "https://your-production-domain.com",
    "https://staging.your-domain.com"
]
```

---

## JWT Token Configuration

### Token Types

The application uses two types of JWT tokens:

1. **Access Token**
   - Short-lived token for API authentication
   - Default expiration: 60 minutes
   - Signed with `JWT_SECRET_KEY`

2. **Refresh Token**
   - Long-lived token for obtaining new access tokens
   - Default expiration: 7 days (10080 minutes)
   - Signed with `JWT_REFRESH_SECRET_KEY`

### Token Claims

Access tokens include the following claims:
- `sub`: User ID (UUID)
- `exp`: Expiration timestamp
- `iat`: Issued at timestamp

### Security Best Practices

1. **Generate Strong Secret Keys:**
   ```bash
   # Generate a secure random key
   python -c "import secrets; print(secrets.token_urlsafe(32))"
   ```

2. **Never commit secrets to version control**

3. **Use different keys for different environments** (development, staging, production)

4. **Rotate keys periodically** in production

---

## Email Service Configuration

The application uses [Resend](https://resend.com) for sending emails (password recovery, invitations, etc.).

### Setup Steps

1. Create an account at [resend.com](https://resend.com)
2. Verify your sending domain
3. Generate an API key
4. Set the `RESEND_API_KEY` environment variable

### Email Templates

The following email types are sent:
- Password recovery emails
- User invitation emails
- Email verification emails

Email templates are located in `src/services/email_service.py`.

---

## Database Configuration

Database configuration is handled separately via SQLModel/SQLAlchemy. See your database connection settings in the appropriate configuration files.

---

## Model Service Configuration

The model service runs on separate ports:

| Service | Default Port | Description |
|---------|--------------|-------------|
| SAM (School Attachment Monitor) | 8002 | Audio/text attachment prediction |
| Universal LLM | 8003 | Multi-provider LLM inference |
| ANNIF | 8004 | Subject/topic prediction |

See [model_service.md](model_service.md) for detailed model service documentation.

---

## Production Deployment Checklist

Before deploying to production, ensure:

- [ ] `JWT_SECRET_KEY` is set to a strong, unique value
- [ ] `JWT_REFRESH_SECRET_KEY` is set to a strong, unique value
- [ ] `RESEND_API_KEY` is configured for email functionality
- [ ] `FRONTEND_URL` points to your production frontend
- [ ] `BACKEND_CORS_ORIGINS` includes only trusted origins
- [ ] All sensitive values are stored securely (environment variables, secrets manager)
- [ ] HTTPS is enabled for all endpoints
