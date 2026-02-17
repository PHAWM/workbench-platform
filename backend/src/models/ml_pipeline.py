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

from uuid import uuid4, UUID
from pydantic import field_validator

class Apikeymodel(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    user_id: UUID = Field(default=None, ondelete="CASCADE", foreign_key="user.id")
    model_api_key: str = Field(min_length=1, max_length=256)
    costing_policy: str
    model_metadata_id: int | None = Field(default=None, ondelete="CASCADE", foreign_key="modelmetadata.id")
    
class ApikeymodelCreate(SQLModel):
    user_id: UUID
    model_api_key: str = Field(min_length=1, max_length=256)
    costing_policy: str
    model_metadata_id: int
    
class ApikeymodelUpdate(SQLModel):
    user_id: UUID | None = None
    model_api_key: str | None = Field(default=None, min_length=1, max_length=256)
    costing_policy: str | None = None
    model_metadata_id: int
    
class ApiKeyResponse(SQLModel):
    id: int
    user_id: UUID
    model_api_key: str 
    costing_policy: str
    model_metadata_id: int

class ModelAuditResponse(SQLModel):
    audit_id: int
    audit_name: str
    audit_status: int
    audit_status_text: str
    application_name: str


class ModelCompleteCreate(SQLModel):
    name: str
    model_type: bool
    location: Optional[str] = None
    acceptable_formats: Optional[List[str]] = None  # e.g., ["txt", "html"] for Annif, ["wav", "mp3"] for Sam
    output_context: Optional[str] = None
    task: Optional[str] = None
    api_key_data: Optional[ApikeymodelCreate] = None
    audit_id: Optional[int] = None

class ModelWithKeysResponse(SQLModel):
    id: int
    name: str
    model_type: bool
    location: Optional[str]
    acceptable_formats: Optional[List[str]]
    output_context: Optional[str]
    task: Optional[str]
    api_keys: List[ApiKeyResponse]
    associated_audits: List[ModelAuditResponse]
    total_api_keys: int
    total_audits: int

class ModelCompleteResponse(SQLModel):
    id: int
    name: str
    model_type: bool
    location: Optional[str] = None
    acceptable_formats: Optional[List[str]] = None
    output_context: Optional[str] = None
    task: Optional[str] = None
    api_key_created: Optional[int] = None
    audit_association_created: Optional[int] = None
    message: str = None

class Modelmetadata(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(description="The name of the model i.e. Model")
    model_type: bool = Field(description="0: Predictive AI 1: Generative AI")
    location: str | None = Field(description="the location of the model in case is being hosted locally")
    acceptable_formats: List[str] | None = Field(default=None, sa_column=Column(JSON), description="Acceptable file formats for upload (e.g., ['txt', 'html'] for Annif, ['wav', 'mp3'] for Sam)")
    output_context: str | None = Field(description="The context of the expect output")
    task: str | None = Field(description="The context of the expect output")
   
class ModelmetadataCreate(SQLModel):
    name: str = Field(description="The name of the model i.e. Model")
    model_type: int = Field(description="0: Predictive AI 1: Generative AI", ge=0, le=1)
    location: str | None = Field(default=None, description="the location of the model in case is being hosted locally")
    acceptable_formats: List[str] | None = Field(default=None, description="Acceptable file formats for upload (e.g., ['txt', 'html'] for Annif, ['wav', 'mp3'] for Sam)")
    output_context: str | None = Field(default=None, description="The context of the expect output")
    task: str | None = Field(default=None, description="The context of the expect output")

class ModelmetadataUpdate(SQLModel):
    api_key_id: int | None = None
    name: str | None = None
    model_type: bool | None = None
    location: str | None = None
    acceptable_formats: List[str] | None = None
    output_context: str | None = Field(default=None)
    task: str | None = Field(default=None)
    
class DatasetMetadata(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    purpose: str = Field(description="the purpose of the dataset")
    copyright_agreement: bool | None = Field(description="Whether there is a copyright")
    input_dataset_metadata: list["InputDatasetMetadata"] | None = Relationship(back_populates="dataset_info")
    output_dataset_metadata: list["OutputDatasetMetadata"] | None = Relationship(back_populates="dataset_info")
  
class DatasetMetadataCreate(SQLModel):
    purpose: str = Field(description="the purpose of the dataset")
    copyright_agreement: bool | None = Field(default=None, description="Whether there is a copyright")

class DatasetMetadataUpdate(SQLModel):
    purpose: str | None = None
    copyright_agreement: bool | None = None
    
class DatasetInputResponse(SQLModel):
    id: int
    dataset_metadata_id: int
    headers: Dict[str, Any]
    benchmark_dataset: bool
    datatypes: Dict[str, Any]
    location: Optional[str] | None

class DatasetOutputResponse(SQLModel):
    id: int
    dataset_metadata_id: int
    headers: Dict[str, Any]
    benchmark_dataset: bool
    datatypes: Dict[str, Any]
    location: Optional[str]

class DatasetCompleteResponse(SQLModel):
    id: int
    purpose: str
    copyright_agreement: Optional[bool]
    input_metadata: Optional[DatasetInputResponse]
    output_metadata: Optional[DatasetOutputResponse]
    message: str

class InputDatasetMetadataUpdate(SQLModel):
    dataset_metadata_id: int | None = None
    headers: Dict[str, Any] | None = None
    benchmark_dataset: bool | None = None
    datatypes: Dict[str, Any] | None = None
    location: str | None = None
    
    @field_validator('headers', 'datatypes')
    @classmethod
    def validate_json_fields(cls, v):
        if v is not None and not isinstance(v, dict):
            raise ValueError("Must be a valid dictionary")
        return v

class OutputDatasetMetadataUpdate(SQLModel):
    dataset_metadata_id: int | None = None
    headers: Dict[str, Any] | None = None
    benchmark_dataset: bool | None = None
    datatypes: Dict[str, Any] | None = None
    location: str | None = None
    
    @field_validator('headers', 'datatypes')
    @classmethod
    def validate_json_fields(cls, v):
        if v is not None and not isinstance(v, dict):
            raise ValueError("Must be a valid dictionary")
        return v

class InputDatasetMetadata(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    dataset_metadata_id: int | None = Field(default=None, ondelete="CASCADE", foreign_key="datasetmetadata.id")  # Optional foreign key
    dataset_info: DatasetMetadata | None = Relationship(back_populates="input_dataset_metadata")
    headers: Dict[str, Any] = Field(sa_column=Column(JSON))
    benchmark_dataset: bool = Field(default=False, description="0 not a benchmark")
    datatypes: Dict[str, Any] = Field(sa_column=Column(JSON))
    location: str | None = Field(description="the location of the model in case is being hosted locally")

class InputDatasetMetadataCreate(SQLModel):
    dataset_metadata_id: int | None = Field(default=None)
    headers: Dict[str, Any]
    benchmark_dataset: bool = Field(default=False, description="0 not a benchmark")
    datatypes: Dict[str, Any]
    location: str | None = Field(default=None, description="the location of the model in case is being hosted locally")
    
    @field_validator('headers', 'datatypes')
    @classmethod
    def validate_json_fields(cls, v):
        if not isinstance(v, dict):
            raise ValueError("Must be a valid dictionary")
        return v

class InputDatasetMetadataUpdate(SQLModel):
    dataset_metadata_id: int | None = None
    headers: Dict[str, Any] | None = None
    benchmark_dataset: bool | None = None
    datatypes: Dict[str, Any] | None = None
    location: str | None = None
    
    @field_validator('headers', 'datatypes')
    @classmethod
    def validate_json_fields(cls, v):
        if v is not None and not isinstance(v, dict):
            raise ValueError("Must be a valid dictionary")
        return v

class OutputDatasetMetadata(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    dataset_metadata_id: int | None = Field(default=None, ondelete="CASCADE", foreign_key="datasetmetadata.id")  # Optional foreign key
    dataset_info: DatasetMetadata | None = Relationship(back_populates="output_dataset_metadata")
    headers: Dict[str, Any] = Field(sa_column=Column(JSON))
    benchmark_dataset: bool = Field(default=False, description="0 not a benchmark")
    datatypes: Dict[str, Any] = Field(sa_column=Column(JSON))
    location: str | None = Field(description="the location of the model in case is being hosted locally")
    
class OutputDatasetMetadataCreate(SQLModel):
    dataset_metadata_id: int | None = Field(default=None)
    headers: Dict[str, Any]
    benchmark_dataset: bool = Field(default=False, description="0 not a benchmark")
    datatypes: Dict[str, Any]
    location: str | None = Field(default=None, description="the location of the model in case is being hosted locally")
    
    @field_validator('headers', 'datatypes')
    @classmethod
    def validate_json_fields(cls, v):
        if not isinstance(v, dict):
            raise ValueError("Must be a valid dictionary")
        return v

class OutputDatasetMetadataUpdate(SQLModel):
    dataset_metadata_id: int | None = None
    headers: Dict[str, Any] | None = None
    benchmark_dataset: bool | None = None
    datatypes: Dict[str, Any] | None = None
    location: str | None = None
    
    @field_validator('headers', 'datatypes')
    @classmethod
    def validate_json_fields(cls, v):
        if v is not None and not isinstance(v, dict):
            raise ValueError("Must be a valid dictionary")
        return v
    
class DatasetWithInputOutputCreate(SQLModel):
    """Model for creating dataset metadata with optional input/output metadata"""
    purpose: str = Field(description="the purpose of the dataset")
    copyright_agreement: bool | None = Field(default=None, description="Whether there is a copyright")
    input_metadata: InputDatasetMetadataCreate | None = Field(default=None)
    output_metadata: OutputDatasetMetadataCreate | None = Field(default=None)

# Enhanced update model for dataset with input/output metadata
class DatasetWithInputOutputUpdate(SQLModel):
    """Model for updating dataset metadata with optional input/output metadata"""
    purpose: str | None = None
    copyright_agreement: bool | None = None
    input_metadata: InputDatasetMetadataUpdate | None = None
    output_metadata: OutputDatasetMetadataUpdate | None = None
    
class UnderlyingFeatures(SQLModel, table=True):
    id: int = Field(default=None, primary_key=True)
    feature_name: str
    # data_type:str

class UserDefinedUnderlyingFeatures(SQLModel, table=True):
    """User-defined underlying features specific to an audit"""
    id: int | None = Field(default=None, primary_key=True)
    feature_name: str = Field(description="Name of the underlying feature")
    description: str | None = Field(default=None, description="Description of what this feature represents")
    data_type: str | None = Field(default=None, description="Data type: categorical, numerical, boolean, etc.")
    audit_id: int = Field(ondelete="CASCADE", foreign_key="audit.id")
    user_audit_id: int = Field(ondelete="CASCADE", foreign_key="mappingaudituser.id",
                                description="User who created this feature")

class TargetFeatures(SQLModel, table=True):
    id: int = Field(default=None, primary_key=True)
    target_feature: str
    function_name: str | None

class UserDefinedTargetFeatures(SQLModel, table=True):
    """User-defined target features specific to an audit"""
    id: int | None = Field(default=None, primary_key=True)
    target_feature: str = Field(description="Name of the target feature/metric")
    function_name: str | None = Field(default=None, description="Function name if it maps to a computation")
    description: str | None = Field(default=None, description="Description of what this target feature measures")
    audit_id: int = Field(ondelete="CASCADE", foreign_key="audit.id")
    user_audit_id: int = Field(ondelete="CASCADE", foreign_key="mappingaudituser.id",
                                description="User who created this feature")

class UserDefinedUnderlyingFeatureCreate(SQLModel):
    """Model for creating a user-defined underlying feature"""
    feature_name: str = Field(description="Name of the underlying feature")
    description: str | None = Field(default=None, description="Description of what this feature represents")
    data_type: str | None = Field(default=None, description="Data type: categorical, numerical, boolean, etc.")
    audit_id: int = Field(description="The audit ID this feature belongs to")

class UserDefinedUnderlyingFeatureResponse(SQLModel):
    """Response model for user-defined underlying feature"""
    id: int
    feature_name: str
    description: str | None
    data_type: str | None
    audit_id: int
    user_audit_id: int
    created_by: str  # email of creator
    message: str

class UserDefinedUnderlyingFeatureUpdate(SQLModel):
    """Model for updating a user-defined underlying feature"""
    feature_name: str | None = None
    description: str | None = None
    data_type: str | None = None

class UserDefinedTargetFeatureCreate(SQLModel):
    """Model for creating a user-defined target feature"""
    target_feature: str = Field(description="Name of the target feature/metric")
    function_name: str | None = Field(default=None, description="Function name if it maps to a computation")
    description: str | None = Field(default=None, description="Description of what this target feature measures")
    audit_id: int = Field(description="The audit ID this feature belongs to")

class UserDefinedTargetFeatureResponse(SQLModel):
    """Response model for user-defined target feature"""
    id: int
    target_feature: str
    function_name: str | None
    description: str | None
    audit_id: int
    user_audit_id: int
    created_by: str  # email of creator
    message: str

class UserDefinedTargetFeatureUpdate(SQLModel):
    """Model for updating a user-defined target feature"""
    target_feature: str | None = None
    function_name: str | None = None
    description: str | None = None

class MappingDatasetFeatures(SQLModel, table=True):
    id: int = Field(default=None, primary_key=True)
    dataset_metadata_id: int | None = Field(default=None, ondelete="CASCADE", foreign_key="datasetmetadata.id")
    underlying_feature_id: int = Field(default=None, ondelete="CASCADE", foreign_key="underlyingfeatures.id")
    
class MappingModelTargetFeatures(SQLModel, table=True):
    id: int = Field(default=None, primary_key=True)
    dataset_metadata_id: int | None = Field(default=None, ondelete="CASCADE", foreign_key="datasetmetadata.id")
    target_feature_id: int = Field(default=None, ondelete="CASCADE", foreign_key="targetfeatures.id")

class MappingUserAuditFeatures(SQLModel, table=True):
    """Maps user-specific underlying features to their audit participation"""
    id: int = Field(default=None, primary_key=True)
    user_audit_id: int = Field(default=None, ondelete="CASCADE", foreign_key="mappingaudituser.id")
    underlying_feature_id: int = Field(default=None, ondelete="CASCADE", foreign_key="underlyingfeatures.id")

class MappingUserAuditTargetFeatures(SQLModel, table=True):
    """Maps user-specific target features to their audit participation"""
    id: int = Field(default=None, primary_key=True)
    user_audit_id: int = Field(default=None, ondelete="CASCADE", foreign_key="mappingaudituser.id")
    target_feature_id: int = Field(default=None, ondelete="CASCADE", foreign_key="targetfeatures.id")

class UserFeatureCreate(SQLModel):
    """Model for creating a new user-specific underlying feature"""
    feature_name: str = Field(description="Name of the feature (e.g., 'age', 'gender')")
    audit_id: int = Field(description="The audit ID this feature is for")

class UserTargetFeatureCreate(SQLModel):
    """Model for creating a new user-specific target feature"""
    target_feature: str = Field(description="Name of the target feature (e.g., 'sentiment', 'classification')")
    audit_id: int = Field(description="The audit ID this feature is for")

class UserFeatureResponse(SQLModel):
    """Response model for user feature"""
    id: int
    feature_name: str
    audit_id: int
    user_audit_id: int
    message: str

class UserTargetFeatureResponse(SQLModel):
    """Response model for user target feature"""
    id: int
    target_feature: str
    function_name: str | None
    audit_id: int
    user_audit_id: int
    message: str

class OutputEvaluationData(SQLModel, table=True):
    id: int = Field(default=None, primary_key=True)
    location: str | None
    
class MappingOutputEvaluationUser(SQLModel, table=True):
    id: int = Field(default=None, primary_key=True)
    user_audit_id: int = Field(default=None, ondelete="CASCADE", foreign_key="mappingaudituser.id")
    output_eval_id: int = Field(default=None, ondelete="CASCADE", foreign_key="outputevaluationdata.id")
    
class OutputEvaluationItem(SQLModel):
    audit_criteria_id: int
    output: dict
    target_features:str
    threshold:str
    requirements:int
    notes: Optional[str] = None
    data_id: Optional[int] = None
    file_name: Optional[str] = None
    file_index: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = None
    scale_points: Optional[Dict[str, Any]] = None  # For qualitative metrics
    
class OutputEvaluationResponse(SQLModel):
    audit_criteria: List[OutputEvaluationItem]

class ClassificationItem(SQLModel):
    file_name: str
    file_path: str
    # SAM-specific fields (binary classification)
    classification: Optional[str] = None
    classification_numeric: Optional[int] = None
    confidence: Optional[float] = None
    secure_probability: Optional[float] = None
    insecure_probability: Optional[float] = None
    gender: Optional[str] = None
    age: Optional[Any] = None
    # Annif-specific fields (subject classification)
    predicted_subjects: Optional[str] = None
    top_subjects: Optional[str] = None
    subject_count: Optional[int] = None
    project_id: Optional[str] = None
    expected_subjects: Optional[str] = None
    # Common fields
    id: Optional[Any] = None
    notes: Optional[str] = None
    # Evaluation fields
    data_id: Optional[int] = None
    requirements: Optional[int] = None

class OutputClassificationResponse(SQLModel):
    success: bool
    model_id: Optional[int] = None
    model_name: Optional[str] = None
    model_type: Optional[str] = None
    total_entries_processed: int
    input_location: Optional[str] = None
    output_location: Optional[str] = None
    classifications: List[ClassificationItem]
    output_columns: Optional[List[str]] = None
    error: Optional[str] = None
    message: Optional[str] = None