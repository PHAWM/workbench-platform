import os
import re
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import col, delete, func, select

from src.api.deps import (
    SessionDep, get_current_active_superuser, get_current_user,
    get_current_instigator_or_superuser, get_current_tenant_id,
)

from src.models import *
from src.services.audit_service import ml_flow_service

router = APIRouter(prefix="/pipeline", tags=["AI Pipeline"])

# Base path for model service API directories
_MODEL_API_BASE = Path(__file__).parent.parent.parent / "services" / "model_service" / "api"

@router.post("/api-keys/", response_model=Apikeymodel)
def create_api_key(api_key_data: ApikeymodelCreate, session: SessionDep, current_user: User = Depends(get_current_instigator_or_superuser)):
    """Create a new API key entry"""
    try:
        # Create new API key instance
        db_api_key = ml_flow_service.create_api_key(session=session, api_key_data=api_key_data, user_id=current_user.id)
        
        return db_api_key
        
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=400, detail=f"Error creating API key: {str(e)}")

@router.post("/model-metadata/", response_model=Modelmetadata)
def create_model_metadata(model_data: ModelmetadataCreate, session: SessionDep, current_user: User = Depends(get_current_instigator_or_superuser)):
    """Create a new model metadata entry"""
    try:
        db_model = ml_flow_service.create_model_metadata(session = session, model_data=model_data)
        
        return db_model
        
    except HTTPException:
        session.rollback()
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=400, detail=f"Error creating model metadata: {str(e)}")
    
@router.get("/model-metadata/{model_id}", response_model=Modelmetadata)
def get_model_metadata(model_id: int, session: SessionDep, current_user: User = Depends(get_current_instigator_or_superuser)):
    """Get model metadata by ID"""
    statement = select(Modelmetadata).where(Modelmetadata.id == model_id)
    model = session.exec(statement).first()
    if not model:
        raise HTTPException(status_code=404, detail="Model metadata not found")
    return model

