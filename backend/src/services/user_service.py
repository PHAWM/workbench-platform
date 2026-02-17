import uuid
from typing import Any
from datetime import datetime, timezone

from sqlmodel import Session, select

from src.core.security import get_password_hash, verify_password
from src.models import User, UserCreate, UserUpdate, EmailVerification, UserInvitation, PasswordResetToken


def create_user(*, session: Session, user_create: UserCreate) -> User:
    db_obj = User.model_validate(
        user_create, update={"hashed_password": get_password_hash(user_create.password)}
    )
    session.add(db_obj)
    session.commit()
    session.refresh(db_obj)
    return db_obj


def update_user(*, session: Session, db_user: User, user_in: UserUpdate) -> Any:
    user_data = user_in.model_dump(exclude_unset=True)
    extra_data = {}
    if "password" in user_data:
        password = user_data["password"]
        hashed_password = get_password_hash(password)
        extra_data["hashed_password"] = hashed_password
    db_user.sqlmodel_update(user_data, update=extra_data)
    session.add(db_user)
    session.commit()
    session.refresh(db_user)
    return db_user


def get_user_by_email(*, session: Session, email: str) -> User | None:
    statement = select(User).where(User.email == email.lower())
    session_user = session.exec(statement).first()
    return session_user


def authenticate(*, session: Session, email: str, password: str) -> User | None:
    db_user = get_user_by_email(session=session, email=email)
    if not db_user:
        return None
    if not verify_password(password, db_user.hashed_password):
        return None
    return db_user


def create_email_verification_token(*, session: Session, user_id: uuid.UUID) -> EmailVerification:
    """Create an email verification token for a user"""
    verification = EmailVerification(user_id=user_id)
    session.add(verification)
    session.commit()
    session.refresh(verification)
    return verification


def verify_email_token(*, session: Session, token: str) -> bool:
    """Verify an email token and mark the verification as complete"""
    statement = select(EmailVerification).where(
        EmailVerification.verification_token == token,
        EmailVerification.is_verified == False
    )
    verification = session.exec(statement).first()

    if not verification:
        return False

    # Check if token has expired
    # Make expires_at timezone-aware if it's naive (from database)
    expires_at = verification.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    if datetime.now(timezone.utc) > expires_at:
        return False

    # Link token to user
    user = session.get(User, verification.user_id)
    if user:
        user.is_verified = True
    # Mark verification as complete
    verification.is_verified = True
    verification.verified_at = datetime.now(timezone.utc)

    session.add(verification)
    session.commit()
    return True


def validate_invitation_token(*, session: Session, token: str) -> UserInvitation | None:
    """Validate an invitation token and return the invitation if valid"""
    statement = select(UserInvitation).where(
        UserInvitation.invitation_token == token,
        UserInvitation.invitation_used == False
    )
    invitation = session.exec(statement).first()

    if not invitation:
        return None

    # Check if token has expired
    # Make expires_at timezone-aware if it's naive (from database)
    expires_at = invitation.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    if datetime.now(timezone.utc) > expires_at:
        return None

    return invitation


def accept_invitation(*, session: Session, token: str) -> dict | None:
    """Accept an invitation - validates the token and returns user status"""
    invitation = validate_invitation_token(session=session, token=token)

    if not invitation:
        return None

    # Get the user associated with this invitation
    user = session.get(User, invitation.user_id)
    if not user:
        return None

    # Check if password has been set in two ways:
    # 1. Check if invitation has been used (marked when password is set)
    # 2. Verify the user has a real password hash (not the default placeholder or empty)
    # A password is considered "set" if the invitation is used OR if the hash is valid
    has_valid_password = bool(
        user.hashed_password and
        user.hashed_password.strip() != "" and
        user.hashed_password != "The hash of the password" and
        len(user.hashed_password) > 20  # Real bcrypt hashes are typically 60 chars
    )

    password_set = bool(invitation.invitation_used or has_valid_password)

    return {
        "user_email": user.email,
        "password_set": password_set
    }


def set_password_with_invitation(*, session: Session, token: str, password: str) -> bool:
    """Set user password using invitation token"""
    invitation = validate_invitation_token(session=session, token=token)

    if not invitation:
        return False

    # Get the user
    user = session.get(User, invitation.user_id)
    if not user:
        return False

    # Set the password
    user.hashed_password = get_password_hash(password)

    # Mark invitation as used
    invitation.invitation_used = True

    session.add(user)
    session.add(invitation)
    session.commit()
    return True


def create_password_reset_token(*, session: Session, email: str) -> PasswordResetToken | None:
    """Create a password reset token for a user"""
    user = get_user_by_email(session=session, email=email)
    if not user:
        return None

    # Create reset token
    reset_token = PasswordResetToken(user_id=user.id)
    session.add(reset_token)
    session.commit()
    session.refresh(reset_token)
    return reset_token


def reset_password_with_token(*, session: Session, token: str, new_password: str) -> bool:
    """Reset user password using reset token"""
    statement = select(PasswordResetToken).where(
        PasswordResetToken.reset_token == token,
        PasswordResetToken.is_used == False
    )
    reset_token = session.exec(statement).first()

    if not reset_token:
        return False

    # Check if token has expired
    expires_at = reset_token.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    if datetime.now(timezone.utc) > expires_at:
        return False

    # Get the user
    user = session.get(User, reset_token.user_id)
    if not user:
        return False

    # Update password
    user.hashed_password = get_password_hash(new_password)

    # Mark token as used
    reset_token.is_used = True
    reset_token.used_at = datetime.now(timezone.utc)

    session.add(user)
    session.add(reset_token)
    session.commit()
    return True
