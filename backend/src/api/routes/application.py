from datetime import datetime, timezone
from typing import Any, List

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import col, delete, func, select

from src.api.deps import (
    SessionDep, get_current_user, get_audit_instigator_access, get_current_tenant_id,
    TenantAdmin
)

from src.models import *
from src.services.audit_service import (
    application_service,
    audit_setup_service,
    audit_overview_service,
    audit_creation_service,
    audit_complete_service,
    audit_outcome_service
)

router = APIRouter(prefix="/audits", tags=["Audit Management"])


@router.get("/")
def get_all_audits_overview(session: SessionDep, current_user: User = Depends(get_current_user)):
    """Get all audits overview for the current user"""
    try:
        audit_overviews, status_summary = audit_overview_service.get_all_audits_overview_comprehensive(
            current_user_id=current_user.id,
            session=session
        )

        return AllAuditsOverviewResponse(
            audits=[AuditOverviewResponse(**audit) for audit in audit_overviews],
            total_audits=len(audit_overviews),
            status_summary=status_summary
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get audits overview: {str(e)}")


@router.get("/{audit_id}")
def get_audit_overview(audit_id: int, session: SessionDep, current_user: User = Depends(get_current_user)):
    """Get single audit overview with application details. Sets started_at on first access."""
    try:
        # Stamp started_at the first time this user opens the audit
        user_audit = session.exec(
            select(MappingAuditUser).where(
                MappingAuditUser.audit_id == audit_id,
                MappingAuditUser.user_id == current_user.id,
            )
        ).first()
        if user_audit and user_audit.started_at is None:
            user_audit.started_at = datetime.now(timezone.utc)
            session.add(user_audit)
            session.commit()

        audit_data = audit_overview_service.get_audit_overview_comprehensive(
            audit_id=audit_id,
            current_user_id=current_user.id,
            session=session
        )

        return AuditOverviewResponse(**audit_data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get audit overview: {str(e)}")


@router.post("/")
def create_audit(
    audit_data: AuditCompleteCreate,
    session: SessionDep,
    current_user: User = Depends(get_current_user)
):
    """Create audit with model associations and pipeline setup.

    The creating user is automatically assigned as audit_instigator.
    A pipeline is always created.
    """
    try:
        result = audit_creation_service.create_audit_comprehensive(
            audit_data=audit_data,
            current_user_id=current_user.id,
            session=session
        )

        return AuditCompleteCreateResponse(**result)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create audit: {str(e)}")


@router.put("/{audit_id}")
def update_audit(
    audit_id: int,
    audit_update: AuditUpdate,
    session: SessionDep,
    audit_access=Depends(get_audit_instigator_access)
):
    """Update audit name/description. Only the audit_instigator can do this."""
    try:
        result = audit_creation_service.update_audit_comprehensive(
            audit_id=audit_id,
            audit_update=audit_update,
            session=session
        )
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update audit: {str(e)}")


@router.delete("/{audit_id}")
def delete_audit(
    audit_id: int,
    session: SessionDep,
    audit_access=Depends(get_audit_instigator_access)
):
    """Delete audit and all associated data. Only the audit_instigator can do this."""
    try:
        result = audit_creation_service.delete_audit_comprehensive(
            audit_id=audit_id,
            session=session
        )
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete audit: {str(e)}")


@router.get("/{audit_id}/complete")
def get_audit_complete(
    audit_id: int | str,
    session: SessionDep,
    current_user: User = Depends(get_current_user)
):
    """Get comprehensive audit information with all relationships"""
    try:
        if isinstance(audit_id, str):
            audit_list = audit_complete_service.get_all_audits_complete_comprehensive(
                current_user_id=current_user.id,
                session=session
            )
            return [AuditCompleteResponse(**audit) for audit in audit_list]
        else:
            audit_data = audit_complete_service.get_single_audit_complete_comprehensive(
                audit_id=audit_id,
                current_user_id=current_user.id,
                session=session
            )
            return AuditCompleteResponse(**audit_data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get complete audit: {str(e)}")


@router.get("/{audit_id}/summary")
async def get_audit_summary(audit_id: int, session: SessionDep, current_user: User = Depends(get_current_user)):
    """Get audit summary with serialized JSON fields"""
    try:
        # Verify user has access to this audit
        audit_user_check = select(MappingAuditUser).where(
            MappingAuditUser.audit_id == audit_id,
            MappingAuditUser.user_id == current_user.id
        )
        if not session.exec(audit_user_check).first():
            raise HTTPException(status_code=403, detail="Access denied to this audit")

        audit_details = audit_setup_service.get_audit_details(session, audit_id, current_user.id)

        # Get application with JSON fields serialized
        application = session.get(Application, audit_details["audit"]["id"])
        if application:
            testing_evaluation_json = application.model_dump_json(include={"testing_evaluation"})
            deployment_json = application.model_dump_json(include={"deployment"})

            return {
                "audit_summary": audit_details,
                "application_testing": testing_evaluation_json,
                "application_deployment": deployment_json
            }

        return audit_details
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get audit summary: {str(e)}")


@router.put("/{audit_id}/outcome")
def update_audit_outcome(
    audit_id: int,
    outcome_data: AuditOutcomeUpdate,
    session: SessionDep,
    current_user: User = Depends(get_current_user)
):
    """Update audit outcome for the current user"""
    try:
        result = audit_outcome_service.update_audit_outcome_comprehensive(
            audit_id=audit_id,
            outcome_data=outcome_data,
            current_user_id=current_user.id,
            session=session
        )
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update audit outcome: {str(e)}")


@router.get("/{audit_id}/outcome")
def get_audit_outcome(
    audit_id: int,
    session: SessionDep,
    current_user: User = Depends(get_current_user)
):
    """Get audit outcome for the current user"""
    try:
        result = audit_outcome_service.get_audit_outcome_comprehensive(
            audit_id=audit_id,
            current_user_id=current_user.id,
            session=session
        )
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get audit outcome: {str(e)}")


# ---------------------------------------------------------------------------
# Audit timing — submit + active session tracking
# ---------------------------------------------------------------------------

@router.post("/{audit_id}/submit", response_model=AuditTimingResponse)
def submit_audit(
    audit_id: int,
    session: SessionDep,
    current_user: User = Depends(get_current_user),
):
    """Mark the audit as submitted for the current user.

    Sets submitted_at to now and computes duration_seconds from started_at.
    Idempotent — calling it again updates submitted_at but does not reset started_at.
    """
    user_audit = session.exec(
        select(MappingAuditUser).where(
            MappingAuditUser.audit_id == audit_id,
            MappingAuditUser.user_id == current_user.id,
        )
    ).first()
    if not user_audit:
        raise HTTPException(status_code=403, detail="Access denied to this audit")

    now = datetime.now(timezone.utc)
    user_audit.submitted_at = now

    if user_audit.started_at is not None:
        started = user_audit.started_at
        if started.tzinfo is None:
            started = started.replace(tzinfo=timezone.utc)
        user_audit.duration_seconds = int((now - started).total_seconds())

    session.add(user_audit)
    session.commit()
    session.refresh(user_audit)

    return AuditTimingResponse(
        user_audit_id=user_audit.id,
        audit_id=audit_id,
        started_at=user_audit.started_at,
        submitted_at=user_audit.submitted_at,
        duration_seconds=user_audit.duration_seconds,
        active_seconds=user_audit.active_seconds,
    )


@router.post("/{audit_id}/session", response_model=AuditTimingResponse)
def record_session_chunk(
    audit_id: int,
    body: AuditSessionChunkCreate,
    session: SessionDep,
    current_user: User = Depends(get_current_user),
):
    """Accumulate an active-time chunk from the frontend.

    The frontend should call this whenever the auditor navigates away from
    an audit page, sending the number of seconds the tab was actively open.
    The backend stores each chunk and adds to active_seconds on MappingAuditUser.
    """
    if body.duration_seconds <= 0:
        raise HTTPException(status_code=400, detail="duration_seconds must be positive")

    user_audit = session.exec(
        select(MappingAuditUser).where(
            MappingAuditUser.audit_id == audit_id,
            MappingAuditUser.user_id == current_user.id,
        )
    ).first()
    if not user_audit:
        raise HTTPException(status_code=403, detail="Access denied to this audit")

    chunk = AuditSessionChunk(
        user_audit_id=user_audit.id,
        duration_seconds=body.duration_seconds,
    )
    session.add(chunk)

    user_audit.active_seconds = (user_audit.active_seconds or 0) + body.duration_seconds
    session.add(user_audit)
    session.commit()
    session.refresh(user_audit)

    return AuditTimingResponse(
        user_audit_id=user_audit.id,
        audit_id=audit_id,
        started_at=user_audit.started_at,
        submitted_at=user_audit.submitted_at,
        duration_seconds=user_audit.duration_seconds,
        active_seconds=user_audit.active_seconds,
    )


@router.get("/{audit_id}/timing", response_model=AuditTimingResponse)
def get_audit_timing(
    audit_id: int,
    session: SessionDep,
    current_user: User = Depends(get_current_user),
):
    """Return timing data for the current user's audit session."""
    user_audit = session.exec(
        select(MappingAuditUser).where(
            MappingAuditUser.audit_id == audit_id,
            MappingAuditUser.user_id == current_user.id,
        )
    ).first()
    if not user_audit:
        raise HTTPException(status_code=403, detail="Access denied to this audit")

    return AuditTimingResponse(
        user_audit_id=user_audit.id,
        audit_id=audit_id,
        started_at=user_audit.started_at,
        submitted_at=user_audit.submitted_at,
        duration_seconds=user_audit.duration_seconds,
        active_seconds=user_audit.active_seconds,
    )


# ---------------------------------------------------------------------------
# Pipeline — model/dataset wiring
# ---------------------------------------------------------------------------

@router.get("/{audit_id}/pipeline", response_model=PipelineOverviewResponse)
def get_audit_pipeline(
    audit_id: int,
    session: SessionDep,
    current_user: User = Depends(get_current_user),
):
    """Return the pipeline for this audit with all model-dataset pairs.

    This is the primary endpoint the frontend uses to show the instigator
    which models and datasets are wired into the pipeline, and to let them
    decide what to add or remove.  Accessible to any user linked to the audit.
    """
    # Verify user access
    user_audit = session.exec(
        select(MappingAuditUser).where(
            MappingAuditUser.audit_id == audit_id,
            MappingAuditUser.user_id == current_user.id,
        )
    ).first()
    if not user_audit:
        raise HTTPException(status_code=403, detail="Access denied to this audit")

    # Get the pipeline for this audit
    pipeline_audit = session.exec(
        select(MappingAuditPipelineAudit).where(
            MappingAuditPipelineAudit.audit_id == audit_id
        )
    ).first()
    if not pipeline_audit:
        raise HTTPException(status_code=404, detail="No pipeline found for this audit")

    pipeline_id = pipeline_audit.audit_pipeline

    # Fetch all model-dataset pairs for the pipeline
    pairs_rows = session.exec(
        select(MappingModelDatasetAudit).where(
            MappingModelDatasetAudit.auditpipeline == pipeline_id
        )
    ).all()

    pairs = []
    model_ids_seen = set()
    dataset_ids_seen = set()

    for row in pairs_rows:
        model = session.get(Modelmetadata, row.model_id)
        dataset = session.get(DatasetMetadata, row.dataset_id)
        if not model or not dataset:
            continue

        has_input = session.exec(
            select(InputDatasetMetadata).where(
                InputDatasetMetadata.dataset_metadata_id == dataset.id
            )
        ).first() is not None

        has_output = session.exec(
            select(OutputDatasetMetadata).where(
                OutputDatasetMetadata.dataset_metadata_id == dataset.id
            )
        ).first() is not None

        pairs.append(PipelineModelDatasetPair(
            mapping_id=row.id,
            model_id=model.id,
            model_name=model.name,
            dataset_id=dataset.id,
            dataset_purpose=dataset.purpose,
            dataset_has_input=has_input,
            dataset_has_output=has_output,
        ))
        model_ids_seen.add(model.id)
        dataset_ids_seen.add(dataset.id)

    return PipelineOverviewResponse(
        audit_id=audit_id,
        pipeline_id=pipeline_id,
        pairs=pairs,
        total_models=len(model_ids_seen),
        total_datasets=len(dataset_ids_seen),
    )


@router.post("/{audit_id}/pipeline/model-dataset", response_model=PipelineOverviewResponse)
def add_pipeline_model_dataset(
    audit_id: int,
    body: PipelineModelDatasetAdd,
    session: SessionDep,
    current_user: User = Depends(get_current_user),
    audit_access=Depends(get_audit_instigator_access),
):
    """Wire a model-dataset pair into this audit's pipeline.

    Only the audit_instigator can call this.  Use this after audit creation
    to add additional models or datasets, or to connect a gray-box results
    dataset to its model.  Returns the full updated pipeline overview.
    """
    pipeline_audit = session.exec(
        select(MappingAuditPipelineAudit).where(
            MappingAuditPipelineAudit.audit_id == audit_id
        )
    ).first()
    if not pipeline_audit:
        raise HTTPException(status_code=404, detail="No pipeline found for this audit")

    model = session.get(Modelmetadata, body.model_id)
    if not model:
        raise HTTPException(status_code=404, detail=f"Model {body.model_id} not found")

    dataset = session.get(DatasetMetadata, body.dataset_id)
    if not dataset:
        raise HTTPException(status_code=404, detail=f"Dataset {body.dataset_id} not found")

    # Prevent duplicate pairs
    existing = session.exec(
        select(MappingModelDatasetAudit).where(
            MappingModelDatasetAudit.auditpipeline == pipeline_audit.audit_pipeline,
            MappingModelDatasetAudit.model_id == body.model_id,
            MappingModelDatasetAudit.dataset_id == body.dataset_id,
        )
    ).first()
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"Model {body.model_id} + Dataset {body.dataset_id} already wired into this pipeline"
        )

    # Also ensure the model is linked to the audit itself
    audit_model = session.exec(
        select(MappingAuditModel).where(
            MappingAuditModel.audit_id == audit_id,
            MappingAuditModel.model_id == body.model_id,
        )
    ).first()
    if not audit_model:
        session.add(MappingAuditModel(audit_id=audit_id, model_id=body.model_id))

    session.add(MappingModelDatasetAudit(
        auditpipeline=pipeline_audit.audit_pipeline,
        model_id=body.model_id,
        dataset_id=body.dataset_id,
    ))
    session.commit()

    # Return updated pipeline view by re-using the GET logic
    return get_audit_pipeline(audit_id=audit_id, session=session, current_user=current_user)


@router.delete("/{audit_id}/pipeline/model-dataset/{mapping_id}", response_model=PipelineOverviewResponse)
def remove_pipeline_model_dataset(
    audit_id: int,
    mapping_id: int,
    session: SessionDep,
    current_user: User = Depends(get_current_user),
    audit_access=Depends(get_audit_instigator_access),
):
    """Remove a model-dataset pair from this audit's pipeline by mapping_id.

    Only the audit_instigator can call this.  Returns the full updated
    pipeline overview so the frontend can refresh in one round-trip.
    """
    row = session.get(MappingModelDatasetAudit, mapping_id)
    if not row:
        raise HTTPException(status_code=404, detail="Pipeline mapping not found")

    # Confirm this mapping belongs to this audit's pipeline
    pipeline_audit = session.exec(
        select(MappingAuditPipelineAudit).where(
            MappingAuditPipelineAudit.audit_id == audit_id
        )
    ).first()
    if not pipeline_audit or row.auditpipeline != pipeline_audit.audit_pipeline:
        raise HTTPException(status_code=403, detail="This mapping does not belong to this audit's pipeline")

    session.delete(row)
    session.commit()

    return get_audit_pipeline(audit_id=audit_id, session=session, current_user=current_user)


# ---------------------------------------------------------------------------
# Invite auditor by email
# ---------------------------------------------------------------------------

@router.post("/{audit_id}/invite")
def invite_auditor(
    audit_id: int,
    body: AuditInviteRequest,
    session: SessionDep,
    current_user: User = Depends(get_current_user),
    audit_access=Depends(get_audit_instigator_access),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """Invite a user to participate in this audit as an auditor.

    The audit_instigator provides the invitee's email address — no UUID needed.
    On success an invitation email is sent and the user is linked to the audit
    with the 'auditor' role. A new user account is created if the email is not
    yet registered.
    """
    try:
        result = audit_setup_service.invite_user_to_audit(
            session=session,
            audit_id=audit_id,
            email=body.email,
            inviter_name=current_user.full_name,
            tenant_id=tenant_id,
        )
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to invite user: {str(e)}")

# Application endpoints

@router.post("/applications/")
def create_application(
    app_data: ApplicationCreate,
    session: SessionDep,
    current_user: TenantAdmin,
):
    """Create a new application. Tenant admin only."""
    try:
        db_entity = application_service.create_application_from_schema(
            app_data=app_data,
            session=session
        )
        return db_entity
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=400, detail=f"Error creating application: {str(e)}")


@router.put("/applications/{application_id}")
def update_application(
    application_id: int,
    application_update: ApplicationUpdate,
    session: SessionDep,
    current_user: TenantAdmin,
):
    """Update an existing application. Tenant admin only."""
    try:
        db_application = application_service.update_application_comprehensive(
            application_id=application_id,
            application_update=application_update,
            session=session
        )
        return db_application
    except HTTPException:
        session.rollback()
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=400, detail=f"Error updating application: {str(e)}")


@router.delete("/applications/{application_id}")
def delete_application(
    application_id: int,
    session: SessionDep,
    current_user: TenantAdmin,
):
    """Delete an application. Tenant admin only. Fails if audits are still linked."""
    try:
        result = application_service.delete_application(
            application_id=application_id,
            session=session
        )
        return result
    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=400, detail=f"Error deleting application: {str(e)}")