@router.post("/dataset/metadata/", response_model=DatasetMetadata)
def create_complete_dataset(
    dataset_data: DatasetWithInputOutputCreate, 
    session: SessionDep,
    current_user: User = Depends(get_current_instigator_or_superuser)
):
    """Create dataset with complete input and output metadata in one call"""
    try:
        # Create main dataset metadata
        dataset = DatasetMetadata(
            purpose=dataset_data.purpose,
            copyright_agreement=dataset_data.copyright_agreement
        )
        session.add(dataset)
        session.flush()
        
        input_metadata = None
        output_metadata = None
        
        # Create input metadata if provided
        if dataset_data.input_metadata:
            input_metadata = InputDatasetMetadata(
                dataset_metadata_id=dataset.id,
                headers=dataset_data.input_metadata.headers,
                benchmark_dataset=dataset_data.input_metadata.benchmark_dataset,
                datatypes=dataset_data.input_metadata.datatypes,
                location=dataset_data.input_metadata.location
            )
            session.add(input_metadata)
            session.flush()
        
        # Create output metadata if provided
        if dataset_data.output_metadata:
            output_metadata = OutputDatasetMetadata(
                dataset_metadata_id=dataset.id,
                headers=dataset_data.output_metadata.headers,
                benchmark_dataset=dataset_data.output_metadata.benchmark_dataset,
                datatypes=dataset_data.output_metadata.datatypes,
                location=dataset_data.output_metadata.location
            )
            session.add(output_metadata)
            session.flush()
        
        # Auto-create underlying features from input headers
        EXCLUDED_FIELDS = {'id', 'true_value', 'y_pred', 'y_actual', 'file', 'output', 'subjects'}
        created_underlying = []
        if input_metadata and input_metadata.headers:
            for feature_name in input_metadata.headers.keys():
                if feature_name in EXCLUDED_FIELDS:
                    continue
                # Find or create UnderlyingFeatures record
                existing = session.exec(
                    select(UnderlyingFeatures).where(UnderlyingFeatures.feature_name == feature_name)
                ).first()
                if not existing:
                    existing = UnderlyingFeatures(feature_name=feature_name)
                    session.add(existing)
                    session.flush()
                # Create MappingDatasetFeatures link
                existing_mapping = session.exec(
                    select(MappingDatasetFeatures).where(
                        MappingDatasetFeatures.dataset_metadata_id == dataset.id,
                        MappingDatasetFeatures.underlying_feature_id == existing.id
                    )
                ).first()
                if not existing_mapping:
                    session.add(MappingDatasetFeatures(
                        dataset_metadata_id=dataset.id,
                        underlying_feature_id=existing.id
                    ))
                created_underlying.append(feature_name)

        # Create target features from explicit list
        created_targets = []
        if dataset_data.target_features:
            for target_name in dataset_data.target_features:
                existing = session.exec(
                    select(TargetFeatures).where(TargetFeatures.target_feature == target_name)
                ).first()
                if not existing:
                    existing = TargetFeatures(target_feature=target_name, function_name=None)
                    session.add(existing)
                    session.flush()
                # Create MappingModelTargetFeatures link
                existing_mapping = session.exec(
                    select(MappingModelTargetFeatures).where(
                        MappingModelTargetFeatures.dataset_metadata_id == dataset.id,
                        MappingModelTargetFeatures.target_feature_id == existing.id
                    )
                ).first()
                if not existing_mapping:
                    session.add(MappingModelTargetFeatures(
                        dataset_metadata_id=dataset.id,
                        target_feature_id=existing.id
                    ))
                created_targets.append(target_name)

        session.commit()

        return DatasetCompleteResponse(
            id=dataset.id,
            purpose=dataset.purpose,
            copyright_agreement=dataset.copyright_agreement,
            input_metadata=DatasetInputResponse(
                id=input_metadata.id,
                dataset_metadata_id=input_metadata.dataset_metadata_id,
                headers=input_metadata.headers,
                benchmark_dataset=input_metadata.benchmark_dataset,
                datatypes=input_metadata.datatypes,
                location=input_metadata.location
            ) if input_metadata else None,
            output_metadata=DatasetOutputResponse(
                id=output_metadata.id,
                dataset_metadata_id=output_metadata.dataset_metadata_id,
                headers=output_metadata.headers,
                benchmark_dataset=output_metadata.benchmark_dataset,
                datatypes=output_metadata.datatypes,
                location=output_metadata.location
            ) if output_metadata else None,
            message=f"Dataset created successfully. Underlying features: {created_underlying}. Target features: {created_targets}."
        )
        
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=400, detail=f"Error creating complete dataset: {str(e)}")
    
@router.get("/dataset/metadata/{dataset_id}", response_model=DatasetCompleteResponse)
def get_complete_dataset(
    dataset_id: int, 
    session: SessionDep,
    current_user: User = Depends(get_current_instigator_or_superuser)
):
    """Get dataset with complete input and output metadata"""
    
    # Get main dataset
    dataset = session.get(DatasetMetadata, dataset_id)
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")
    
    # Get input metadata
    input_statement = select(InputDatasetMetadata).where(
        InputDatasetMetadata.dataset_metadata_id == dataset_id
    )
    input_metadata = session.exec(input_statement).first()
    
    # Get output metadata
    output_statement = select(OutputDatasetMetadata).where(
        OutputDatasetMetadata.dataset_metadata_id == dataset_id
    )
    output_metadata = session.exec(output_statement).first()
    
    return DatasetCompleteResponse(
        id=dataset.id,
        purpose=dataset.purpose,
        copyright_agreement=dataset.copyright_agreement,
        input_metadata=DatasetInputResponse(
            id=input_metadata.id,
            dataset_metadata_id=input_metadata.dataset_metadata_id,
            headers=input_metadata.headers,
            benchmark_dataset=input_metadata.benchmark_dataset,
            datatypes=input_metadata.datatypes,
            location=input_metadata.location
        ) if input_metadata else None,
        output_metadata=DatasetOutputResponse(
            id=output_metadata.id,
            dataset_metadata_id=output_metadata.dataset_metadata_id,
            headers=output_metadata.headers,
            benchmark_dataset=output_metadata.benchmark_dataset,
            datatypes=output_metadata.datatypes,
            location=output_metadata.location
        ) if output_metadata else None,
        message="Dataset retrieved successfully"
    )

