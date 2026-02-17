from typing import List, Optional

# from decouple import config
from pydantic import AnyHttpUrl, EmailStr, Field, parse_obj_as
from pydantic_settings import BaseSettings
import secrets

class Settings(BaseSettings):
    API_V1_STR: str = "/api/v1"
    JWT_SECRET_KEY: str = secrets.token_urlsafe(32)
    JWT_REFRESH_SECRET_KEY: str = secrets.token_urlsafe(32)
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days
    BACKEND_CORS_ORIGINS: List[AnyHttpUrl] = [
        parse_obj_as(AnyHttpUrl, "http://localhost:3000"),
    ]
    PROJECT_NAME: str = "PHAWM workbench"
    EMAIL_RESET_TOKEN_EXPIRE_HOURS: int = 48

    # Email Configuration
    FRONTEND_URL: str = Field(default="http://129.215.193.50:3000", env="FRONTEND_URL") # Change this to host's url
    RESEND_API_KEY: str = Field(default="", env="RESEND_API_KEY")
    EMAIL_FROM_NAME: str = Field(default="PHAWM team", env="EMAIL_FROM_NAME")
    EMAIL_FROM_ADDRESS: str = Field(default="noreply@workbench.phawm.org", env="EMAIL_FROM_ADDRESS")


    class Config:
        case_sensitive = True
        env_file = ".env"
        extra = "ignore"  # Allow extra fields in .env that aren't defined in Settings


settings = Settings()
