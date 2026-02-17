from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse

from src.api.deps import (
    SessionDep, get_current_user
)

from src.models import *

# Import service layer functions
from src.services.performance_service import evaluation_service

router = APIRouter(prefix="/evaluation", tags=["Performance Analysis"])


@router.get('/status/{audit_id}/summary')
def get_status_summary(
    audit_id: int,
    session: SessionDep,
    current_user = Depends(get_current_user)
):
    """Get the status summary for an audit including all event-metric pairs"""
    try:
        result = evaluation_service.get_status_summary_comprehensive(
            audit_id=audit_id,
            current_user_id=current_user.id,
            session=session
        )
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get status summary: {str(e)}")


@router.put('/status/{audit_id}/submit')
def submit_audit(
    audit_id: int,
    submission: AuditSubmit,
    session: SessionDep,
    current_user = Depends(get_current_user)
):
    """Submit audit with final recommendation and notes"""
    try:
        result = evaluation_service.submit_audit_comprehensive(
            audit_id=audit_id,
            submission=submission,
            current_user_id=current_user.id,
            session=session
        )
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to submit audit: {str(e)}")


@router.put('/status/{audit_id}')
def update_status(
    audit_id: int,
    updated_data: AuditStatusUpdate,
    session: SessionDep,
    current_user = Depends(get_current_user)
):
    """Update status for a single event-metric pair"""
    try:
        result = evaluation_service.update_status_comprehensive(
            audit_id=audit_id,
            updated_data=updated_data,
            current_user_id=current_user.id,
            session=session
        )
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update status: {str(e)}")


@router.put('/status/{audit_id}/batch')
def update_status_batch(
    audit_id: int,
    batch_updated_data: BatchAuditStatusUpdate,
    session: SessionDep,
    current_user = Depends(get_current_user)
):
    """Update status for multiple event-metric pairs in batch"""
    try:
        result = evaluation_service.update_status_batch_comprehensive(
            audit_id=audit_id,
            batch_updated_data=batch_updated_data,
            current_user_id=current_user.id,
            session=session
        )
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to batch update status: {str(e)}")


@router.get('/results/{audit_id}/summary')
def get_results_summary(
    audit_id: int,
    session: SessionDep,
    current_user = Depends(get_current_user)
):
    """Get comprehensive results summary for an audit with all event-metric pairs"""
    try:
        result = evaluation_service.get_results_summary_comprehensive(
            audit_id=audit_id,
            current_user_id=current_user.id,
            session=session
        )
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get results summary: {str(e)}")


@router.get('/results/{audit_id}/output/summary')
def get_output_evaluation_summary(
    audit_id: int,
    session: SessionDep,
    current_user = Depends(get_current_user)
):
    """Get summary of output evaluation results for an audit"""
    try:
        result = evaluation_service.get_output_evaluation_summary_comprehensive(
            audit_id=audit_id,
            current_user_id=current_user.id,
            session=session
        )
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get output evaluation summary: {str(e)}")


@router.delete('/results/{audit_id}/output/clear')
def clear_output_evaluation_results(
    audit_id: int,
    session: SessionDep,
    current_user = Depends(get_current_user)
):
    """Clear cached output evaluation results to force re-running inference"""
    try:
        result = evaluation_service.clear_output_evaluation_results_comprehensive(
            audit_id=audit_id,
            current_user_id=current_user.id,
            session=session
        )
        return JSONResponse(status_code=200, content=result)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to clear output evaluation results: {str(e)}")


@router.post('/results/{audit_id}/generate/output')
async def generate_output_evaluation_results(
    audit_id: int,
    session: SessionDep,
    current_user = Depends(get_current_user)
):
    """Generate output evaluation results by running inference on uploaded data"""
    try:
        result = await evaluation_service.classify_output_comprehensive(
            audit_id=audit_id,
            current_user_id=current_user.id,
            session=session
        )
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate output evaluation results: {str(e)}")


@router.get('/results/{audit_id}/output')
async def get_output_results(
    audit_id: int,
    session: SessionDep,
    current_user = Depends(get_current_user)
):
    """Retrieve generated output classification results for an audit"""
    try:
        result = await evaluation_service.get_output_results_comprehensive(
            audit_id=audit_id,
            current_user_id=current_user.id,
            session=session
        )
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get output results: {str(e)}")


@router.put('/outcome/{audit_id}/batch')
def update_outcome_evaluation_batch(
    audit_id: int,
    batch_updated_data: list[AuditStatusUpdate],
    session: SessionDep,
    current_user = Depends(get_current_user)
):
    """Batch update outcome evaluation values (meet_requirement status and notes)"""
    try:
        result = evaluation_service.update_outcome_evaluation_batch_comprehensive(
            audit_id=audit_id,
            batch_updated_data=batch_updated_data,
            current_user_id=current_user.id,
            session=session
        )
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to batch update outcome evaluation: {str(e)}")


@router.post('/results/{audit_id}/generate/')
async def generate_results(
    audit_id: int,
    session: SessionDep,
    current_user = Depends(get_current_user)
):
    """Generate evaluation results by running inference and evaluation on datasets"""
    try:
        result = await evaluation_service.generate_results_comprehensive(
            audit_id=audit_id,
            current_user_id=current_user.id,
            session=session
        )
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate results: {str(e)}")
