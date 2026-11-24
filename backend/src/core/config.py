from typing import List, Optional

# from decouple import config
from pydantic import AnyHttpUrl, EmailStr, Field, parse_obj_as
from pydantic_settings import BaseSettings
import secrets

class Settings(BaseSettings):
    API_V1_STR: str = ""
    JWT_SECRET_KEY: str = Field(default="", env="JWT_SECRET_KEY")
    JWT_REFRESH_SECRET_KEY: str = Field(default="", env="JWT_REFRESH_SECRET_KEY")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 6 # 6 hours
    REFRESH_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days
    BACKEND_CORS_ORIGINS: List[AnyHttpUrl] = [
            parse_obj_as(AnyHttpUrl, "http://app:3000"),
            parse_obj_as(AnyHttpUrl, "https://phawm.ngrok.app"),
            parse_obj_as(AnyHttpUrl, "https://phawmweb.dcs.gla.ac.uk"),
            parse_obj_as(AnyHttpUrl, "https://phawm.org")
    ]
    PROJECT_NAME: str = "PHAWM workbench"
    EMAIL_RESET_TOKEN_EXPIRE_HOURS: int = 48

    # Email Configuration
    FRONTEND_URL: str = Field(default="", env="FRONTEND_URL") # Change this to host's url
    RESEND_API_KEY: str = Field(default="", env="RESEND_API_KEY")
    EMAIL_FROM_NAME: str = Field(default="PHAWM team", env="EMAIL_FROM_NAME")
    EMAIL_FROM_ADDRESS: str = Field(default="noreply@workbench.phawm.org", env="EMAIL_FROM_ADDRESS")

    # Demo Mode
    IS_DEMO: bool = Field(default=False, env="IS_DEMO")

    # S3 / RustFS Storage Configuration
    STORAGE_BACKEND: str = Field(default="local", env="STORAGE_BACKEND")  # "local" or "s3"
    S3_ENDPOINT_URL: str = Field(default="http://localhost:9000", env="S3_ENDPOINT_URL")
    S3_ACCESS_KEY: str = Field(default="", env="S3_ACCESS_KEY")
    S3_SECRET_KEY: str = Field(default="", env="S3_SECRET_KEY")
    S3_BUCKET_NAME: str = Field(default="workbench", env="S3_BUCKET_NAME")
    S3_REGION: str = Field(default="us-east-1", env="S3_REGION")


    class Config:
        case_sensitive = True
        env_file = ".env"
        extra = "ignore"  # Allow extra fields in .env that aren't defined in Settings


settings = Settings()
