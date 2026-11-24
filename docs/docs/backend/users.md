# Users API

## Overview

The Users API manages user accounts within a tenant. It covers self-service registration, email verification, invitation flows, password management, and profile updates, as well as superuser-only administrative operations.

**Base Path:** `/users`

**Authentication:** Most endpoints require a Bearer token. Unauthenticated endpoints (signup, verify-email, invite flows, forgot/reset-password) require an `X-Tenant-ID` header instead so the backend knows which tenant schema to operate against.

See [authentication.md](authentication.md) for the login flow and [multi_tenancy.md](multi_tenancy.md) for how tenant context is propagated.

---

## Endpoint Reference

### Self-service / Unauthenticated

These endpoints do not require a Bearer token but **must** include the `X-Tenant-ID` header.

---

#### POST `/users/signup`

Register a new user account within a tenant.

**Headers:**

| Header | Required | Description |
|---|---|---|
| `X-Tenant-ID` | Yes | Tenant the user is registering under, e.g. `uni_glasgow` |

**Request Body:**
```json
{
  "email": "jane@uni-glasgow.ac.uk",
  "username": "jsmith",
  "password": "SecurePass1!",
  "full_name": "Jane Smith",
  "ethnicity": "Not Specified",
  "gender": "Not Specified",
  "country": "Not Specified",
  "organisation": "Not Specified"
}
```

| Field | Type | Required | Constraints |
|---|---|---|---|
| `email` | string | Yes | Valid email, max 255 chars |
| `username` | string | Yes | |
| `password` | string | Yes | 8–40 characters |
| `full_name` | string | Yes | |
| `ethnicity` | string | No | Defaults to `"Not Specified"` |
| `gender` | string | No | Defaults to `"Not Specified"` |
| `country` | string | No | Defaults to `"Not Specified"` |
| `organisation` | string | No | Defaults to `"Not Specified"` |

**Response `200`:**
```json
{
  "email": "jane@uni-glasgow.ac.uk",
  "username": "jsmith",
  "full_name": "Jane Smith",
  "ethnicity": "Not Specified",
  "gender": "Not Specified",
  "country": "Not Specified",
  "organisation": "Not Specified",
  "is_superuser": false
}
```

A verification email is sent automatically. The user must verify their email before they can log in.

**Error Responses:**

| Status | Detail |
|---|---|
| `400` | `"The user with this email already exists in the system"` |

---

#### POST `/users/verify-email`

Verify a user's email address using the token from the verification email.

**Headers:**

| Header | Required | Description |
|---|---|---|
| `X-Tenant-ID` | Yes | Must match the tenant the user registered under |

**Query Parameters:**

| Parameter | Type | Required |
|---|---|---|
| `token` | string | Yes |

**Example:**
```bash
curl -X POST "/users/verify-email?token=abc123..." \
  -H "X-Tenant-ID: uni_glasgow"
```

**Response `200`:**
```json
{ "message": "Email verified successfully" }
```

**Error Responses:**

| Status | Detail |
|---|---|
| `400` | `"Invalid or expired verification token"` |

---

#### POST `/users/accept-invite`

Validate an invitation token and check whether the invited user has already set a password.

**Headers:**

| Header | Required | Description |
|---|---|---|
| `X-Tenant-ID` | Yes | Must match the tenant the invitation was issued from |

**Request Body:**
```json
{ "token": "invitation-token-from-email" }
```

**Response `200`:**
```json
{
  "message": "Invitation accepted successfully",
  "password_set": false,
  "user_email": "jane@uni-glasgow.ac.uk"
}
```

Use `password_set` to decide whether to show a set-password form or redirect to login.

**Error Responses:**

| Status | Detail |
|---|---|
| `400` | `"Invalid or expired invitation token"` |

---

#### POST `/users/set-password-with-invite`

Set the initial password for an invited user. Also marks the email as verified.

**Headers:**

| Header | Required | Description |
|---|---|---|
| `X-Tenant-ID` | Yes | Must match the tenant the invitation was issued from |

**Request Body:**
```json
{
  "token": "invitation-token-from-email",
  "password": "SecurePass1!"
}
```

| Field | Constraints |
|---|---|
| `password` | 8–40 characters |

**Response `200`:**
```json
{ "message": "Password set successfully. You can now login." }
```