@router.get("/dataset/", response_model=list[DatasetSummary])
def list_datasets(
    session: SessionDep,
    current_user: User = Depends(get_current_user),
    skip: int = 0,
    limit: int = 100,
):
    """List all datasets with a summary — accessible to any authenticated user so the
    audit_instigator can pick an existing dataset or decide whether to upload new files.

    Gray-box audits commonly supply only a pre-computed results.csv (no training data),
    so this endpoint deliberately returns metadata-only datasets alongside fully uploaded ones.
    The frontend can use ``has_input`` / ``has_output`` flags to show the dataset mode.
    """
    datasets = session.exec(select(DatasetMetadata).offset(skip).limit(limit)).all()
    result = []
    for ds in datasets:
        input_meta = session.exec(
            select(InputDatasetMetadata).where(InputDatasetMetadata.dataset_metadata_id == ds.id)
        ).first()
        output_meta = session.exec(
            select(OutputDatasetMetadata).where(OutputDatasetMetadata.dataset_metadata_id == ds.id)
        ).first()
        result.append(
            DatasetSummary(
                id=ds.id,
                purpose=ds.purpose,
                copyright_agreement=ds.copyright_agreement,
                has_input=input_meta is not None,
                has_output=output_meta is not None,
                input_location=input_meta.location if input_meta else None,
                output_location=output_meta.location if output_meta else None,
            )
        )
    return result


@router.get("/dataset/input/{input_id}", response_model=InputDatasetMetadata)
def get_input_dataset_metadata(input_id: int, session: SessionDep, current_user: User = Depends(get_current_instigator_or_superuser)):
    """Get input dataset metadata by ID"""
    statement = select(InputDatasetMetadata).where(InputDatasetMetadata.id == input_id)
    input_data = session.exec(statement).first()
    if not input_data:
        raise HTTPException(status_code=404, detail="Input dataset metadata not found")
    return input_data

@router.get("/dataset/output/{output_id}", response_model=OutputDatasetMetadata)
def get_output_dataset_metadata(output_id: int, session: SessionDep, current_user: User = Depends(get_current_instigator_or_superuser)):
    """Get output dataset metadata by ID"""
    statement = select(OutputDatasetMetadata).where(OutputDatasetMetadata.id == output_id)
    output_data = session.exec(statement).first()
    if not output_data:
        raise HTTPException(status_code=404, detail="Output dataset metadata not found")
    return output_data

@router.get("/model/", response_model=list[Modelmetadata])
def list_model_metadata(session: SessionDep, current_user: User = Depends(get_current_user), skip: int = 0, limit: int = 100):
    """List all model metadata with pagination — accessible to any authenticated user so the
    audit_instigator can populate a model picker during audit creation."""
    statement = select(Modelmetadata).offset(skip).limit(limit)
    models = session.exec(statement).all()
    return models

@router.put("/api-keys/{api_key_id}", response_model=Apikeymodel)
def update_api_key(api_key_id: int, api_key_update: ApikeymodelUpdate, session: SessionDep, current_user: User = Depends(get_current_instigator_or_superuser)):
    """Update an existing API key"""
    try:
        # Get existing API key
        db_api_key = ml_flow_service.update_api_key(api_key_id=api_key_id, api_key_update=api_key_update, session=session)
        
        return db_api_key
        
    except HTTPException:
        session.rollback()
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=400, detail=f"Error updating API key: {str(e)}")

