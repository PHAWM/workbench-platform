from uuid import uuid4, UUID
from datetime import datetime
from sqlmodel import SQLModel, Field, Column
from sqlalchemy.dialects.postgresql import JSONB
from typing import Optional, Dict
from pydantic import EmailStr
import datetime
import secrets

class UserBase(SQLModel):
    email: EmailStr = Field(unique=True, index=True, max_length=255)
    full_name: str
    username: str
    ethnicity: str = Field(default="Not Specified", description="Enthinicity of the user i.e, White/Black/Mixed White")
    gender:str = Field(default="Not Specified", description="Gender of the user")
    country:str = Field(default="Not Specified", description="The country of the user")
    organisation:str = Field(default="Not Specified", description="The organisation of the user")
    is_active: bool = True
    is_superuser: bool = False
    is_verified: bool = True
    
class UserCreate(UserBase):
    password: str = Field(min_length=8, max_length=40, description="user password")

class UserRegister(SQLModel):
    email: EmailStr = Field(max_length=255)
    username: str
    password: str = Field(min_length=8, max_length=40)
    full_name: str
    ethnicity: str = Field(default="Not Specified")
    gender:str = Field(default="Not Specified")
    country:str = Field(default="Not Specified")
    organisation:str = Field(default="Not Specified")

class UserUpdate(UserBase):
    id: UUID = Field(default_factory=uuid4, description="user id")
    email: EmailStr | None = Field(default=None, description="user email")
    new_password: str | None = Field(
        default=None,
        min_length=8,
        max_length=40,
        description="new user password",
    )
    password: str = Field(description="user password")

class UserProfileUpdate(SQLModel):
    """Model for updating user profile without password verification"""
    full_name: Optional[str] = None
    username: Optional[str] = None
    ethnicity: Optional[str] = None
    gender: Optional[str] = None
    country: Optional[str] = None
    organisation: Optional[str] = None

class UpdatePassword(SQLModel):
        current_password: str = Field(min_length=8, max_length=40)
        new_password: str = Field(min_length=8, max_length=40)

class User(UserBase, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True, description="user id")
    hashed_password: str = Field(default="The hash of the password")

class NewPassword(SQLModel):
    token: str
    new_password: str = Field(min_length=10, max_length=40)

class AcceptInvite(SQLModel):
    token: str

class AcceptInviteResponse(SQLModel):
    message: str
    password_set: bool
    user_email: str

class SetPasswordWithInvite(SQLModel):
    token: str
    password: str = Field(min_length=8, max_length=40)

# Generic message
class Message(SQLModel):
    message: str

# JSON payload containing access token
class Token(SQLModel):
    access_token: str
    token_type: str = "bearer"


# Contents of JWT token
class TokenPayload(SQLModel):
    sub: str | None = None

# Properties to return via API, id is always required
class UserPublic(SQLModel):
    email: EmailStr
    full_name: str
    username: str
    ethnicity: str 
    gender:str
    country:str
    organisation:str

class UsersPublic(SQLModel):
    data: list[UserPublic]
    count: int

class UserRoles(SQLModel, table=True):
    id: int = Field(primary_key=True)
    user_id: UUID = Field(ondelete="CASCADE", foreign_key="user.id")
    permissions:  Dict = Field(sa_column=Column(JSONB))

class UserInvitation(SQLModel, table=True):
    id: int = Field(primary_key=True)
    user_id: UUID = Field(ondelete="CASCADE", foreign_key="user.id")
    invitation_token: str = Field(default_factory=lambda: secrets.token_urlsafe(64), description="Token to verify the invitation")
    invitation_used: bool = Field(default=False)
    created_at: datetime.datetime = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc))
    expires_at: datetime.datetime = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=7)) 

class AuditRoles(SQLModel, table=True):
    id: int = Field(primary_key=True)
    role: str

class Permissions(SQLModel, table=True):
    id: int = Field(primary_key=True)
    permission: str

class EmailVerification(SQLModel, table=True):
    id: int = Field(primary_key=True)
    user_id: UUID = Field(ondelete="CASCADE", foreign_key="user.id")
    verification_token: str = Field(default_factory=lambda: secrets.token_urlsafe(32), description="Token to verify the email", unique=True, index=True)
    is_verified: bool = Field(default=False)
    created_at: datetime.datetime = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc))
    expires_at: datetime.datetime = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=7))
    verified_at: Optional[datetime.datetime] = Field(default=None)

class PasswordResetToken(SQLModel, table=True):
    id: int = Field(primary_key=True)
    user_id: UUID = Field(ondelete="CASCADE", foreign_key="user.id")
    reset_token: str = Field(default_factory=lambda: secrets.token_urlsafe(32), description="Token to reset password", unique=True, index=True)
    is_used: bool = Field(default=False)
    created_at: datetime.datetime = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc))
    expires_at: datetime.datetime = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=48))
    used_at: Optional[datetime.datetime] = Field(default=None)

class ForgotPassword(SQLModel):
    email: EmailStr

class ResetPassword(SQLModel):
    token: str
    new_password: str = Field(min_length=8, max_length=40)