**Error Responses:**

| Status | Detail |
|---|---|
| `400` | `"Invalid or expired invitation token"` |

---

#### POST `/users/forgot-password`

Request a password reset email. Always returns a success message regardless of whether the email is registered (prevents email enumeration).

**Headers:**

| Header | Required | Description |
|---|---|---|
| `X-Tenant-ID` | Yes | Scopes the reset to the correct tenant's user account |

**Request Body:**
```json
{ "email": "jane@uni-glasgow.ac.uk" }
```

**Response `200`:**
```json
{
  "message": "If an account exists with this email, you will receive password reset instructions."
}
```

Token is valid for **48 hours**.

---

#### POST `/users/reset-password`

Reset a user's password using the token from the reset email.

**Headers:**

| Header | Required | Description |
|---|---|---|
| `X-Tenant-ID` | Yes | Must match the tenant the reset token was issued for |

**Request Body:**
```json
{
  "token": "reset-token-from-email",
  "new_password": "NewSecurePass1!"
}
```

| Field | Constraints |
|---|---|
| `new_password` | 8–40 characters |

**Response `200`:**
```json
{ "message": "Password reset successfully. You can now login with your new password." }
```

**Error Responses:**

| Status | Detail |
|---|---|
| `400` | `"Invalid or expired password reset token"` |

---

### Authenticated — current user

These endpoints require a Bearer token. No `X-Tenant-ID` header is needed — tenant context is read from the token.

---

#### GET `/users/me`

Return the currently authenticated user's profile.

**Response `200`:**
```json
{
  "email": "jane@uni-glasgow.ac.uk",
  "username": "jsmith",
  "full_name": "Jane Smith",
  "ethnicity": "Not Specified",
  "gender": "Not Specified",
  "country": "Not Specified",
  "organisation": "University of Glasgow",
  "is_superuser": false
}
```

---

#### PATCH `/users/me`

Update the current user's profile fields. Only fields included in the request body are updated.

**Request Body** (all fields optional):
```json
{
  "full_name": "Jane A. Smith",
  "username": "jane_smith",
  "ethnicity": "White",
  "gender": "Female",
  "country": "United Kingdom",
  "organisation": "University of Glasgow"
}
```

**Response `200`:** Updated `UserPublic` object (same shape as `GET /users/me`).

---

#### PATCH `/users/me/password`

Change the current user's password. Requires the current password for verification.

**Request Body:**
```json
{
  "current_password": "OldPass1!",
  "new_password": "NewPass1!"
}
```

| Field | Constraints |
|---|---|
| `current_password` | 8–40 characters |
| `new_password` | 8–40 characters, must differ from current |

**Response `200`:**
```json
{ "message": "Password updated successfully" }
```

**Error Responses:**

| Status | Detail |
|---|---|
| `400` | `"Incorrect password"` |
| `400` | `"New password cannot be the same as the current one"` |

---

#### GET `/users/{user_id}/files/{filename}`

Download a file from a user's storage directory. Users can only access their own files; superusers can access any user's files.

**Path Parameters:**

| Parameter | Type | Description |
|---|---|---|
| `user_id` | UUID | Target user's ID |
| `filename` | string | File path relative to the user's storage root (supports subdirectories) |

**Response `200`:** File download (`application/octet-stream`).

**Error Responses:**

| Status | Detail |
|---|---|
| `403` | `"Not authorized to access this user's files"` |
| `404` | User or file not found |
| `400` | Invalid or directory-traversal file path |

---

#### GET `/users/{user_id}`

Get a specific user by ID. Users can retrieve their own record; superusers can retrieve any user.

**Path Parameters:**

| Parameter | Type |
|---|---|
| `user_id` | UUID |

**Response `200`:** `UserPublic` object.

**Error Responses:**

| Status | Detail |
|---|---|
| `403` | `"The user doesn't have enough privileges"` |

---

### Superuser only

These endpoints require a Bearer token from a superuser account (`is_superuser: true`).

---

#### GET `/users/`

List all users in the current schema. Supports pagination.

**Query Parameters:**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `skip` | int | `0` | Number of records to skip |
| `limit` | int | `100` | Maximum records to return |