@router.put("/model/{model_id}", response_model=Modelmetadata)
def update_model_metadata(model_id: int, model_update: ModelmetadataUpdate, session: SessionDep, current_user: User = Depends(get_current_instigator_or_superuser)):
    """Update an existing model metadata"""
    try:
        db_model = ml_flow_service.update_model_metadata(model_id=model_id, model_update=model_update, session=session)
        
        return db_model
        
    except HTTPException:
        session.rollback()
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=400, detail=f"Error updating model metadata: {str(e)}")

@router.put("/dataset/metadata/{dataset_id}", response_model=DatasetMetadata)
def update_dataset_metadata(
    dataset_id: int,
    dataset_update: DatasetMetadataUpdate,
    session: SessionDep,
    current_user: User = Depends(get_current_instigator_or_superuser)
):
    """Update an existing dataset metadata"""
    try:
        db_dataset = ml_flow_service.update_dataset_metadata(dataset_id=dataset_id, dataset_update=dataset_update, session=session)
        
        return db_dataset
        
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=400, detail=f"Error updating dataset metadata: {str(e)}")

@router.put("/dataset/metadata/{dataset_id}/all")
def update_dataset_with_input_output(dataset_id: int, dataset_update: DatasetWithInputOutputUpdate, session: SessionDep, current_user: User = Depends(get_current_instigator_or_superuser)):
    """Update dataset metadata with optional input/output metadata updates"""
    try:
        response_data = ml_flow_service.update_dataset_with_input_output(dataset_id=dataset_id, dataset_update=dataset_update, session=session)
        
        return response_data
        
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=400, detail=f"Error updating dataset with metadata: {str(e)}")

@router.delete("/api-keys/{api_key_id}")
def delete_api_key(api_key_id: int, session: SessionDep, current_user: User = Depends(get_current_instigator_or_superuser)):
    """Delete an API key and check for dependencies"""
    try:
        ml_flow_service.delete_api_key(api_key_id=api_key_id, session=session)
        
        return {"message": "API key deleted successfully"}
        
    except HTTPException:
        session.rollback()
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=400, detail=f"Error deleting API key: {str(e)}")

@router.delete("/model/{model_id}")
def delete_model_metadata(model_id: int, session: SessionDep, current_user: User = Depends(get_current_instigator_or_superuser)):
    """Delete a model metadata entry"""
    try:
        # Get existing model metadata
        statement = select(Modelmetadata).where(Modelmetadata.id == model_id)
        db_model = session.exec(statement).first()
        
        if not db_model:
            raise HTTPException(status_code=404, detail="Model metadata not found")
        
        session.delete(db_model)
        session.commit()
        
        return {"message": "Model metadata deleted successfully"}
        
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=400, detail=f"Error deleting model metadata: {str(e)}")

@router.delete("/dataset/metadata/{dataset_id}")
def delete_dataset_metadata(dataset_id: int, session: SessionDep, current_user: User = Depends(get_current_instigator_or_superuser)):
    """Force delete dataset metadata and all associated input/output datasets"""
    try:
        # Get existing dataset metadata
        statement = select(DatasetMetadata).where(DatasetMetadata.id == dataset_id)
        db_dataset = session.exec(statement).first()
        
        if not db_dataset:
            raise HTTPException(status_code=404, detail="Dataset metadata not found")
        
        # Delete all dependent input/output dataset metadata
        input_statement = select(InputDatasetMetadata).where(InputDatasetMetadata.dataset_metadata_id == dataset_id)
        output_statement = select(OutputDatasetMetadata).where(OutputDatasetMetadata.dataset_metadata_id == dataset_id)
        
        dependent_inputs = session.exec(input_statement).all()
        dependent_outputs = session.exec(output_statement).all()
        
        for input_item in dependent_inputs:
            session.delete(input_item)
        
        for output_item in dependent_outputs:
            session.delete(output_item)
        
        session.delete(db_dataset)
        session.commit()
        
        total_deleted = len(dependent_inputs) + len(dependent_outputs)
        return {"message": f"Dataset metadata and {total_deleted} associated input/output entries deleted successfully"}
        
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=400, detail=f"Error force deleting dataset metadata: {str(e)}")

