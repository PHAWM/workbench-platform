import uuid
import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlmodel import col, delete, func, select

from src.api.deps import (
    CurrentUser,
    SessionDep,
    get_current_active_superuser
)
from src.core.config import settings
from src.core.security import get_password_hash, verify_password
from src.models import (
    Message,
    UpdatePassword,
    User,
    UserCreate,
    UserPublic,
    UserProfileUpdate,
    UserRegister,
    UserUpdate,
    UsersPublic,
    AcceptInvite,
    AcceptInviteResponse,
    SetPasswordWithInvite,
    ForgotPassword,
    ResetPassword
)
from src.services import user_service
from src.services.email_service import send_verification_email, send_invitation_email, send_password_reset_email

router = APIRouter(prefix="/users", tags=["users"])

@router.get(
    "/",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=UsersPublic,
)
def read_users(session: SessionDep, skip: int = 0, limit: int = 100) -> Any:
    """
    Retrieve users.
    """

    count_statement = select(func.count()).select_from(User)
    count = session.exec(count_statement).one()

    statement = select(User).offset(skip).limit(limit)
    users = session.exec(statement).all()

    return UsersPublic(data=users, count=count)

@router.post(
    "/", dependencies=[Depends(get_current_active_superuser)], response_model=UserPublic
)
def create_user(*, session: SessionDep, user_in: UserCreate) -> Any:
    """
    Create new user.
    """
    user = user_service.get_user_by_email(session=session, email=user_in.email)
    if user:
        raise HTTPException(
            status_code=400,
            detail="The user with this email already exists in the system.",
        )

    user = user_service.create_user(session=session, user_create=user_in)
    return user



@router.get("/me", response_model=UserPublic)
def read_user_me(current_user: CurrentUser) -> Any:
    """
    Get current user.
    """
    return current_user


@router.patch("/me", response_model=UserPublic)
def update_user_me(
    *, session: SessionDep, user_in: UserProfileUpdate, current_user: CurrentUser
) -> Any:
    """
    Update current user profile.
    """
    # Update only the fields that are provided (not None)
    user_data = user_in.model_dump(exclude_unset=True)

    for field, value in user_data.items():
        setattr(current_user, field, value)

    session.add(current_user)
    session.commit()
    session.refresh(current_user)
    return current_user


