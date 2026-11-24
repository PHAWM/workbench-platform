from datetime import timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel import Session, select

from src.core import security
from src.core.config import settings
from src.core.security import get_password_hash
from src.database import engine, get_tenant_engine
from src.models import Message, NewPassword, Token
from src.models.tenant import Tenant
from src.utils.utils import (
    generate_password_reset_token,
    verify_password_reset_token,
)
from src.services.user_service import authenticate, get_user_by_email

from src.api.deps import CurrentUser, SessionDep

router = APIRouter(tags=["login"])


@router.post("/login/access-token")
def login_access_token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    x_tenant_id: Annotated[str | None, Header()] = None,
) -> Token:
    """
    OAuth2 compatible token login.

    Tenant users must supply X-Tenant-ID matching their organisation's tenant.
    The issued JWT embeds the tenant schema (tid claim) so all subsequent
    requests are automatically routed to the correct schema — no header needed
    after login.

    Superusers omit X-Tenant-ID; their JWT has no tid claim and their session
    always operates on the public schema.
    """
    if x_tenant_id:
        # --- Tenant user login ---
        # Validate tenant exists and is active (public schema lookup)
        with Session(engine) as pub_session:
            tenant = pub_session.get(Tenant, x_tenant_id)

        if not tenant:
            raise HTTPException(status_code=400, detail="Unknown tenant")
        if not tenant.is_active:
            raise HTTPException(status_code=400, detail="Tenant is inactive")

        try:
            tenant_engine = get_tenant_engine(tenant.db_schema)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid tenant configuration")

        with Session(tenant_engine) as session:
            user = authenticate(session=session, email=form_data.username, password=form_data.password)
            if not user:
                raise HTTPException(status_code=400, detail="Incorrect email or password")
            if not user.is_active:
                raise HTTPException(status_code=400, detail="Inactive user")
            if not user.is_verified:
                raise HTTPException(status_code=400, detail="User not verified. Please check your email.")

        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        return Token(
            access_token=security.create_access_token(
                user.id,
                expires_delta=access_token_expires,
                tenant_id=tenant.db_schema,
            )
        )

    else:
        # --- Superuser login (no tenant context) ---
        with Session(engine) as session:
            user = authenticate(session=session, email=form_data.username, password=form_data.password)

        if not user:
            raise HTTPException(status_code=400, detail="Incorrect email or password")
        if not user.is_active:
            raise HTTPException(status_code=400, detail="Inactive user")
        if not user.is_superuser:
            # Regular users must supply X-Tenant-ID
            raise HTTPException(status_code=400, detail="X-Tenant-ID header required for non-superuser login")

        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        return Token(
            access_token=security.create_access_token(
                user.id,
                expires_delta=access_token_expires,
                # No tenant_id — superuser operates on public schema
            )
        )


@router.post("/password-recovery/{email}")
def recover_password(email: str, session: SessionDep) -> Message:
    """
    Password Recovery
    """
    user = get_user_by_email(session=session, email=email)

    if not user:
        raise HTTPException(
            status_code=404,
            detail="The user with this email does not exist in the system.",
        )
    password_reset_token = generate_password_reset_token(email=email)
    return Message(message="Password recovery email sent")


@router.post("/reset-password/")
def reset_password(session: SessionDep, body: NewPassword) -> Message:
    """
    Reset password
    """
    email = verify_password_reset_token(token=body.token)
    if not email:
        raise HTTPException(status_code=400, detail="Invalid token")
    user = get_user_by_email(session=session, email=email)
    if not user:
        raise HTTPException(
            status_code=404,
            detail="The user with this email does not exist in the system.",
        )
    elif not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    hashed_password = get_password_hash(password=body.new_password)
    user.hashed_password = hashed_password
    session.add(user)
    session.commit()
    return Message(message="Password updated successfully")


@router.post("/logout")
def logout(current_user: CurrentUser) -> Message:
    """
    Logout endpoint

    Note: Since this application uses JWT tokens, logout is primarily handled client-side
    by removing the token from storage. This endpoint can be used for:
    - Logging the logout action
    - Future token blacklist implementation
    - Confirming successful logout to the client

    The client should delete the access token after receiving this response.
    """
    return Message(message=f"User {current_user.email} logged out successfully")

