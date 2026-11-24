import uuid
from typing import Any
from fastapi import HTTPException

from sqlmodel import Session, select

from src.models import *

def create_api_key(*, session: Session, api_key_data: ApikeymodelCreate, user_id: uuid.UUID) -> Any:

    db_api_key = Apikeymodel(
        user_id=user_id,
        model_api_key=api_key_data.model_api_key,
        costing_policy=api_key_data.costing_policy,
        model_metadata_id=api_key_data.model_metadata_id
    )
    
    # Add to database
    session.add(db_api_key)
    session.commit()
    session.refresh(db_api_key)
    
    return db_api_key

def get_api_key(model_id:int, user_id: uuid, session: Session):
    """Get an API key by user_id and model_id"""
    statement = select(Apikeymodel).where(Apikeymodel.user_id == user_id and Apikeymodel.model_id == model_id)
    api_key = session.exec(statement).first()
    
    return api_key

def update_api_key(api_key_id:int, api_key_update: ApikeymodelUpdate, session: Session):
    # Get existing API key
    statement = select(Apikeymodel).where(Apikeymodel.id == api_key_id)
    db_api_key = session.exec(statement).first()
    
    if not db_api_key:
        raise HTTPException(status_code=404, detail="API key not found")
    
    # Update only provided fields
    update_data = api_key_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_api_key, field, value)
    
    session.add(db_api_key)
    session.commit()
    session.refresh(db_api_key)
    
    return db_api_key

def delete_api_key(api_key_id: int, session: Session):
    statement = select(Apikeymodel).where(Apikeymodel.id == api_key_id)
    db_api_key = session.exec(statement).first()
    
    if not db_api_key:
        raise HTTPException(status_code=404, detail="API key not found")
    
    # Get dependent model metadata and set their api_key_id to null
    model_statement = select(Modelmetadata).where(Modelmetadata.api_key_id == api_key_id)
    dependent_models = session.exec(model_statement).all()
    
    # Set api_key_id to null for all dependent model metadata
    for model in dependent_models:
        model.api_key_id = None
        session.add(model)
    
    # Now delete the API key
    session.delete(db_api_key)
    session.commit()
    
    if dependent_models:
        return {
            "message": f"API key deleted successfully. {len(dependent_models)} model metadata entries had their api_key_id set to null."
        }
    else:
        return {"message": "API key deleted successfully"}

def create_model_metadata(*, session: Session, model_data: ModelmetadataCreate) -> Any:
    # Create new model metadata instance
    db_model = Modelmetadata(
        name=model_data.name,
        model_type=model_data.model_type,
        location=model_data.location,
        acceptable_formats=model_data.acceptable_formats,
        output_context=model_data.output_context,
        task=model_data.task
    )
    
    # Add to database
    session.add(db_model)
    session.commit()
    session.refresh(db_model)
    
    return db_model

def update_model_metadata(model_id: int, model_update: ModelmetadataUpdate, session: Session):
    statement = select(Modelmetadata).where(Modelmetadata.id == model_id)
    db_model = session.exec(statement).first()
    
    if not db_model:
        raise HTTPException(status_code=404, detail="Model metadata not found")
    
    # Validate API key exists if being updated
    update_data = model_update.model_dump(exclude_unset=True)
    if 'api_key_id' in update_data:
        raise HTTPException(status_code=404, detail="API key not found")
    
    # Update only provided fields
    for field, value in update_data.items():
        setattr(db_model, field, value)
    
    session.add(db_model)
    session.commit()
    session.refresh(db_model)
    
    return db_model

def create_dataset_metadata(*, session: Session, dataset_data: DatasetWithInputOutputCreate) -> Any:
    # Create new dataset metadata instance
    db_dataset = DatasetMetadata(
        purpose=dataset_data.purpose,
        copyright_agreement=dataset_data.copyright_agreement
    )
    
    # Add to database and flush to get ID
    session.add(db_dataset)
    session.flush()  # This assigns the ID without committing
    
    response_data = {
        "dataset_metadata": db_dataset,
        "input_metadata": None,
        "output_metadata": None
    }
    
    # Create input metadata if provided
    if dataset_data.input_metadata:
        db_input = InputDatasetMetadata(
            dataset_metadata_id=db_dataset.id,
            headers=dataset_data.input_metadata.headers,
            benchmark_dataset=dataset_data.input_metadata.benchmark_dataset,
            datatypes=dataset_data.input_metadata.datatypes,
            location=dataset_data.input_metadata.location
        )
        session.add(db_input)
        session.flush()
        response_data["input_metadata"] = db_input
    
    # Create output metadata if provided
    if dataset_data.output_metadata:
        db_output = OutputDatasetMetadata(
            dataset_metadata_id=db_dataset.id,
            headers=dataset_data.output_metadata.headers,
            benchmark_dataset=dataset_data.output_metadata.benchmark_dataset,
            datatypes=dataset_data.output_metadata.datatypes,
            location=dataset_data.output_metadata.location
        )
        session.add(db_output)
        session.flush()
        response_data["output_metadata"] = db_output
    
    # Commit all changes
    session.commit()
    
    # Refresh all objects
    session.refresh(db_dataset)
    if response_data["input_metadata"]:
        session.refresh(response_data["input_metadata"])
    if response_data["output_metadata"]:
        session.refresh(response_data["output_metadata"])
    
    return response_data

