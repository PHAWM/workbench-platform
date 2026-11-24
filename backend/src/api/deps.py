from collections.abc import Generator
from typing import Annotated, Optional

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from jwt.exceptions import InvalidTokenError
from pydantic import ValidationError
from sqlmodel import Session, select

from src.core import security
from src.core.config import settings
from src.database import engine, get_tenant_engine, get_tenant_schema_from_request
from src.models import TokenPayload, User, UserRoles, MappingAuditUser, AuditRoles

reusable_oauth2 = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/login/access-token"
)

# ---------------------------------------------------------------------------
# Session dependencies
# ---------------------------------------------------------------------------

def get_db() -> Generator[Session, None, None]:
    """Public-schema session — tenant registry and superuser ops only."""
    with Session(engine) as session:
        yield session


def get_tenant_db(request: Request) -> Generator[Session, None, None]:
    """
    Tenant-aware session used by route handlers via SessionDep.

    Resolution order:
      1. X-Tenant-ID header — used by unauthenticated routes (signup, verify-email)
         where no token is available yet.
      2. Bearer token tid claim — used by all authenticated routes so the session
         schema always matches the token without requiring the client to repeat the
         header on every request.
      3. Falls back to public schema (superuser ops, no tenant context).
    """
    # 1. Explicit header (unauthenticated flows)
    schema = get_tenant_schema_from_request(request)

    # 2. Extract from Bearer token when header is absent
    if not schema:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            raw_token = auth_header[len("Bearer "):]
            try:
                payload = jwt.decode(
                    raw_token, settings.JWT_SECRET_KEY, algorithms=[security.ALGORITHM]
                )
                schema = payload.get("tid")
            except Exception:
                pass  # Invalid token handled later by get_current_user

    if schema:
        try:
            tenant_engine = get_tenant_engine(schema)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid tenant: {schema!r}")
        with Session(tenant_engine) as session:
            yield session
    else:
        with Session(engine) as session:
            yield session


def _session_from_token(token: str) -> Generator[Session, None, None]:
    """
    Decode the JWT, extract the tenant schema (tid claim), and return a
    session scoped to that schema.  Superusers have no tid → public schema.
    Raises HTTP 403 on invalid tokens before any DB call.
    """
    try:
        payload = jwt.decode(
            token, settings.JWT_SECRET_KEY, algorithms=[security.ALGORITHM]
        )
        token_data = TokenPayload(**payload)
    except (InvalidTokenError, ValidationError):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Could not validate credentials",
        )

    schema = token_data.tid
    if schema:
        try:
            tenant_engine = get_tenant_engine(schema)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid tenant in token: {schema!r}")
        with Session(tenant_engine) as session:
            yield session
    else:
        with Session(engine) as session:
            yield session


SessionDep = Annotated[Session, Depends(get_tenant_db)]
TokenDep = Annotated[str, Depends(reusable_oauth2)]

# ---------------------------------------------------------------------------
# User resolution
# ---------------------------------------------------------------------------

def get_current_user(token: TokenDep) -> User:
    """
    Decode the JWT, open a session on the correct tenant schema (from the
    token's tid claim), and return the authenticated User.
    Superusers have no tid and are looked up in the public schema.
    """
    try:
        payload = jwt.decode(
            token, settings.JWT_SECRET_KEY, algorithms=[security.ALGORITHM]
        )
        token_data = TokenPayload(**payload)
    except (InvalidTokenError, ValidationError):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Could not validate credentials",
        )

    schema = token_data.tid
    if schema:
        try:
            tenant_engine = get_tenant_engine(schema)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid tenant in token: {schema!r}")
        session_ctx = Session(tenant_engine)
    else:
        session_ctx = Session(engine)

    with session_ctx as session:
        user = session.get(User, token_data.sub)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        if not user.is_active:
            raise HTTPException(status_code=400, detail="Inactive user")
        # Detach from session so the object can be used outside the with-block
        session.expunge(user)
        return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def get_current_tenant_id(token: TokenDep) -> Optional[str]:
    """Return the tenant schema name (tid) from the Bearer token, or None for superusers."""
    try:
        payload = jwt.decode(
            token, settings.JWT_SECRET_KEY, algorithms=[security.ALGORITHM]
        )
        return TokenPayload(**payload).tid
    except (InvalidTokenError, ValidationError):
        return None


def get_current_active_superuser(current_user: CurrentUser) -> User:
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=403, detail="The user doesn't have enough privileges"
        )
    return current_user


