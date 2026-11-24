# Authentication

## Overview

The Authentication API provides secure login, password recovery, and password reset functionality. It implements OAuth2-compatible token-based authentication using JWT tokens with configurable expiration times.

The platform is multi-tenant. Each tenant user must identify their organisation on login via the `X-Tenant-ID` header. The issued JWT embeds the tenant context so no further headers are needed on subsequent requests. See [multi_tenancy.md](multi_tenancy.md) for the full tenancy model.

**Base Path:** `/` (no prefix)

**Authentication:** Login endpoint provides tokens; password recovery/reset endpoints require valid tokens or reset tokens

---

## Endpoints

### 1. Login Access Token

**Endpoint:** `POST /login/access-token`

**Description:** OAuth2 compatible token login endpoint that returns an access token for authenticated requests.

**Content-Type:** `application/x-www-form-urlencoded`

**Headers:**

| Header | Required | Description |
|---|---|---|
| `X-Tenant-ID` | Yes (tenant users) | Tenant identifier, e.g. `uni_glasgow`. Omit only for superuser login. |

**Request Body (Form Data):**
```
username=user@example.com
password=userpassword
```

**Tenant user example:**
```bash
curl -X POST "/login/access-token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -H "X-Tenant-ID: uni_glasgow" \
  -d "username=user@uni-glasgow.ac.uk&password=userpassword"
```

**Superuser example (no tenant header):**
```bash
curl -X POST "/login/access-token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin@platform.com&password=adminpassword"
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

The JWT payload contains:
- `sub` — user UUID
- `tid` — tenant schema name (absent for superusers)
- `exp` — expiry timestamp

**Status Codes:**

- `200`: Successfully authenticated, token returned
- `400`: Invalid credentials, inactive user, unverified email, unknown tenant, or missing `X-Tenant-ID` for a non-superuser

**Error Responses:**
```json
{ "detail": "Incorrect email or password" }
```
```json
{ "detail": "Inactive user" }
```
```json
{ "detail": "User not verified. Please check your email." }
```
```json
{ "detail": "Unknown tenant" }
```
```json
{ "detail": "Tenant is inactive" }
```
```json
{ "detail": "X-Tenant-ID header required for non-superuser login" }
```

**Usage:**
The returned access token must be included in all subsequent API requests. No `X-Tenant-ID` header is needed after login — the tenant is read from the token automatically.
```
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

**Token Expiration:**

- Token expiration is configurable via `ACCESS_TOKEN_EXPIRE_MINUTES` setting
- Default expiration time varies based on application configuration

---

### 2. Password Recovery

**Endpoint:** `POST /password-recovery/{email}`

**Description:** Initiates password recovery process for a registered user by generating a password reset token.

**Path Parameters:**

- `email` (str, required): Email address of the user requesting password recovery

**Response:**
```json
{
  "message": "Password recovery email sent"
}
```

**Status Codes:**

- `200`: Password recovery email sent successfully
- `404`: User with provided email does not exist

**Error Response:**
```json
{
  "detail": "The user with this email does not exist in the system."
}
```

**Process Flow:**
1. System validates that user exists with provided email
2. Generates a secure password reset token
3. Returns success message (actual email sending would be handled by external service)
4. Token can be used with the reset password endpoint

**Security Notes:**

- Always returns success message even for non-existent emails (to prevent email enumeration)
- Reset tokens have limited validity period
- Tokens are cryptographically secure and single-use

---

### 3. Reset Password

**Endpoint:** `POST /reset-password/`

**Description:** Resets user password using a valid password reset token obtained from the password recovery process.

**Request Body:**
```json
{
  "token": "secure-reset-token-from-email",
  "new_password": "NewSecurePassword123!"
}
```

**Request Parameters:**

- `token` (str, required): Valid password reset token from password recovery
- `new_password` (str, required): New password (minimum 10 characters, maximum 40 characters)

**Response:**
```json
{
  "message": "Password updated successfully"
}
```

**Status Codes:**

- `200`: Password successfully updated
- `400`: Invalid or expired token
- `404`: User does not exist
- `400`: User account is inactive

**Error Responses:**
```json
{
  "detail": "Invalid token"
}
```

```json
{
  "detail": "The user with this email does not exist in the system."
}
```

```json
{
  "detail": "Inactive user"
}
```

**Security Features:**

- Password reset tokens are single-use and expire after a set time
- New passwords are securely hashed before storage
- Validates user account is active before allowing password reset
- Token validation prevents unauthorized password changes

---

### 4. Logout