@router.patch("/me/password", response_model=Message)
def update_password_me(
    *, session: SessionDep, body: UpdatePassword, current_user: CurrentUser
) -> Any:
    """
    Update own password.
    """
    if not verify_password(body.current_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Incorrect password")
    if body.current_password == body.new_password:
        raise HTTPException(
            status_code=400, detail="New password cannot be the same as the current one"
        )
    hashed_password = get_password_hash(body.new_password)
    current_user.hashed_password = hashed_password
    session.add(current_user)
    session.commit()
    return Message(message="Password updated successfully")


@router.post("/signup", response_model=UserPublic)
def register_user(session: SessionDep, user_in: UserRegister) -> Any:
    """
    Create new user without the need to be logged in.
    """
    user = user_service.get_user_by_email(session=session, email=user_in.email)
    if user:
        raise HTTPException(
            status_code=400,
            detail="The user with this email already exists in the system",
        )
    user_create = UserCreate.model_validate(user_in)
    user = user_service.create_user(session=session, user_create=user_create)

    # Create email verification token
    verification_token = user_service.create_email_verification_token(
        session=session, user_id=user.id
    )

    # Send verification email
    send_verification_email(
        email_to=user.email,
        token=verification_token.verification_token
    )

    return user


@router.get("/verify-email", response_model=Message)
def verify_email(token: str, session: SessionDep) -> Any:
    """
    Verify user's email address using the verification token.
    """
    is_verified = user_service.verify_email_token(session=session, token=token)

    if not is_verified:
        raise HTTPException(
            status_code=400,
            detail="Invalid or expired verification token",
        )

    return Message(message="Email verified successfully")


@router.post("/accept-invite", response_model=AcceptInviteResponse)
def accept_invite(session: SessionDep, body: AcceptInvite) -> Any:
    """
    Accept a user invitation using the invitation token.
    Validates the token and returns whether the password has been set.
    """
    result = user_service.accept_invitation(session=session, token=body.token)

    if not result:
        raise HTTPException(
            status_code=400,
            detail="Invalid or expired invitation token",
        )

    return AcceptInviteResponse(
        message="Invitation accepted successfully",
        password_set=result["password_set"],
        user_email=result["user_email"]
    )


@router.post("/set-password-with-invite", response_model=Message)
def set_password_with_invite(session: SessionDep, body: SetPasswordWithInvite) -> Any:
    """
    Set user password using invitation token.
    This accepts the invitation, sets the password, and marks the email as verified.
    """
    is_set = user_service.set_password_with_invitation(
        session=session, token=body.token, password=body.password
    )

    if not is_set:
        raise HTTPException(
            status_code=400,
            detail="Invalid or expired invitation token",
        )

    return Message(message="Password set successfully. You can now login.")


@router.post("/forgot-password", response_model=Message)
def forgot_password(session: SessionDep, body: ForgotPassword) -> Any:
    """
    Request password reset email.
    Sends an email with a password reset link to the user's email address.
    """
    # Create password reset token
    reset_token = user_service.create_password_reset_token(
        session=session, email=body.email
    )

    # Always return success message even if email doesn't exist (security best practice)
    # This prevents email enumeration attacks
    if reset_token:
        # Send password reset email
        send_password_reset_email(
            email_to=body.email,
            token=reset_token.reset_token
        )

    return Message(
        message="If an account exists with this email, you will receive password reset instructions."
    )


@router.post("/reset-password", response_model=Message)
def reset_password(session: SessionDep, body: ResetPassword) -> Any:
    """
    Reset password using the reset token from email.
    """
    is_reset = user_service.reset_password_with_token(
        session=session, token=body.token, new_password=body.new_password
    )

    if not is_reset:
        raise HTTPException(
            status_code=400,
            detail="Invalid or expired password reset token",
        )

    return Message(message="Password reset successfully. You can now login with your new password.")


@router.get("/{user_id}/files/{filename:path}")
def get_user_file(
    user_id: uuid.UUID,
    filename: str,
    session: SessionDep,
    current_user: CurrentUser
) -> FileResponse:
    """
    Retrieve a file for a specific user by user ID and filename.
    Users can only access their own files unless they are a superuser.
    """
    # Security check: users can only access their own files unless superuser
    if str(current_user.id) != str(user_id) and not current_user.is_superuser:
        raise HTTPException(
            status_code=403,
            detail="Not authorized to access this user's files"
        )

    # Verify the user exists
    target_user = session.get(User, user_id)
    if not target_user:
        raise HTTPException(
            status_code=404,
            detail=f"User with ID {user_id} not found"
        )

    # Construct the file path
    base_storage_path = Path("storage/users")
    user_storage_path = base_storage_path / str(user_id)
    file_path = user_storage_path / filename

    # Security: Prevent directory traversal attacks
    try:
        file_path = file_path.resolve()
        user_storage_path = user_storage_path.resolve()

        # Ensure the file path is within the user's storage directory
        if not str(file_path).startswith(str(user_storage_path)):
            raise HTTPException(
                status_code=400,
                detail="Invalid file path"
            )
    except Exception:
        raise HTTPException(
            status_code=400,
            detail="Invalid file path"
        )

    # Check if file exists
    if not file_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"File '{filename}' not found for user {user_id}"
        )

    # Check if it's actually a file (not a directory)
    if not file_path.is_file():
        raise HTTPException(
            status_code=400,
            detail=f"'{filename}' is not a file"
        )

    # Return the file
    return FileResponse(
        path=str(file_path),
        filename=file_path.name,
        media_type="application/octet-stream"
    )


@router.get("/{user_id}", response_model=UserPublic)
def read_user_by_id(
    user_id: uuid.UUID, session: SessionDep, current_user: CurrentUser
) -> Any:
    """
    Get a specific user by id.
    """
    user = session.get(User, user_id)
    if user == current_user:
        return user
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=403,
            detail="The user doesn't have enough privileges",
        )
    return user

