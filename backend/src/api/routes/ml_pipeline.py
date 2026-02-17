import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import col, delete, func, select

from src.api.deps import (
    SessionDep,get_current_user
)

from src.models import *
from src.services.audit_service import ml_flow_service

router = APIRouter(prefix="/pipeline", tags=["AI Pipeline"])

@router.post("/api-keys/", response_model=Apikeymodel)
def create_api_key(api_key_data: ApikeymodelCreate, session: SessionDep):
    """Create a new API key entry"""
    try:
        # Create new API key instance
        db_api_key = ml_flow_service.create_api_key(session = session, api_key_data=api_key_data)
        
        return db_api_key
        
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=400, detail=f"Error creating API key: {str(e)}")

@router.post("/model-metadata/", response_model=Modelmetadata)
def create_model_metadata(model_data: ModelmetadataCreate, session: SessionDep):
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
def get_model_metadata(model_id: int,  session: SessionDep):
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
    current_user: User = Depends(get_current_user)
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
            message="Dataset created successfully with input and output metadata"
        )
        
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=400, detail=f"Error creating complete dataset: {str(e)}")
    
@router.get("/dataset/metadata/{dataset_id}", response_model=DatasetCompleteResponse)
def get_complete_dataset(
    dataset_id: int, 
    session: SessionDep,
    current_user: User = Depends(get_current_user)
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

@router.get("/dataset/input/{input_id}", response_model=InputDatasetMetadata)
def get_input_dataset_metadata(input_id: int, session: SessionDep):
    """Get input dataset metadata by ID"""
    statement = select(InputDatasetMetadata).where(InputDatasetMetadata.id == input_id)
    input_data = session.exec(statement).first()
    if not input_data:
        raise HTTPException(status_code=404, detail="Input dataset metadata not found")
    return input_data

@router.get("/dataset/output/{output_id}", response_model=OutputDatasetMetadata)
def get_output_dataset_metadata(output_id: int, session: SessionDep):
    """Get output dataset metadata by ID"""
    statement = select(OutputDatasetMetadata).where(OutputDatasetMetadata.id == output_id)
    output_data = session.exec(statement).first()
    if not output_data:
        raise HTTPException(status_code=404, detail="Output dataset metadata not found")
    return output_data

@router.get("/model/", response_model=list[Modelmetadata])
def list_model_metadata(session: SessionDep, skip: int = 0, limit: int = 100):
    """List all model metadata with pagination"""
    statement = select(Modelmetadata).offset(skip).limit(limit)
    models = session.exec(statement).all()
    return models

@router.put("/api-keys/{api_key_id}", response_model=Apikeymodel)
def update_api_key(api_key_id: int, api_key_update: ApikeymodelUpdate, session: SessionDep):
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
def update_model_metadata(model_id: int, model_update: ModelmetadataUpdate, session: SessionDep):
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
    session: SessionDep
):
    """Update an existing dataset metadata"""
    try:
        db_dataset = ml_flow_service.update_dataset_metadata(dataset_id=dataset_id, dataset_update=dataset_update, session=session)
        
        return db_dataset
        
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=400, detail=f"Error updating dataset metadata: {str(e)}")

@router.put("/dataset/metadata/{dataset_id}/all")
def update_dataset_with_input_output(dataset_id: int, dataset_update: DatasetWithInputOutputUpdate, session: SessionDep):
    """Update dataset metadata with optional input/output metadata updates"""
    try:
        response_data = ml_flow_service.update_dataset_with_input_output(dataset_id=dataset_id, dataset_update=dataset_update, session=session)
        
        return response_data
        
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=400, detail=f"Error updating dataset with metadata: {str(e)}")

@router.delete("/api-keys/{api_key_id}")
def delete_api_key(api_key_id: int, session: SessionDep):
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
def delete_model_metadata(model_id: int, session: SessionDep):
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
def delete_dataset_metadata(dataset_id: int, session: SessionDep):
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
def delete_input_dataset_metadata(input_id: int, session: SessionDep):
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
def delete_output_dataset_metadata(output_id: int, session: SessionDep):
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
    