@router.delete("/dataset/metadata/input/{input_id}")
def delete_input_dataset_metadata(input_id: int, session: SessionDep, current_user: User = Depends(get_current_instigator_or_superuser)):
    """Delete an input dataset metadata entry"""
    try:
        # Get existing input dataset metadata
        statement = select(InputDatasetMetadata).where(InputDatasetMetadata.id == input_id)
        db_input = session.exec(statement).first()
        
        if not db_input:
            raise HTTPException(status_code=404, detail="Input dataset metadata not found")
        
        session.delete(db_input)
        session.commit()
        
        return {"message": "Input dataset metadata deleted successfully"}
        
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=400, detail=f"Error deleting input dataset metadata: {str(e)}")

@router.delete("/dataset/metadata/output/{output_id}")
def delete_output_dataset_metadata(output_id: int, session: SessionDep, current_user: User = Depends(get_current_instigator_or_superuser)):
    """Delete an output dataset metadata entry"""
    try:
        # Get existing output dataset metadata
        statement = select(OutputDatasetMetadata).where(OutputDatasetMetadata.id == output_id)
        db_output = session.exec(statement).first()
        
        if not db_output:
            raise HTTPException(status_code=404, detail="Output dataset metadata not found")
        
        session.delete(db_output)
        session.commit()
        
        return {"message": "Output dataset metadata deleted successfully"}
        
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=400, detail=f"Error deleting output dataset metadata: {str(e)}")


# ---------------------------------------------------------------------------
# Dataset Import (HuggingFace / PyTorch / File)
# ---------------------------------------------------------------------------

@router.post("/dataset/import/", response_model=DatasetImportResponse)
def import_dataset(
    request: DatasetImportRequest,
    session: SessionDep,
    current_user: User = Depends(get_current_instigator_or_superuser),
):
    """Import a dataset from HuggingFace, PyTorch, or a remote file URL.

    Supported source_type values:
      - 'huggingface' — any HuggingFace Hub dataset (e.g. 'imdb', 'glue')
      - 'pytorch'     — torchvision datasets (e.g. 'cifar10', 'mnist')
      - 'file'        — a direct URL to a CSV, JSON, JSONL, or Parquet file
    """
    from src.services.dataset_service.loader import DatasetLoaderService

    try:
        loader = DatasetLoaderService()
        result = loader.import_dataset(
            session=session,
            source_type=request.source_type,
            dataset_name=request.dataset_name,
            split=request.split,
            subset=request.subset,
            max_samples=request.max_samples,
            label_column=request.label_column,
            text_column=request.text_column,
            purpose=request.purpose,
            audit_id=request.audit_id,
            target_features=request.target_features,
            underlying_feature_columns=request.underlying_feature_columns,
        )
        return DatasetImportResponse(
            dataset_id=result["dataset_id"],
            input_metadata_id=result["input_metadata_id"],
            output_metadata_id=result["output_metadata_id"],
            location=result["location"],
            row_count=result["row_count"],
            columns=result["columns"],
            underlying_features=result["underlying_features"],
            target_features=result["target_features"],
            source=result["source"],
            message=f"Dataset '{request.dataset_name}' imported successfully "
                    f"({result['row_count']} rows, "
                    f"{len(result['underlying_features'])} underlying features, "
                    f"{len(result['target_features'])} target features).",
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=f"Error importing dataset: {str(e)}")


# ---------------------------------------------------------------------------
# Discovery endpoints — help the frontend populate pickers
# ---------------------------------------------------------------------------

