from sqlmodel import (
        SQLModel, 
        Field, 
        Relationship, 
        Column, 
        JSON
    )

from typing import (
        List, 
        Optional, 
        Dict, 
        Any
    )

from pydantic import HttpUrl, field_validator
from uuid import uuid4, UUID

#===================================================
#                   Datatables
#===================================================

class MappingAuditModel(SQLModel, table=True):
    """Map Audit with model and audit"""
    id: int | None = Field(default=None, primary_key=True)
    model_id: int | None = Field(default=None, ondelete="CASCADE", foreign_key="modelmetadata.id")
    audit_id: int | None = Field(default=None, ondelete="CASCADE", foreign_key="audit.id")
    
class MappingAuditPipelineEvents(SQLModel, table=True):
    """Map Audit with Pipepline and Event"""
    id: int | None = Field(default=None, primary_key=True)
    audit_pipeline: int | None = Field(default=None, ondelete="CASCADE", foreign_key="auditpipeline.id")
    user_audit_id: int | None = Field(default=None, ondelete="CASCADE", foreign_key="mappingaudituser.id")
    event_id: int | None = Field(default=None, ondelete="CASCADE", foreign_key="events.id")
    metric_id: int | None = Field(default=None, ondelete="CASCADE", foreign_key="metrics.id")
    
class MappingAuditPipelineAudit(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    audit_pipeline: int | None = Field(default=None, ondelete="CASCADE", foreign_key="auditpipeline.id")
    audit_id: int | None = Field(default=None, ondelete="CASCADE", foreign_key="audit.id")
    
class MappingModelDatasetAudit(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    auditpipeline: int = Field(default=None, ondelete="CASCADE", foreign_key="auditpipeline.id")
    model_id: int = Field(default=None, ondelete="CASCADE", foreign_key="modelmetadata.id")
    dataset_id: int = Field(default=None, ondelete="CASCADE", foreign_key="datasetmetadata.id")
    
class MappingAuditOutcomeUser(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    user_audit_id: int | None = Field(default=None, ondelete="CASCADE", foreign_key="mappingaudituser.id")
    audit_id: int | None = Field(default=None, ondelete="CASCADE", foreign_key="audit.id")
    status: int = Field(default=0, description="0 - Not started yet, 1 - In Progress, 2 - Finished")
    recommendation: int | None = Field(default=0, description="0 - Not Evaluated, 1 - Incoclusive, 2 - Fail, 3 - Pass")
    notes: str | None = Field(default=None, description="Overall")
    
class AuditPipeline(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)

# ---------------------------------------------------------------------------
# Pipeline read models (non-table, used as API responses)
# ---------------------------------------------------------------------------

class PipelineModelDatasetPair(SQLModel):
    """One model-dataset pair wired into a pipeline."""
    mapping_id: int
    model_id: int
    model_name: str
    dataset_id: int
    dataset_purpose: str
    dataset_has_input: bool
    dataset_has_output: bool

class PipelineOverviewResponse(SQLModel):
    """Full pipeline overview for an audit, including all wired model-dataset pairs."""
    audit_id: int
    pipeline_id: int
    pairs: List[PipelineModelDatasetPair]
    total_models: int
    total_datasets: int

class PipelineModelDatasetAdd(SQLModel):
    """Request body to wire a model-dataset pair into an audit's pipeline."""
    model_id: int
    dataset_id: int

class AuditInviteRequest(SQLModel):
    """Request body for inviting a user to an audit by email address."""
    email: str

class Audit(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str  | None = Field(default=None)
    description: str | None = Field(default=None)

class AuditOutcomeUpdate(SQLModel):
    status: str | None
    recommendation : int | None
    notes: str | None
    
class AuditOutcomeStatus(SQLModel):
    audit_criteria_id:int
    event_name: str
    metric_name: str
    recommendation: int | None
    recommendation_text: str | None
    status: int
    status_text: str | None
    notes:str | None

class AuditOutcomeResponse(SQLModel):
    audit_criteria: List[AuditOutcomeStatus]
    recommendation: int | None
    recommendation_text: str | None
    notes: str | None

class AuditEvaluationStatus(SQLModel):
    audit_criteria_id: int
    event_id: int
    event_name: str
    metric_id: int
    metric_name: str
    metric_type: str | None
    threshold: str
    output: dict | None
    recommendation: int | None
    recommendation_text: str | None
    status: int
    status_text: str | None
    notes:str | None
    underlying_features: List[dict] | None = []
    scale_points: dict | None = None
    target_feature: str | None = None
    
class AuditEvaluationResponse(SQLModel):
    audit_criteria: List[AuditEvaluationStatus]
    total_criteria_evaluated: int
    total_criteria: int
    output_evaluation: List[Dict[str, Any]] = []
    total_output_evaluated: int = 0

class AuditSubmit(SQLModel):
    recommendation: int
    notes: str | None

class AuditCreateRequest(SQLModel):
    name: str = Field(..., min_length=1, max_length=255, description="Name of the audit")
    application_id: int = Field(..., description="ID of the application to audit")
    status: int = Field(default=0, ge=0, le=2, description="0: Not started, 1: In Progress, 2: Finished")
    recommendation: Optional[str] = Field(default=None, description="Overall audit recommendation")

class AuditCreateResponse(SQLModel):
    id: int
    name: str
    description: str
    status: int
    recommendation: Optional[str]
    application_id: int
    application_name: str
    message: str
    
class AuditEventDetail(SQLModel):
    event_id: int
    description: str
    cause: str
    likelihood: float
    magnitude: float
    valence: float

class AuditPipelineDetail(SQLModel):
    pipeline_id: int
    associated_events: List[AuditEventDetail]

class AuditModelDetail(SQLModel):
    model_id: int
    model_name: str
    model_type: bool
    model_type_text: str
    task: Optional[str]

class ModelDatasetMapping(SQLModel):
    model_id: int
    model_name: str
    dataset_id: int
    dataset_purpose: str

class AuditCompleteResponse(SQLModel):
    id: int
    audit_insigator:str
    name: str
    description: str
    status: int
    status_text: str
    recommendation_text: Optional[str]
    application_id: int
    application_name: str
    associated_models: List[AuditModelDetail]
    audit_pipelines: List[AuditPipelineDetail]
    model_dataset_mappings: List[ModelDatasetMapping]
    total_models: int
    total_pipelines: int
    total_mappings: int

class AuditCompleteCreateResponse(SQLModel):
    id: int
    name: str
    description: str
    status: int
    recommendation_text: Optional[str]
    application_id: int
    application_name: str
    pipeline_created: Optional[int]
    models_associated: int
    model_association_ids: List[int]
    message: str

class AuditUpdate(SQLModel):
    name: Optional[str] = None
    description: Optional[str] = None

class AuditCompleteCreate(SQLModel):
    name: str
    description: str
    application_id: int
    status: int = 0
    recommendation: Optional[str] = None
    create_pipeline: bool = False
    model_ids: Optional[List[int]] = None
    dataset_ids: Optional[List[int]] = None