**Response `200`:**
```json
{
  "data": [
    {
      "email": "jane@uni-glasgow.ac.uk",
      "username": "jsmith",
      "full_name": "Jane Smith",
      "ethnicity": "Not Specified",
      "gender": "Not Specified",
      "country": "Not Specified",
      "organisation": "University of Glasgow",
      "is_superuser": false
    }
  ],
  "count": 1
}
```

---

#### POST `/users/`

Create a new user directly (without the registration flow). Superuser only.

**Request Body:**
```json
{
  "email": "jane@uni-glasgow.ac.uk",
  "username": "jsmith",
  "password": "SecurePass1!",
  "full_name": "Jane Smith",
  "ethnicity": "Not Specified",
  "gender": "Not Specified",
  "country": "Not Specified",
  "organisation": "Not Specified",
  "is_active": true,
  "is_superuser": false,
  "is_verified": true
}
```

**Response `200`:** `UserPublic` object.

**Error Responses:**

| Status | Detail |
|---|---|
| `400` | `"The user with this email already exists in the system."` |

---

## Data Models

### UserPublic

Returned by all read endpoints.

```json
{
  "email": "string",
  "full_name": "string",
  "username": "string",
  "ethnicity": "string",
  "gender": "string",
  "country": "string",
  "organisation": "string",
  "is_superuser": false
}
```

### UserRegister

Used for `POST /users/signup`.

```json
{
  "email": "string (required)",
  "username": "string (required)",
  "password": "string (required, 8–40 chars)",
  "full_name": "string (required)",
  "ethnicity": "string (optional)",
  "gender": "string (optional)",
  "country": "string (optional)",
  "organisation": "string (optional)"
}
```

---

## Flow Diagrams

### Self-registration flow

```
Frontend                        Backend
   │                               │
   ├─ POST /users/signup ──────────►│  Creates user, sends verification email
   │   X-Tenant-ID: uni_glasgow    │
   │                               │
   │◄─ UserPublic ─────────────────┤
   │                               │
   │  (user clicks email link)     │
   │                               │
   ├─ POST /users/verify-email ────►│  Marks email as verified
   │   X-Tenant-ID: uni_glasgow    │
   │   ?token=...                  │
   │◄─ { message: "verified" } ────┤
   │                               │
   ├─ POST /login/access-token ────►│  Issues JWT with tid=uni_glasgow
   │◄─ { access_token: "..." } ────┤
```

### Invitation flow

```
Tenant admin                    Backend                         Invited user
     │                             │                                 │
     ├─ POST /invite ─────────────►│  Creates UserInvitation         │
     │                             ├─────── sends invite email ──────►│
     │                             │                                 │
     │                             │◄─ POST /users/accept-invite ───┤
     │                             │   X-Tenant-ID: uni_glasgow     │
     │                             │   { token: "..." }             │
     │                             ├─ { password_set: false } ──────►│
     │                             │                                 │
     │                             │◄─ POST /users/set-password ────┤
     │                             │   X-Tenant-ID: uni_glasgow     │
     │                             │   { token, password }          │
     │                             ├─ { message: "Password set" } ──►│
     │                             │                                 │
     │                             │◄─ POST /login/access-token ────┤
     │                             ├─ { access_token: "..." } ───────►│
```

### Password reset flow

```
Frontend                        Backend
   │                               │
   ├─ POST /users/forgot-password ►│  Sends reset email if account exists
   │   X-Tenant-ID: uni_glasgow   │
   │   { email: "..." }           │
   │◄─ { message: "..." } ────────┤
   │                               │
   │  (user clicks email link)     │
   │                               │
   ├─ POST /users/reset-password ─►│  Validates token, updates password
   │   X-Tenant-ID: uni_glasgow   │
   │   { token, new_password }    │
   │◄─ { message: "..." } ────────┤
```

---

## Security Notes

- **Email enumeration prevention:** `POST /users/forgot-password` always returns the same success message whether or not the email exists.
- **Directory traversal prevention:** `GET /users/{user_id}/files/{filename}` resolves the full path and checks it stays within the user's storage root before serving the file.
- **Token expiry:** Verification tokens expire after **7 days**. Invitation tokens expire after **7 days**. Password reset tokens expire after **48 hours**. All tokens are single-use.
- **X-Tenant-ID on unauthenticated routes:** Required so the backend routes the request to the correct tenant schema before a JWT is available.