@router.get("/available-metrics/")
def get_available_metrics(
    current_user: User = Depends(get_current_user),
):
    """Return all metric names from the METRICS_REGISTRY, grouped by category.

    The frontend can use this to populate the target-features picker when
    setting up a dataset or an audit.
    """
    from src.services.performance_service.functions import METRICS_REGISTRY

    # Build a simple categorised view based on the registry comments
    classification = []
    regression = []
    fairness = []
    ranking = []
    calibration = []
    generative = []
    keyword = []
    composite = []

    fairness_keys = {
        "equalized_odds", "equal_opportunity", "demographic_parity",
        "statistical_parity", "disparate_impact",
    }
    regression_keys = {
        "mse", "mean_squared_error", "rmse", "root_mean_squared_error",
        "mae", "mean_absolute_error", "mape", "mean_absolute_percentage_error",
        "r2", "r_squared", "explained_variance", "max_error",
        "median_absolute_error", "regression_summary",
    }
    ranking_keys = {"ndcg", "normalized_dcg", "top_k_accuracy"}
    calibration_keys = {"calibration", "ece", "expected_calibration_error"}
    generative_keys = {"bleu", "rouge", "perplexity"}
    keyword_keys = {"keyword_accuracy", "batch_keyword_accuracy"}
    composite_keys = {"performance_summary", "classification_summary", "regression_summary"}

    for key in METRICS_REGISTRY:
        if key in fairness_keys:
            fairness.append(key)
        elif key in regression_keys:
            regression.append(key)
        elif key in ranking_keys:
            ranking.append(key)
        elif key in calibration_keys:
            calibration.append(key)
        elif key in generative_keys:
            generative.append(key)
        elif key in keyword_keys:
            keyword.append(key)
        elif key in composite_keys:
            composite.append(key)
        else:
            classification.append(key)

    # Build detailed list with function names
    all_metrics = []
    for key in sorted(METRICS_REGISTRY.keys()):
        all_metrics.append({
            "name": key,
            "function_name": METRICS_REGISTRY[key].__name__,
        })

    def _sorted_with_functions(keys):
        return [
            {"name": k, "function_name": METRICS_REGISTRY[k].__name__}
            for k in sorted(keys)
        ]

    return {
        "all": all_metrics,
        "by_category": {
            "classification": _sorted_with_functions(classification),
            "regression": _sorted_with_functions(regression),
            "fairness": _sorted_with_functions(fairness),
            "ranking": _sorted_with_functions(ranking),
            "calibration": _sorted_with_functions(calibration),
            "generative_ai": _sorted_with_functions(generative),
            "keyword_matching": _sorted_with_functions(keyword),
            "composite": _sorted_with_functions(composite),
        },
    }


@router.get("/dataset/columns/{dataset_id}")
def get_dataset_columns(
    dataset_id: int,
    session: SessionDep,
    current_user: User = Depends(get_current_user),
    tenant_id: str | None = Depends(get_current_tenant_id),
):
    """Return the columns available in a dataset so the frontend can show a
    picker for underlying features.

    Reads columns from InputDatasetMetadata.headers and, if present, from
    the actual metadata.csv or data.csv on disk.
    """
    import os

    input_meta = session.exec(
        select(InputDatasetMetadata)
        .where(InputDatasetMetadata.dataset_metadata_id == dataset_id)
    ).first()
    if not input_meta:
        raise HTTPException(status_code=404, detail="Dataset not found")

    # Columns from DB headers
    db_columns = list(input_meta.headers.keys()) if input_meta.headers else []

    # Try to read columns from the actual file for the most up-to-date view
    file_columns = []
    if input_meta.location:
        from src.services.utility_service.s3_storage_service import get_storage_manager, S3StorageManager
        import pandas as pd
        sm = get_storage_manager(tenant_id)
        for fname in ["metadata.csv", "data.csv"]:
            try:
                if isinstance(sm, S3StorageManager):
                    prefix = input_meta.location.rstrip("/")
                    if prefix.startswith("storage/"):
                        prefix = prefix[len("storage/"):]
                    key = f"{prefix}/{fname}"
                    if sm.file_exists(key):
                        raw = sm.read_file(key)
                        import io
                        df_head = pd.read_csv(io.BytesIO(raw), nrows=0)
                        file_columns = list(df_head.columns)
                        break
                else:
                    csv_path = os.path.join(input_meta.location, fname)
                    if os.path.isfile(csv_path):
                        df_head = pd.read_csv(csv_path, nrows=0)
                        file_columns = list(df_head.columns)
                        break
            except Exception:
                pass

    # Merge — file columns are authoritative when available
    all_columns = file_columns if file_columns else db_columns

    SYSTEM_FIELDS = {"id", "true_value", "y_pred", "y_actual", "file", "output", "subjects"}
    selectable = [c for c in all_columns if c not in SYSTEM_FIELDS]

    return {
        "dataset_id": dataset_id,
        "all_columns": all_columns,
        "selectable_as_features": selectable,
        "system_columns": [c for c in all_columns if c in SYSTEM_FIELDS],
        "source": input_meta.source,
    }


