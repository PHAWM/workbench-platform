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

from pydantic import EmailStr, HttpUrl, field_validator
from uuid import uuid4, UUID

class MetricsValues(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    output: dict | None = Field(default=None, sa_column=Column(JSON))
    threshold: str
    
class OutcomeEvaluationValues(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    output: dict | None = Field(default=None, sa_column=Column(JSON))
    meet_requirement: int = Field(default=0, description="0 - Maybe, 1- No, 2-Yes")
    
class MappingOutcomeEvaluationValues(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    user_audit_id: int = Field(ondelete="CASCADE", foreign_key="mappingaudituser.id")
    metric_id: int = Field(ondelete="CASCADE", foreign_key="metrics.id")
    event_id: int = Field(ondelete="CASCADE", foreign_key="events.id")
    audit_id : int | None = Field(ondelete="CASCADE", foreign_key="audit.id")
    output: dict | None = Field(default=None, sa_column=Column(JSON))
    data_id: int = Field(ondelete="CASCADE", foreign_key="mappingoutputevaluationuser.id")
    meet_requirement: int | None = Field(default=None, description="0 - Maybe, 1- No, 2-Yes")
    notes: str | None = Field(default=None)
    
class MetricsUnderlyingFeatures(SQLModel, table=True):
    id: int = Field(default=None, primary_key=True)
    metric_values_id : int = Field(default=None, ondelete="CASCADE", foreign_key="metricsvalues.id")
    feature_id : int = Field(default=None, ondelete="CASCADE", foreign_key="underlyingfeatures.id")
    ranges: List[str] | None = Field(default=None, sa_column=Column(JSON))

class UserMetricThresholds(SQLModel, table=True):
    """Store user-specific threshold customisations"""
    id: int | None = Field(default=None, primary_key=True)
    user_audit_id: int = Field(ondelete="CASCADE", foreign_key="mappingaudituser.id")
    metric_id: int = Field(ondelete="CASCADE", foreign_key="metrics.id")
    event_id: int = Field(ondelete="CASCADE", foreign_key="events.id")
    values_id: int = Field(ondelete="CASCADE", foreign_key="metricsvalues.id")
    custom_threshold: str

class MetricsTargetFeatures(SQLModel, table=True):
    id: int = Field(default=None, primary_key=True)
    metric_values_id : int = Field(default=None, ondelete="CASCADE", foreign_key="metricsvalues.id")
    target_feature_id : int = Field(default=None, ondelete="CASCADE", foreign_key="targetfeatures.id")
    
class MetricsScalePoints(SQLModel, table=True):
    id: int = Field(default=None, primary_key=True)
    metric_values_id : int = Field(default=None, ondelete="CASCADE", foreign_key="metricsvalues.id")
    scale_points: dict | None = Field(default=None, sa_column=Column(JSON))
    
class Metrics(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name:str
    description: str
    reason:str

class QuantitativeMetrics(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    metric_id: int | None = Field(default=None, ondelete="CASCADE", foreign_key="metrics.id")
    formula: str | None = Field(default=None, description="description of the formula")

class QualitativeMetrics(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    metric_id: int | None = Field(default=None, ondelete="CASCADE", foreign_key="metrics.id")
    definition: str
    
class MetricValuesDetail(SQLModel):
    id: int
    event_id: int | None = None
    output: dict | None = None
    threshold: str | None = None # This will be the effective threshold (custom or default)
    underlying_features: List[dict] | None = []
    target_features: List[dict] | None = []
    scale_points: dict | None = {}
    is_threshold_customised: bool = False 

class MetricFeatureCreate(SQLModel):
    """Model for creating metric features"""
    feature_id: int
    ranges: Optional[List[str]] = []

class MetricFeatureUpdate(SQLModel):
    """Model for updating metric features"""
    id: Optional[int] = None  # MetricsUnderlyingFeatures.id
    feature_id: int
    ranges: Optional[List[str]] = []
    delete: Optional[bool] = False

class MetricValueCreate(SQLModel):
    """Model for creating metric values - Updated for new schema"""
    output: dict | None = None
    threshold: str
    underlying_features: Optional[List[MetricFeatureCreate]] = []
    target_features: Optional[List[MetricFeatureCreate]] = []
    scale_points: Optional[Dict[str, Any]] | None = None

class MetricValueUpdate(SQLModel):
    """Model for updating metric values - Updated for new schema"""
    id: Optional[int] = None  # If provided, update existing; if None, create new
    output: dict | None = None
    threshold: Optional[str] = None
    event_id: Optional[int] = None
    audit_id : Optional[int] = None
    underlying_features: Optional[List[MetricFeatureCreate]] = []
    target_features: Optional[List[MetricFeatureCreate]] = []
    scale_points: Optional[Dict[str, Any]] | None = None
   
class MetricsUpdate(SQLModel):
    description: str | None = None
 
class MetricMappingCreate(SQLModel):
    """Model for creating metric-event mappings"""
    event_id: int
    # user_audit_id will be automatically set to current_user.id
    
class QuantitativeMetricCreate(SQLModel):
    """Model for creating a complete quantitative metric with values and mappings"""
    audit_id:int
    name:str
    description: str
    reason: str
    formula: str
    metric_values: List[MetricValueCreate] = MetricValueCreate
    event_mappings: List[MetricMappingCreate] = MetricMappingCreate

class QuantitativeMetricUpdate(SQLModel):
    """Model for updating a complete quantitative metric with values"""
    description: Optional[str] = None
    name: Optional[str] = None
    reason: Optional[str] = None
    formula: Optional[str] = None
    metric_values: List[MetricValueUpdate] = None
    
class QualitativeMetricCreate(SQLModel):
    """Model for creating a complete qualitative metric with values and mappings"""
    audit_id:int
    name:str
    description: str
    reason: str
    definition: str
    metric_values: List[MetricValueCreate] = MetricValueCreate
    event_mappings: List[MetricMappingCreate] = MetricMappingCreate

class QualitativeMetricUpdate(SQLModel):
    """Model for updating a complete qualitative metric with values"""
    name: Optional[str] = None
    description: Optional[str] = None
    reason: Optional[str] = None
    definition: Optional[str] = None
    metric_values: List[MetricValueUpdate] = None
    
class MetricWithTypeResponse(SQLModel):
    id: int
    description: str
    reason: str
    metric_type: str  
    formula: Optional[str] = None
    is_quantitative: bool
    is_qualitative: bool

class QuantitativeMetricDetail(SQLModel):
    id: int
    metric_id: int
    formula: Optional[str]

class QualitativeMetricDetail(SQLModel):
    id: int
    metric_id: int
    definition: Optional[str]

class MetricDetailResponse(SQLModel):
    id: int
    description: str
    reason: str
    quantitative_details: Optional[QuantitativeMetricDetail] = None
    qualitative_details: Optional[QualitativeMetricDetail] = None
    metric_type: str
    
class MetricEventsDetail(SQLModel):
    event_id: int
    event_description: str
    event_reason: str
    event_name:str
    likelihood: float
    magnitude: float
    valence: float

class CompleteMetricResponse(SQLModel):
    """Response model for complete metric creation/update"""
    id: int
    description: str
    reason: str
    metric_type: str
    quantitative_details: Optional[QuantitativeMetricDetail] = None
    qualitative_details: Optional[QualitativeMetricDetail] = None
    created_values: List[MetricValuesDetail] = MetricValuesDetail
    created_mappings: List[int] = []  # List of mapping IDs
    total_values_created: int
    total_mappings_created: int
    feature_warnings: Optional[List[Dict[str, Any]]] = []  # Warnings about user-specific features

class CompleteMetricUpdateResponse(SQLModel):
    """Response model for complete metric updates"""
    id: int
    description: str
    reason: str
    metric_type: str
    quantitative_details: Optional[QuantitativeMetricDetail] = None
    qualitative_details: Optional[QualitativeMetricDetail] = None
    updated_values: List[MetricValuesDetail] = MetricValuesDetail
    created_values: List[MetricValuesDetail] = MetricValuesDetail
    deleted_values: List[int] = []  # List of deleted value IDs
    total_values_updated: int
    total_values_created: int
    total_values_deleted: int

class SingleMetricDetailResponse(SQLModel):
    # Basic metric info
    id: int
    name:str
    description: str
    reason: str
    
    # Type classification
    metric_type: str  # "quantitative", "qualitative", "both", "unclassified"
    is_quantitative: bool
    is_qualitative: bool
    
    # Detailed type info
    quantitative_details: Optional[QuantitativeMetricDetail] = None
    qualitative_details: Optional[QualitativeMetricDetail] = None
    
    # Related data
    associated_events: List[MetricEventsDetail] = MetricEventsDetail
    metric_values: List[MetricValuesDetail] = MetricValuesDetail
    
    # Counts
    total_events: int
    total_values: int

class MetricDetailedListItem(SQLModel):
    """Model for listing metrics with creator information"""
    id: int
    name: str
    description: str
    reason: str
    metric_type: str  # "quantitative", "qualitative", "unclassified"
    is_user_defined: bool  # True if created by a user, False if system-generated
    is_audit_instigator: bool  # True if created by the audit creator/owner
    created_by_user_id: Optional[int] = None
    created_by_username: Optional[str] = None
    created_at: Optional[str] = None  # ISO datetime string

    # Optional type-specific details
    formula: Optional[str] = None  # For quantitative metrics
    definition: Optional[str] = None  # For qualitative metrics

    # Threshold information - uses user's custom threshold if exists, otherwise default
    threshold: Optional[str] = None
    is_threshold_customised: bool = False

    # Counts for quick reference
    total_events: int = 0
    total_values: int = 0

class MetricListResponse(SQLModel):
    """Response model for listing metrics with pagination"""
    metrics: List[MetricDetailedListItem]
    total_count: int
    page: int
    page_size: int
    has_next: bool
    has_previous: bool


class AssignMetricEventRequest(SQLModel):
    """Request model for assigning a metric to an event for a user_audit"""
    audit_id: int
    event_id: int
    metric_id: int
    threshold: str = "0.5"


class AssignMetricEventResponse(SQLModel):
    """Response model for assigning a metric to an event"""
    mapping_id: int
    values_id: int
    metric_id: int
    event_id: int
    user_audit_id: int
    audit_status_id: int
    message: str