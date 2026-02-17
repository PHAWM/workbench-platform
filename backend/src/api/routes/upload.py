from fastapi import UploadFile, APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from typing import List

from src.api.deps import (
    SessionDep, get_current_user
)

from src.models import *

# Import service layer functions
from src.services.audit_service import upload_service

router = APIRouter(prefix="/upload", tags=["AI Pipeline"])


@router.post("/dataset/{audit_id}/single")
def upload_dataset(
    file: UploadFile,
    audit_id: int,
    session: SessionDep,
    current_user = Depends(get_current_user)
):
    """Upload a dataset file to the evaluation system"""
    try:
        result = upload_service.upload_dataset_comprehensive(
            file=file,
            audit_id=audit_id,
            current_user_id=current_user.id,
            session=session
        )
        return JSONResponse(status_code=200, content=result)
    except HTTPException:
        session.rollback()
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@router.post("/dataset/{audit_id}/multiple")
def upload_multiple_datasets(
    files: List[UploadFile],
    audit_id: int,
    session: SessionDep,
    current_user = Depends(get_current_user)
):
    """Upload multiple dataset files including metadata.csv"""
    try:
        result = upload_service.upload_multiple_datasets_comprehensive(
            files=files,
            audit_id=audit_id,
            current_user_id=current_user.id,
            session=session
        )
        return JSONResponse(status_code=200, content=result)
    except HTTPException:
        session.rollback()
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@router.post("/audit/{audit_id}/input")
def upload_audit_input(
    file: UploadFile,
    audit_id: int,
    session: SessionDep,
    current_user = Depends(get_current_user)
):
    """Upload input data for an audit (audit instigator)"""
    try:
        result = upload_service.upload_audit_input_comprehensive(
            file=file,
            audit_id=audit_id,
            current_user_id=current_user.id,
            session=session
        )
        return JSONResponse(status_code=200, content=result)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@router.get("/dataset/{audit_id}")
def list_uploaded_datasets(
    audit_id: int,
    session: SessionDep,
    current_user = Depends(get_current_user)
):
    """List all uploaded dataset files for a specific audit and user"""
    try:
        result = upload_service.list_uploaded_datasets_comprehensive(
            audit_id=audit_id,
            current_user_id=current_user.id,
            session=session
        )
        return JSONResponse(status_code=200, content=result)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list files: {str(e)}")


@router.get("/audit/{audit_id}/files")
def list_audit_files(
    audit_id: int,
    session: SessionDep,
    current_user = Depends(get_current_user)
):
    """List all input files for a specific audit"""
    try:
        result = upload_service.list_audit_files_comprehensive(
            audit_id=audit_id,
            current_user_id=current_user.id,
            session=session
        )
        return JSONResponse(status_code=200, content=result)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list files: {str(e)}")


@router.delete("/dataset/{audit_id}")
def delete_dataset_file(
    audit_id: int,
    files: UploadFileDelete,
    session: SessionDep,
    current_user = Depends(get_current_user)
):
    """Delete an uploaded dataset file for a specific audit and user"""
    try:
        result = upload_service.delete_dataset_file_comprehensive(
            audit_id=audit_id,
            filename=files.filename,
            current_user_id=current_user.id,
            session=session
        )
        return JSONResponse(status_code=200, content=result)
    except HTTPException:
        session.rollback()
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to delete file: {str(e)}")


@router.get("/audit/{audit_id}/view/{filename:path}")
def view_audit_file(
    audit_id: int,
    filename: str,
    session: SessionDep,
    current_user = Depends(get_current_user)
):
    """View/download an audit input file or results.csv"""
    try:
        file_path, file_name = upload_service.view_audit_file_comprehensive(
            audit_id=audit_id,
            filename=filename,
            current_user_id=current_user.id,
            session=session
        )
        return FileResponse(
            path=str(file_path),
            filename=file_name,
            media_type='application/octet-stream'
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve file: {str(e)}")