# ---------------------------------------------------------------------------
# MCP Model Scaffolding & Health
# ---------------------------------------------------------------------------

RESERVED_PORTS = {8002, 8003, 8004, 8005}


@router.post("/model/scaffold/", response_model=ModelScaffoldResponse)
def scaffold_model_service(
    request: ModelScaffoldRequest,
    session: SessionDep,
    current_user: User = Depends(get_current_instigator_or_superuser),
):
    """Scaffold a new MCP model service from the template.

    Creates:
      - A new directory under src/services/model_service/api/{ServiceName}/
      - Customised server.py, Dockerfile, requirements.txt
      - A Modelmetadata DB record with mcp_tool_name and location
    Returns the generated files and a docker-compose snippet.
    """
    # Validate tool_name is a valid Python identifier
    if not request.tool_name.isidentifier():
        raise HTTPException(status_code=422, detail=f"tool_name '{request.tool_name}' is not a valid Python identifier")

    if request.port in RESERVED_PORTS:
        raise HTTPException(status_code=422, detail=f"Port {request.port} is reserved (SAM=8002, Universal=8003, ANNIF=8004, Eval=8005)")

    # Directory name: convert service_name to PascalCase for the directory
    dir_name = request.service_name.replace("-", "_").replace(" ", "_")
    dir_name = "".join(word.capitalize() for word in dir_name.split("_"))
    service_dir = _MODEL_API_BASE / dir_name

    if service_dir.exists():
        raise HTTPException(status_code=409, detail=f"Directory '{dir_name}' already exists under model_service/api/")

    # Read the template files
    template_dir = _MODEL_API_BASE / "Template"
    template_server = (template_dir / "server.py").read_text()
    template_dockerfile = (template_dir / "Dockerfile").read_text()
    template_requirements = (template_dir / "requirements.txt").read_text()

    # Customise server.py
    server_py = template_server
    # Replace configuration values
    server_py = server_py.replace('SERVICE_NAME = "custom-model"', f'SERVICE_NAME = "{request.service_name}"')
    server_py = server_py.replace('TOOL_NAME = "custom_predict"', f'TOOL_NAME = "{request.tool_name}"')
    server_py = server_py.replace(f'PORT = 8010', f'PORT = {request.port}')
    # Update tool description
    server_py = server_py.replace(
        'description="Your model\'s description here. Returns standardised evaluation-ready output."',
        f'description="{request.description}. Returns standardised evaluation-ready output."',
    )
    # Update the startup print
    server_py = server_py.replace(
        'print(f"Starting {SERVICE_NAME} MCP Server on port {PORT}")',
        f'print(f"Starting {{SERVICE_NAME}} MCP Server on port {{PORT}}")',
    )
    # Remove the docstring guide (it's the template instructions)
    server_py = re.sub(r'^""".*?"""\n\n', '', server_py, flags=re.DOTALL)

    # Customise Dockerfile — update the port
    dockerfile = template_dockerfile.replace("8010", str(request.port))
    # Update the build context path
    dockerfile = dockerfile.replace("Template", dir_name)

    # Create the directory and files
    service_dir.mkdir(parents=True)
    files_created = []

    (service_dir / "server.py").write_text(server_py)
    files_created.append(f"src/services/model_service/api/{dir_name}/server.py")

    (service_dir / "Dockerfile").write_text(dockerfile)
    files_created.append(f"src/services/model_service/api/{dir_name}/Dockerfile")

    (service_dir / "requirements.txt").write_text(template_requirements)
    files_created.append(f"src/services/model_service/api/{dir_name}/requirements.txt")

    # Docker service name
    docker_service = request.service_name.lower().replace("_", "-")
    container_name = docker_service

    # Build docker-compose snippet
    s3_env = ""
    if request.needs_s3:
        s3_env = """
      - S3_ENDPOINT_URL=${S3_ENDPOINT_URL}
      - S3_ACCESS_KEY=${S3_ACCESS_KEY}
      - S3_SECRET_KEY=${S3_SECRET_KEY}
      - S3_BUCKET_NAME=${S3_BUCKET_NAME}"""

    docker_compose_entry = f"""  {docker_service}-api:
    build:
      context: ../../../../
      dockerfile: src/services/model_service/api/{dir_name}/Dockerfile
    container_name: {container_name}
    environment:
      - PYTHONPATH=/app{s3_env}
    restart: unless-stopped
    networks:
      - backend-network"""

    # Create DB record
    location = f"http://{docker_service}-api:{request.port}"
    try:
        db_model = Modelmetadata(
            name=request.service_name,
            model_type=bool(request.model_type),
            location=location,
            mcp_tool_name=request.tool_name,
            acceptable_formats=request.acceptable_formats,
            output_context=request.output_context,
            task=request.task,
        )
        session.add(db_model)
        session.commit()
        session.refresh(db_model)
    except Exception as e:
        # Clean up created files on DB failure
        import shutil
        shutil.rmtree(service_dir, ignore_errors=True)
        session.rollback()
        raise HTTPException(status_code=500, detail=f"DB error (files cleaned up): {str(e)}")

    return ModelScaffoldResponse(
        model_metadata_id=db_model.id,
        service_name=request.service_name,
        tool_name=request.tool_name,
        port=request.port,
        directory=f"src/services/model_service/api/{dir_name}/",
        files_created=files_created,
        docker_compose_entry=docker_compose_entry,
        message=(
            f"MCP service '{request.service_name}' scaffolded. "
            f"Implement _get_model(), _standardise_output(), and _translate_input() in server.py, "
            f"then add the docker-compose entry and run: docker compose up {docker_service}-api"
        ),
    )


