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

from pydantic import EmailStr, HttpUrl
from uuid import uuid4, UUID

class MappingUserEvents(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    user_audit_id: int | None = Field(default=None, ondelete="CASCADE", foreign_key="mappingaudituser.id")
    event_id: int | None = Field(default=None, ondelete="CASCADE", foreign_key="events.id")
    
class MappingUserMetrics(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    user_audit_id: int | None = Field(default=None, ondelete="CASCADE", foreign_key="mappingaudituser.id")
    metric_id: int | None = Field(default=None, ondelete="CASCADE", foreign_key="metrics.id")
    
class MappingEventsEntities(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    audit_id : int | None = Field(default=None, ondelete="CASCADE", foreign_key="audit.id")
    user_audit_id: int | None = Field(default=None, ondelete="CASCADE", foreign_key="mappingaudituser.id")
    event_id: int | None = Field(default=None, ondelete="CASCADE", foreign_key="events.id")
    entity_id: int | None = Field(default=None, ondelete="CASCADE", foreign_key="entities.id")
    
class MappingMetricsEvents(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    metric_id: int | None = Field(default=None, ondelete="CASCADE", foreign_key="metrics.id")
    event_id: int | None = Field(default=None, ondelete="CASCADE", foreign_key="events.id")
    user_audit_id: int | None = Field(default=None, ondelete="CASCADE", foreign_key="mappingaudituser.id")
    values_id : int | None = Field(default=None, ondelete="CASCADE", foreign_key="metricsvalues.id")

class MappingEventsAuditStatus(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    event_id: int | None = Field(default=None, ondelete="CASCADE", foreign_key="events.id")
    audit_id : int | None = Field(default=None, ondelete="CASCADE", foreign_key="audit.id")
    metric_id : int | None = Field(default=None, ondelete="CASCADE", foreign_key="metrics.id")
    user_audit_id: int | None = Field(default=None, ondelete="CASCADE", foreign_key="mappingaudituser.id")
    recommendation : int | None
    notes : str | None
    status : int | None
    
class AuditStatusUpdate(SQLModel):
    event_id: int
    metric_id: int
    recommendation: int | None = None
    meet_requirement: int | None = None
    notes: str | None = None
    data_id: int | None = None
    output: Dict[str, Any] | None = None

class BatchAuditStatusUpdate(SQLModel):
    audit_statutes: List[AuditStatusUpdate]
    
class MappingEventsCategory(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    event_id: int | None = Field(default=None, ondelete="CASCADE", foreign_key="events.id")
    category_id: int | None  = Field(default=None, ondelete="CASCADE", foreign_key="eventscategory.id")
    
class MappingTaxonomyCategory(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    category_id: int | None = Field(default=None, ondelete="CASCADE", foreign_key="eventscategory.id")
    taxonomy_id: int | None  = Field(default=None, ondelete="CASCADE", foreign_key="taxonomygroups.id")
    
class Events(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    description: str
    cause: str
    reason: str
    likelihood: float
    magnitude: float
    valence: float
    
class EventsCategory(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    event_name: str
    description: str
    
class UserEventCustomisations(SQLModel, table=True):
    """Store user-specific customisations for events"""
    id: int | None = Field(default=None, primary_key=True)
    user_audit_id: int = Field(ondelete="CASCADE", foreign_key="mappingaudituser.id")
    event_id: int = Field(ondelete="CASCADE", foreign_key="events.id")
    
    # Custom event values - only store what's been customised
    custom_likelihood: float | None = Field(default=None, ge=0.0, le=1.0)
    custom_magnitude: float | None = None
    custom_valence: float | None = Field(default=None, ge=-1.0, le=1.0)
    
class EventsCustomUpdate(SQLModel):
    """Model for updating user-specific event customisations"""
    likelihood: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    magnitude: Optional[float] = None
    valence: Optional[float] = Field(default=None, ge=-1.0, le=1.0)
    
class TaxonomyGroups(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    event_name: str
    description: str
    reason:str | None = None
    
class Entities(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    num_individuals: int

class MappingAuditEntities(SQLModel, table=True):
    """Maps entities to audits - defines which entities are available for a specific audit"""
    id: int | None = Field(default=None, primary_key=True)
    audit_id: int = Field(ondelete="CASCADE", foreign_key="audit.id")
    entity_id: int = Field(ondelete="CASCADE", foreign_key="entities.id")

class MappingUserEntities(SQLModel, table=True):
    """Maps user-specific entities to their audit participation
    DEPRECATED: Use MappingAuditEntities instead for better audit isolation"""
    id: int | None = Field(default=None, primary_key=True)
    user_audit_id: int = Field(default=None, ondelete="CASCADE", foreign_key="mappingaudituser.id")
    entity_id: int = Field(default=None, ondelete="CASCADE", foreign_key="entities.id")

class MappingUserCategories(SQLModel, table=True):
    """Maps user-specific categories to their audit participation"""
    id: int | None = Field(default=None, primary_key=True)
    user_audit_id: int = Field(default=None, ondelete="CASCADE", foreign_key="mappingaudituser.id")
    category_id: int = Field(default=None, ondelete="CASCADE", foreign_key="eventscategory.id")

class UserEntityCreate(SQLModel):
    """Model for creating a new user-specific entity"""
    name: str = Field(description="Name of the entity (e.g., 'Students', 'Teachers')")
    num_individuals: int = Field(description="Number of individuals in this entity", ge=0)
    audit_id: int = Field(description="The audit ID this entity is for")

class UserEntityResponse(SQLModel):
    """Response model for user entity"""
    entities_id: int
    name: str
    num_individuals: int
    audit_id: int
    user_audit_id: int
    message: str

class UserCategoryCreate(SQLModel):
    """Model for creating a new user-specific category"""
    event_name: str = Field(description="Name of the category (e.g., 'Privacy Risks', 'Security Concerns')")
    description: str = Field(description="Description of the category")
    audit_id: int = Field(description="The audit ID this category is for")

class UserCategoryResponse(SQLModel):
    """Response model for user category"""
    category_id: int
    event_name: str
    description: str
    audit_id: int
    user_audit_id: int
    message: str

class AuditEntityCreate(SQLModel):
    """Model for adding an entity to an audit"""
    audit_id: int = Field(description="The audit ID")
    entity_id: int = Field(description="The entity ID to add to the audit")

class AuditEntityResponse(SQLModel):
    """Response model for audit entity mapping"""
    id: int
    audit_id: int
    entity_id: int
    entity_name: str
    num_individuals: int
    user_audit_id: int
    created_by: str  # email of creator
    message: str

class EventType(SQLModel, table=True):
    """Table to distinguish between user events and predefined events"""
    id: int | None = Field(default=None, primary_key=True)
    event_id: int | None = Field(default=None, ondelete="CASCADE", foreign_key="events.id")
    is_user_defined: bool = Field(default=True, description="True for user events, False for predefined")
    created_by_user_id: int | None = Field(default=None, description="User who created this event")
    is_template: bool = Field(default=False, description="Whether this event can be used as a template")
    category: str | None = Field(default=None, description="Category for organization")

class EventMetricUpdate(SQLModel):
    """Model for updating metrics associations with an event"""
    metric_id: int
    values_id: Optional[int] = None  # For associating metric values
    
class EventsUpdate(SQLModel):
    description: str | None = None
    likelihood: float | None = Field(default=None, ge=0.0, le=1.0, description="Likelihood between 0 and 1")
    magnitude: float | None = None
    valence: float | None = Field(default=None, ge=-1.0, le=1.0, description="Valence between -1 and 1")
    cause:str | None = None

class MappingAuditPipelineEventsCreate(SQLModel):
    """Model for creating audit pipeline events mapping"""
    audit_pipeline: int
    event_id: int
    metric_id: int

class MappingAuditPipelineEventsBatch(SQLModel):
    """Model for batch creating audit pipeline events mappings"""
    mappings: List[MappingAuditPipelineEventsCreate]

class EventTypeCreate(SQLModel):
    """Model for creating event type"""
    event_id: int
    is_user_defined: bool = True
    is_template: bool = False
    category: Optional[str] = None

class EventTypeUpdate(SQLModel):
    """Model for updating event type"""
    is_user_defined: Optional[bool] = None
    is_template: Optional[bool] = None
    category: Optional[str] = None

class EventTypeDetail(SQLModel):
    """Model for event type details in responses"""
    id: int
    event_id: int
    is_user_defined: bool
    created_by_user_id: Optional[str]
    is_template: bool
    category: Optional[str]

class EntitiesUpdate(SQLModel):
    name: str | None = None
    num_individuals: int | None = Field(default=None, ge=0, description="Number of individuals must be non-negative")
    
class EventMetricSummary(SQLModel):
    metric_id: int
    metric_description: str
    metric_name: str
    metric_type: str
    reason:str
    threshold:str | None
    formula: Optional[str] = None
    metric_value_output: Optional[dict] = None
    underlying_features:  Optional[dict | list] = None
    target_features:  Optional[dict | list] = None
    scale_points:  Optional[dict | list] = None
    is_user_defined: bool
    is_audit_instigator: bool

class EventEntitySummary(SQLModel):
    entity_id: int
    entity_name: str
    num_individuals: int

class EventCategorySummary(SQLModel):
    category_id: int
    event_name: str

class EventUserSummary(SQLModel):
    user_id: str
    full_name: str
    
class EventPipelineSummary(SQLModel):
    metric_id: int

class EventAuditSummary(SQLModel):
    audit_id: int
    audit_name: str
    audit_status: int
    audit_status_text: str
    application_name: str

# List response models
class EventListItem(SQLModel):
    id: int
    name: str
    description: str
    cause: str
    reason:str
    likelihood: float
    magnitude: float
    valence: float
    total_metrics: int
    total_entities: int
    total_audits: int
    primary_category: Optional[str] = None
    primary_audit: Optional[str] = None

class EventDetailedListItem(SQLModel):
    id: int
    name: str
    description: str
    cause: str
    reason:str
    likelihood: float
    magnitude: float
    valence: float
    is_user_defined:bool
    is_audit_instigator:bool
    associated_metrics: List[EventMetricSummary] = []
    associated_entities: List[EventEntitySummary] = []
    associated_pipelines: List[EventPipelineSummary] = []
    event_categories: List[EventCategorySummary] = []
    assigned_users: List[EventUserSummary] = []
    audit_details: List[EventAuditSummary] = []
    total_metrics: int
    total_entities: int
    total_categories: int
    total_users: int
    total_audits: int

class EventsListResponse(SQLModel):
    events: List[EventListItem]
    total_count: int
    page: int
    page_size: int
    total_pages: int
    filters_applied: Dict[str, Any]

class EventsDetailedListResponse(SQLModel):
    events: List[EventDetailedListItem]
    total_count: int
    page: int
    page_size: int
    total_pages: int
    filters_applied: Dict[str, Any]

# Summary statistics
class EventsStatsSummary(SQLModel):
    total_events: int
    risk_distribution: Dict[str, int]
    impact_distribution: Dict[str, int]
    average_likelihood: float
    average_magnitude: float
    average_valence: float
    most_common_category: Optional[str] = None
    most_active_audit: Optional[str] = None

class EventMetricDetail(SQLModel):
    metric_id: int
    metric_description: str
    metric_reason: str
    metric_type: str  # "quantitative", "qualitative", "both", "unclassified"
    formula: Optional[str] = None
    metric_value_output: Optional[dict] = None
    metric_value_threshold: Optional[str] = None

class EventEntityDetail(SQLModel):
    entity_id: int
    entity_name: str
    num_individuals: int

class EventCategoryDetail(SQLModel):
    category_id: int
    event_name: str
    description: str

class EventUserDetail(SQLModel):
    user_id: UUID
    full_name: str
    email: str
    username: str

class EventAuditDetail(SQLModel):
    audit_id: int
    audit_name: str
    audit_status: int
    audit_status_text: str
    recommendation: int
    notes: Optional[str] = None
    application_id: int
    application_name: str

class SingleEventDetailResponse(SQLModel):
    # Basic event info
    id: int
    name: str
    description: str
    cause: str
    reason:str
    likelihood: float
    magnitude: float
    valence: float
    
    # Related data
    associated_metrics: List[EventMetricDetail] = []
    associated_entities: List[EventEntityDetail] = []
    event_categories: List[EventCategoryDetail] = []
    assigned_users: List[EventUserDetail] = []
    audit_details: List[EventAuditDetail] = []
    
    # Counts
    total_metrics: int
    total_entities: int
    total_categories: int
    total_users: int
    total_audits: int
    
class EventCreatorInfo(SQLModel):
    """Information about who created the event"""
    user_id: str
    full_name: str
    email: Optional[str] = None
    username: Optional[str] = None
 
# ============= CREATE EVENT MODELS =============

class EventEntityCreate(SQLModel):
    """Model for creating entity associations with an event"""
    entity_id: int

class EventCategoryCreate(SQLModel):
    """Model for creating category associations with an event"""
    category_id: int

class EventAuditCreate(SQLModel):
    """Model for creating audit associations with an event"""
    audit_id: int
    recommendation: Optional[str] = None
    status: Optional[int] = None

class EventUserCreate(SQLModel):
    """Model for creating user associations with an event"""
    user_audit_id: int
    
class EventMetricCreate(SQLModel):
    """Model for creating metrics associations with an event"""
    metric_id: int
    values_id: Optional[int] = None

class ComprehensiveEventCreate(SQLModel):
    """Comprehensive model for creating an event with related entities"""
    # Basic event properties (required)
    audit_id: int
    name: str
    description: str
    cause: str
    reason: str
    likelihood: float = Field(ge=0.0, le=1.0, description="Likelihood between 0 and 1")
    magnitude: float
    valence: float = Field(ge=-1.0, le=1.0, description="Valence between -1 and 1")
    
    # Event type (optional)
    is_user_defined: bool = True
    is_template: bool = False
    # category: Optional[str] = None
    
    metrics: Optional[List[EventMetricCreate]] = None  # 🔧 ADD THIS
    entities: Optional[List[EventEntityCreate]] = None
    categories: Optional[List[EventCategoryCreate]] = None
    users: Optional[List[EventUserCreate]] = None

# ============= UPDATE EVENT MODELS =============

class EventEntityUpdate(SQLModel):
    """Model for updating entity associations with an event"""
    entity_id: int

class EventCategoryUpdate(SQLModel):
    """Model for updating category associations with an event"""
    category_id: int

class EventAuditUpdate(SQLModel):
    """Model for updating audit associations with an event"""
    audit_id: int
    recommendation: Optional[str] = None
    status: Optional[int] = None

class EventUserUpdate(SQLModel):
    """Model for updating user associations with an event"""
    user_audit_id: int

class ComprehensiveEventUpdate(SQLModel):
    """Comprehensive model for updating all aspects of an event in one call"""
    # Basic event properties
    audit_id: int
    name: Optional[str] = None
    description: Optional[str] = None
    cause: Optional[str] = None
    reason: Optional[str] = None
    likelihood: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    magnitude: Optional[float] = None
    valence: Optional[float] = Field(default=None, ge=-1.0, le=1.0)
    
    # Event type
    is_template: Optional[bool] = None
    # category: Optional[str] = None
    
    # Related entities - send the complete desired state
    entities: Optional[List[EventEntityUpdate]] = None
    categories: Optional[List[EventCategoryUpdate]] = None
    
    users: Optional[List[EventUserUpdate]] = None

# ============= RESPONSE MODELS =============

class EventCreatorInfo(SQLModel):
    """Information about who created the event"""
    user_id: str
    full_name: str
    email: Optional[str] = None
    username: Optional[str] = None
    
class EnhancedEventDetailResponse(SQLModel):
    """Enhanced response that includes creator information"""
    # Basic event info
    id: int
    name: str
    description: str
    cause: str
    reason:str
    likelihood: float
    magnitude: float
    valence: float
    
    # Creator information
    created_by: Optional[EventCreatorInfo] = None
    
    # Event type info
    is_user_defined: bool
    is_template: bool
    event_category: Optional[str] = None
    
    # Related data
    associated_entities: List[EventEntityDetail] = []
    metrics: Optional[List[EventMetricCreate]] = None
    event_categories: List[EventCategoryDetail] = []
    assigned_users: List[EventUserDetail] = []
    audit_details: List[EventAuditDetail] = []
    
    # Risk assessment
    risk_level: str
    impact_type: str
    
    # Counts
    total_entities: int
    total_categories: int
    total_users: int
    total_audits: int

class EventDetailWithCustomisations(SQLModel):
    id: int
    name: str
    description: str
    cause: str
    reason: str
    
    # Effective values (custom or default)
    likelihood: float
    magnitude: float
    valence: float
    
    # Customisation flags
    is_likelihood_customised: bool = False
    is_magnitude_customised: bool = False
    is_valence_customised: bool = False
    
    # Original values (for reference)
    original_likelihood: Optional[float] = None
    original_magnitude: Optional[float] = None
    original_valence: Optional[float] = None

# ============= AUDIT PIPELINE MODELS =============

class MappingAuditPipelineEventsCreate(SQLModel):
    """Model for creating audit pipeline events mapping"""
    audit_id:int
    event_id: int
    metric_id: int
    
class MappingAuditPipelineEventCreate(SQLModel):
    """Model for creating audit pipeline events mapping"""
    event_id: int
    metric_id: int

class MappingAuditPipelineEventsBatch(SQLModel):
    """Model for batch creating audit pipeline events mappings"""
    audit_id: int
    mappings: List[MappingAuditPipelineEventCreate]