# ---------------------------------------------------------------------------
# Tenant-admin dependency
# Checks UserRoles.permissions["tenant_admin"] == True for the current user.
# ---------------------------------------------------------------------------

def get_tenant_admin(token: TokenDep, current_user: CurrentUser) -> User:
    """
    Allow access if the user is a superuser OR holds the tenant_admin permission.
    Use this for within-tenant management actions (invite users, manage tenant users).
    """
    if current_user.is_superuser:
        return current_user

    try:
        payload = jwt.decode(
            token, settings.JWT_SECRET_KEY, algorithms=[security.ALGORITHM]
        )
        token_data = TokenPayload(**payload)
    except (InvalidTokenError, ValidationError):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Could not validate credentials")

    schema = token_data.tid
    if not schema:
        raise HTTPException(status_code=403, detail="No tenant context in token")

    try:
        tenant_engine = get_tenant_engine(schema)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid tenant in token: {schema!r}")

    with Session(tenant_engine) as session:
        role = session.exec(
            select(UserRoles).where(UserRoles.user_id == current_user.id)
        ).first()

    if not role or not role.permissions.get("tenant_admin"):
        raise HTTPException(status_code=403, detail="Tenant admin role required")

    return current_user


TenantAdmin = Annotated[User, Depends(get_tenant_admin)]


def _get_tenant_session(token: str) -> Session:
    """
    Open and return a session scoped to the tenant embedded in the token.
    Caller is responsible for closing it (use as a context manager).
    """
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[security.ALGORITHM])
        token_data = TokenPayload(**payload)
    except (InvalidTokenError, ValidationError):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Could not validate credentials")

    schema = token_data.tid
    if schema:
        try:
            return Session(get_tenant_engine(schema))
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid tenant in token: {schema!r}")
    return Session(engine)


def get_current_instigator_or_superuser(
    token: TokenDep,
    current_user: CurrentUser,
) -> User:
    """
    Allow access if the user is a superuser, a tenant admin, OR holds the
    audit_instigator role on at least one audit.

    Tenant admins are treated as instigators because in practice they are the
    same person — the admin sets up the platform and creates audits.  Without
    this, a tenant admin would be blocked from model/dataset management until
    they had created their first audit.
    """
    if current_user.is_superuser:
        return current_user

    with _get_tenant_session(token) as session:
        # Pass if tenant admin
        role = session.exec(
            select(UserRoles).where(UserRoles.user_id == current_user.id)
        ).first()
        if role and role.permissions.get("tenant_admin"):
            return current_user

        # Pass if audit instigator on any audit
        is_instigator = session.exec(
            select(MappingAuditUser)
            .join(AuditRoles, AuditRoles.id == MappingAuditUser.roles_id)
            .where(
                MappingAuditUser.user_id == current_user.id,
                AuditRoles.role == "audit_instigator",
            )
        ).first()

    if not is_instigator:
        raise HTTPException(
            status_code=403,
            detail="Audit instigator or tenant admin role required",
        )
    return current_user


def get_audit_instigator_access(
    audit_id: int,
    token: TokenDep,
    current_user=Depends(get_current_user),
):
    """Verify user is the audit_instigator for the specified audit, or a tenant admin.

    Tenant admins are treated as instigators on all audits — they own the
    platform and should have full control over every audit in their schema.
    """
    with _get_tenant_session(token) as session:
        # Tenant admins pass unconditionally
        role = session.exec(
            select(UserRoles).where(UserRoles.user_id == current_user.id)
        ).first()
        if role and role.permissions.get("tenant_admin"):
            return role

        user_access = session.exec(
            select(MappingAuditUser)
            .join(AuditRoles, AuditRoles.id == MappingAuditUser.roles_id)
            .where(
                MappingAuditUser.audit_id == audit_id,
                MappingAuditUser.user_id == current_user.id,
                AuditRoles.role == "audit_instigator",
            )
        ).first()

    if not user_access:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the audit instigator or tenant admin can perform this action",
        )
    return user_access


def get_audit_access(
    audit_id: int,
    token: TokenDep,
    current_user=Depends(get_current_user),
):
    """Verify user has any role on the specified audit."""
    try:
        with _get_tenant_session(token) as session:
            user_access = session.exec(
                select(MappingAuditUser)
                .where(
                    MappingAuditUser.audit_id == audit_id,
                    MappingAuditUser.user_id == current_user.id,
                )
            ).first()

        if not user_access:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this audit",
            )
        return user_access
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to verify audit access",
        )