@router.get("/model/{model_id}/mcp-status/")
async def get_model_mcp_status(
    model_id: int,
    session: SessionDep,
    current_user: User = Depends(get_current_instigator_or_superuser),
):
    """Check MCP server health and list available tools for a model.

    Connects to the model's MCP server via SSE and calls list_tools().
    Returns the tools and their schemas, or an error if unreachable.
    """
    statement = select(Modelmetadata).where(Modelmetadata.id == model_id)
    model = session.exec(statement).first()
    if not model:
        raise HTTPException(status_code=404, detail="Model metadata not found")

    if not model.location:
        raise HTTPException(status_code=400, detail="Model has no location (server URL) configured")

    from src.services.utility_service.mcp_client import MCPClientManager

    client = MCPClientManager()
    try:
        tools = await client.list_tools(model.location)
        tool_list = [
            {
                "name": t.name,
                "description": t.description,
                "input_schema": t.inputSchema,
            }
            for t in tools
        ]
        return {
            "model_id": model.id,
            "model_name": model.name,
            "location": model.location,
            "mcp_tool_name": model.mcp_tool_name,
            "status": "online",
            "tools": tool_list,
        }
    except Exception as e:
        return {
            "model_id": model.id,
            "model_name": model.name,
            "location": model.location,
            "mcp_tool_name": model.mcp_tool_name,
            "status": "offline",
            "error": str(e),
            "tools": [],
        }
