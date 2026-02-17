from sqlmodel import (
        SQLModel, 
        Field, 
        Relationship, 
        Column, 
        JSON
    )

from sqlalchemy.dialects.postgresql import JSONB

from typing import (
        List, 
        Optional, 
        Dict, 
        Any
    )

from pydantic import HttpUrl, field_validator
from uuid import uuid4, UUID

class MappingAuditUser(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    user_id: UUID | None = Field(default=None, ondelete="CASCADE", foreign_key="user.id")
    audit_id: int | None = Field(default=None, ondelete="CASCADE", foreign_key="audit.id")
    roles_id: int | None = Field(default=None, ondelete="CASCADE", foreign_key="auditroles.id")
    
class MappingAuditApplication(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    application_id: int | None = Field(default=None, ondelete="CASCADE", foreign_key="application.id")
    audit_id: int | None = Field(default=None, ondelete="CASCADE", foreign_key="audit.id")
    
class Application(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    description: str
    organisation: str
    url: str = Field(..., description="Valid HTTP/HTTPS URL")
    access_type: int = Field(default=None, description="0 - Black Box, 1 - Grey Box, 2 - White Box")
    testing_evaluation: Dict = Field(sa_column=Column(JSONB))
    deployment: Dict = Field(sa_column=Column(JSONB))
    business_case: str
    legal_framework: str
    
    @field_validator('url')
    @classmethod
    def validate_url(cls, v: str) -> str:
        # Validate that it's a proper URL
        HttpUrl(v)
        return v
    
class ApplicationUpdate(SQLModel):
    name: str | None = None
    description: str | None = None
    url: str | None = None
    access_type: int | None = None
    organisation: Optional[str] = None
    testing_evaluation: Dict[str, Any] | None = None
    deployment: Dict[str, Any] | None = None
    business_case: str | None = None
    legal_framework: str | None = None

class AuditSummary(SQLModel):
    id: int
    name: str
    status: int
    status_text: str
    recommendation: Optional[str] = None
 
class ApplicationOverviewResponse(SQLModel):
    # Basic application info
    id: int
    name: str
    description: Optional[str] = None
    organisation: Optional[str] = None
    audit_instigator: Optional[str] = None
    url: str | None = None
    access_type: int | None = None
    testing_evaluation: Dict[str, Any] | None = None
    deployment: Dict[str, Any] | None = None
    business_case: str | None = None
    legal_framework: str | None = None
    
    # Associated audits (only for current user)
    audits: List[AuditSummary] = []
    total_audits: int

    # Status summary (for current user's audits)
    audit_status_summary: Dict[str, int] = {}
    
class AllApplicationsOverviewResponse(SQLModel):
    applications: List[ApplicationOverviewResponse] = []
    total_applications: int

class AuditOverviewResponse(SQLModel):
    """Response model for audit overview with application details"""
    id: int
    name: str
    audit_instigator: Optional[str] = None
    status: int
    status_text: str
    completion_percentage: float
    recommendation: Optional[str] = None
    application_id: int
    application_name: str
    application_description: Optional[str] = None
    application_organisation: Optional[str] = None
    application_url: Optional[str] = None
    application_models: list = None
    application_datasets: list = None
    access_type: Optional[int] = None
    testing_evaluation: Optional[Dict[str, Any]] = None
    deployment: Optional[Dict[str, Any]] = None
    business_case: str | None = None
    legal_framework: str | None = None


class AllAuditsOverviewResponse(SQLModel):
    """Response model for all audits overview"""
    audits: List[AuditOverviewResponse]
    total_audits: int
    status_summary: Dict[str, int]
    
class UploadFileDelete(SQLModel):
    filename:str