**Endpoint:** `POST /logout`

**Description:** Logs out the current user. Since JWT tokens are stateless, this endpoint primarily serves for:
- Logging the logout action
- Future token blacklist implementation
- Confirming successful logout to the client

**Note:** The client should delete the stored access token after receiving this response.

**Authentication Required:** Yes (Bearer token)

**Request Headers:**
```
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

**Response:**
```json
{
  "message": "User user@example.com logged out successfully"
}
```

**Status Codes:**

- `200`: Successfully logged out
- `401`: Unauthorized (missing or invalid token)

**Usage Example:**
```bash
curl -X POST "/logout" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."

# Response:
# {
#   "message": "User user@example.com logged out successfully"
# }
```

**Client-Side Logout:**
After receiving a successful response, the client should:
1. Remove the access token from storage (localStorage, sessionStorage, cookies)
2. Clear any user state/session data
3. Redirect to the login page

---

## Data Models

### Token Response Model
```json
{
  "access_token": "string (JWT token)",
  "token_type": "string (always 'bearer')"
}
```

### Message Response Model
```json
{
  "message": "string (descriptive message)"
}
```

### NewPassword Request Model
```json
{
  "token": "string (required)",
  "new_password": "string (required, 10-40 characters)"
}
```

## Security Implementation

### Password Hashing
- Uses secure password hashing (bcrypt or similar)
- Passwords are never stored in plaintext
- Salt is automatically generated for each password

### JWT Token Security
- Tokens are signed with application secret key
- Include user identification and expiration claims
- Should be validated on every protected endpoint request

### Password Requirements
- Minimum length: 10 characters
- Maximum length: 40 characters
- Additional complexity requirements may be enforced at application level

### Token Management
- Access tokens have configurable expiration times
- Reset tokens are single-use and time-limited
- Token validation includes signature and expiration checks

## Usage Examples

### Login Flow
```bash
# 1. Login to get access token
curl -X POST "/login/access-token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=user@example.com&password=userpassword"

# Response:
# {
#   "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
#   "token_type": "bearer"
# }

# 2. Use token for authenticated requests
curl -X GET "/protected-endpoint" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

### Password Recovery Flow
```bash
# 1. Request password recovery
curl -X POST "/password-recovery/user@example.com"

# Response:
# {
#   "message": "Password recovery email sent"
# }

# 2. Use token from email to reset password
curl -X POST "/reset-password/" \
  -H "Content-Type: application/json" \
  -d '{
    "token": "reset-token-from-email",
    "new_password": "NewSecurePassword123!"
  }'

# Response:
# {
#   "message": "Password updated successfully"
# }
```

## Error Handling

### Authentication Errors
- **Invalid Credentials**: Wrong email/password combination
- **Inactive User**: Account exists but is deactivated
- **Missing Token**: Authorization header not provided
- **Invalid Token**: Token is malformed, expired, or invalid
- **Expired Token**: Token has passed expiration time

### Common HTTP Status Codes
- `200`: Success
- `400`: Bad Request (invalid data, inactive user, wrong credentials)
- `401`: Unauthorized (missing or invalid token)
- `404`: Not Found (user does not exist)
- `422`: Validation Error (malformed request data)

## Best Practices

### For API Clients
1. Store tokens securely (avoid localStorage for sensitive applications)
2. Implement token refresh logic before expiration
3. Handle 401 responses by redirecting to login
4. Use HTTPS for all authentication requests
5. Validate token expiration client-side when possible

### For Frontend Integration
1. Use secure storage mechanisms for tokens
2. Implement proper logout functionality (clear stored tokens)
3. Handle network errors gracefully during authentication
4. Provide clear feedback for authentication failures
5. Implement "remember me" functionality if needed

### Security Considerations
1. Always use HTTPS in production
2. Implement rate limiting on login attempts
3. Log authentication events for security monitoring
4. Consider implementing 2FA for sensitive applications
5. Regularly rotate secret keys used for JWT signing

## Configuration

### Environment Variables
- `ACCESS_TOKEN_EXPIRE_MINUTES`: Token expiration time in minutes
- `SECRET_KEY`: Secret key for JWT token signing
- `ALGORITHM`: Algorithm used for JWT token signing (typically HS256)

### Application Settings
The authentication system uses application settings for:
- Token expiration configuration
- Password hashing parameters
- Security key management
- Email service configuration (for password recovery)

---

**Note:** This API follows OAuth2 standards for token-based authentication, making it compatible with standard OAuth2 client libraries and tools.