def update_dataset_metadata(dataset_id: int, dataset_update: DatasetWithInputOutputUpdate, session: Session):
    statement = select(DatasetMetadata).where(DatasetMetadata.id == dataset_id)
    db_dataset = session.exec(statement).first()
    
    if not db_dataset:
        raise HTTPException(status_code=404, detail="Dataset metadata not found")
    
    # Update only provided fields
    update_data = dataset_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_dataset, field, value)
    
    session.add(db_dataset)
    session.commit()
    session.refresh(db_dataset)
    
    return db_dataset

def update_dataset_with_input_output(dataset_id: int, dataset_update: DatasetWithInputOutputUpdate, session: Session):
    statement = select(DatasetMetadata).where(DatasetMetadata.id == dataset_id)
    db_dataset = session.exec(statement).first()
    
    if not db_dataset:
        raise HTTPException(status_code=404, detail="Dataset metadata not found")
    
    response_data = {
        "dataset_metadata": db_dataset,
        "input_metadata": None,
        "output_metadata": None,
        "operations": []
    }
    
    # Update dataset metadata fields if provided
    if dataset_update.purpose is not None:
        db_dataset.purpose = dataset_update.purpose
        response_data["operations"].append("Updated dataset purpose")
    
    if dataset_update.copyright_agreement is not None:
        db_dataset.copyright_agreement = dataset_update.copyright_agreement
        response_data["operations"].append("Updated copyright agreement")
    
    # Handle input metadata update/creation
    if dataset_update.input_metadata:
        # Check if input metadata already exists
        input_statement = select(InputDatasetMetadata).where(
            InputDatasetMetadata.dataset_metadata_id == dataset_id
        )
        existing_input = session.exec(input_statement).first()
        
        if existing_input:
            # Update existing input metadata
            input_update_data = dataset_update.input_metadata.model_dump(exclude_unset=True)
            for field, value in input_update_data.items():
                if field != 'dataset_metadata_id':  # Don't update the foreign key
                    setattr(existing_input, field, value)
            response_data["input_metadata"] = existing_input
            response_data["operations"].append("Updated existing input metadata")
        else:
            # Create new input metadata
            new_input = InputDatasetMetadata(
                dataset_metadata_id=dataset_id,
                headers=dataset_update.input_metadata.headers or {},
                benchmark_dataset=dataset_update.input_metadata.benchmark_dataset or False,
                datatypes=dataset_update.input_metadata.datatypes or {},
                location=dataset_update.input_metadata.location
            )
            session.add(new_input)
            response_data["input_metadata"] = new_input
            response_data["operations"].append("Created new input metadata")
    
    # Handle output metadata update/creation
    if dataset_update.output_metadata:
        # Check if output metadata already exists
        output_statement = select(OutputDatasetMetadata).where(
            OutputDatasetMetadata.dataset_metadata_id == dataset_id
        )
        existing_output = session.exec(output_statement).first()
        
        if existing_output:
            # Update existing output metadata
            output_update_data = dataset_update.output_metadata.model_dump(exclude_unset=True)
            for field, value in output_update_data.items():
                if field != 'dataset_metadata_id':  # Don't update the foreign key
                    setattr(existing_output, field, value)
            response_data["output_metadata"] = existing_output
            response_data["operations"].append("Updated existing output metadata")
        else:
            # Create new output metadata
            new_output = OutputDatasetMetadata(
                dataset_metadata_id=dataset_id,
                headers=dataset_update.output_metadata.headers or {},
                benchmark_dataset=dataset_update.output_metadata.benchmark_dataset or False,
                datatypes=dataset_update.output_metadata.datatypes or {},
                location=dataset_update.output_metadata.location
            )
            session.add(new_output)
            response_data["output_metadata"] = new_output
            response_data["operations"].append("Created new output metadata")
    
    # Commit all changes
    session.commit()
    
    # Refresh all objects
    session.refresh(db_dataset)
    if response_data["input_metadata"]:
        session.refresh(response_data["input_metadata"])
    if response_data["output_metadata"]:
        session.refresh(response_data["output_metadata"])
        
    return response_data