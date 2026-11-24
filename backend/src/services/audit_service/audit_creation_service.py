"""Audit creation service module for creating audits with full setup"""
import shutil
from pathlib import Path
from typing import Dict, Any
from fastapi import HTTPException
from sqlmodel import Session, select

from src.models import *


def create_audit_comprehensive(
    audit_data: 'AuditCompleteCreate',
    current_user_id: str,
    session: Session
) -> Dict[str, Any]:
    """
    Create audit with model associations and pipeline setup in one call.

    The creating user is automatically assigned as audit_instigator.
    A pipeline is always created for the audit.

    Creates:
    - Audit record
    - MappingAuditUser with audit_instigator role
    - MappingAuditOutcomeUser (initial outcome)
    - AuditPipeline + MappingAuditPipelineAudit
    - MappingAuditModel (for each model_id)
    - MappingAuditApplication
    - MappingModelDatasetAudit (if model has dataset)
    """
    try:
        # Verify application exists
        application = session.get(Application, audit_data.application_id)
        if not application:
            raise HTTPException(status_code=400, detail="Application not found")

        # Get audit_instigator role
        instigator_role = session.exec(
            select(AuditRoles).where(AuditRoles.role == "audit_instigator")
        ).first()
        if not instigator_role:
            raise HTTPException(status_code=500, detail="audit_instigator role not found. Run migrations first.")

        # Create audit
        audit = Audit(
            name=audit_data.name,
            description=audit_data.description,
        )
        session.add(audit)
        session.flush()

        # Create audit user association with audit_instigator role
        audit_user = MappingAuditUser(
            audit_id=audit.id,
            user_id=current_user_id,
            roles_id=instigator_role.id
        )
        session.add(audit_user)
        session.flush()

        # Create initial audit outcome for user
        audit_outcome = MappingAuditOutcomeUser(
            user_audit_id=audit_user.id,
            audit_id=audit.id,
            status=0,
            recommendation=0,
            notes=None
        )
        session.add(audit_outcome)
        session.flush()

        # Always create audit pipeline
        pipeline = AuditPipeline()
        session.add(pipeline)
        session.flush()

        pipeline_audit = MappingAuditPipelineAudit(
            audit_pipeline=pipeline.id,
            audit_id=audit.id
        )
        session.add(pipeline_audit)
        session.flush()

        # Associate models if provided
        model_associations = []
        if audit_data.model_ids:
            for model_id in audit_data.model_ids:
                model = session.get(Modelmetadata, model_id)
                if not model:
                    continue

                mapping = MappingAuditModel(
                    model_id=model_id,
                    audit_id=audit.id
                )
                session.add(mapping)
                model_associations.append(mapping)

                # If model has datasets, create MappingModelDatasetAudit
                if audit_data.dataset_ids:
                    for dataset_id in audit_data.dataset_ids:
                        dataset = session.get(DatasetMetadata, dataset_id)
                        if dataset:
                            mda = MappingModelDatasetAudit(
                                auditpipeline=pipeline.id,
                                model_id=model_id,
                                dataset_id=dataset_id
                            )
                            session.add(mda)

            session.flush()

        # Create application-audit mapping
        app_audit_mapping = MappingAuditApplication(
            audit_id=audit.id,
            application_id=audit_data.application_id
        )
        session.add(app_audit_mapping)

        session.commit()

        return {
            "id": audit.id,
            "name": audit.name,
            "description": audit.description,
            "status": audit_outcome.status,
            "recommendation_text": None,
            "application_id": audit_data.application_id,
            "application_name": application.name,
            "pipeline_created": pipeline.id,
            "models_associated": len(model_associations),
            "model_association_ids": [ma.id for ma in model_associations],
            "message": "Audit created successfully"
        }

    except HTTPException:
        session.rollback()
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=400, detail=f"Error creating complete audit: {str(e)}")


def delete_audit_comprehensive(
    audit_id: int,
    session: Session
) -> Dict[str, Any]:
    """
    Delete an audit and all associated data (cascade).

    Deletes in order:
    - MappingAuditPipelineEvents (pipeline event mappings)
    - MappingModelDatasetAudit (model-dataset-pipeline)
    - MappingAuditPipelineAudit (pipeline-audit link)
    - AuditPipeline records
    - MappingEventsAuditStatus (event audit statuses)
    - MappingAuditOutcomeUser (outcomes)
    - MappingUserEvents (user-event for this audit's users)
    - MappingUserMetrics (user-metrics for this audit's users)
    - MappingEventsEntities (event-entity for this audit)
    - MappingAuditModel (audit-model)
    - MappingAuditApplication (audit-app)
    - MappingAuditUser (user-audit)
    - Audit record
    """
    audit = session.get(Audit, audit_id)
    if not audit:
        raise HTTPException(status_code=404, detail="Audit not found")

    audit_name = audit.name

    try:
        # Get all user_audit_ids for this audit
        user_audits = session.exec(
            select(MappingAuditUser).where(MappingAuditUser.audit_id == audit_id)
        ).all()
        user_audit_ids = [ua.id for ua in user_audits]

        # Get pipeline IDs for this audit
        pipeline_audits = session.exec(
            select(MappingAuditPipelineAudit).where(
                MappingAuditPipelineAudit.audit_id == audit_id
            )
        ).all()
        pipeline_ids = [pa.audit_pipeline for pa in pipeline_audits]

        # Delete MappingAuditPipelineEvents
        for pid in pipeline_ids:
            events = session.exec(
                select(MappingAuditPipelineEvents).where(
                    MappingAuditPipelineEvents.audit_pipeline == pid
                )
            ).all()
            for e in events:
                session.delete(e)

        # Delete MappingModelDatasetAudit
        for pid in pipeline_ids:
            mdas = session.exec(
                select(MappingModelDatasetAudit).where(
                    MappingModelDatasetAudit.auditpipeline == pid
                )
            ).all()
            for mda in mdas:
                session.delete(mda)

        # Delete MappingAuditPipelineAudit
        for pa in pipeline_audits:
            session.delete(pa)

        # Delete AuditPipeline records
        for pid in pipeline_ids:
            pipeline = session.get(AuditPipeline, pid)
            if pipeline:
                session.delete(pipeline)

        # Delete MappingEventsAuditStatus
        statuses = session.exec(
            select(MappingEventsAuditStatus).where(
                MappingEventsAuditStatus.audit_id == audit_id
            )
        ).all()
        for s in statuses:
            session.delete(s)

        # Delete MappingAuditOutcomeUser
        outcomes = session.exec(
            select(MappingAuditOutcomeUser).where(
                MappingAuditOutcomeUser.audit_id == audit_id
            )
        ).all()
        for o in outcomes:
            session.delete(o)

        # Delete MappingUserEvents for this audit's users
        for ua_id in user_audit_ids:
            user_events = session.exec(
                select(MappingUserEvents).where(
                    MappingUserEvents.user_audit_id == ua_id
                )
            ).all()
            for ue in user_events:
                session.delete(ue)

        # Delete MappingUserMetrics for this audit's users
        for ua_id in user_audit_ids:
            user_metrics = session.exec(
                select(MappingUserMetrics).where(
                    MappingUserMetrics.user_audit_id == ua_id
                )
            ).all()
            for um in user_metrics:
                session.delete(um)

        # Delete MappingUserAuditFeatures (user-specific underlying features)
        for ua_id in user_audit_ids:
            user_features = session.exec(
                select(MappingUserAuditFeatures).where(
                    MappingUserAuditFeatures.user_audit_id == ua_id
                )
            ).all()
            for uf in user_features:
                session.delete(uf)

        # Delete MappingUserAuditTargetFeatures (user-specific target features)
        for ua_id in user_audit_ids:
            user_targets = session.exec(
                select(MappingUserAuditTargetFeatures).where(
                    MappingUserAuditTargetFeatures.user_audit_id == ua_id
                )
            ).all()
            for ut in user_targets:
                session.delete(ut)

        # Delete MappingUserEntities (user-specific entities)
        for ua_id in user_audit_ids:
            user_entities = session.exec(
                select(MappingUserEntities).where(
                    MappingUserEntities.user_audit_id == ua_id
                )
            ).all()
            for ue in user_entities:
                session.delete(ue)

        # Delete MappingEventsEntities for this audit
        entities = session.exec(
            select(MappingEventsEntities).where(
                MappingEventsEntities.audit_id == audit_id
            )
        ).all()
        for ent in entities:
            session.delete(ent)

        # Delete MappingAuditModel
        audit_models = session.exec(
            select(MappingAuditModel).where(
                MappingAuditModel.audit_id == audit_id
            )
        ).all()
        for am in audit_models:
            session.delete(am)

        # Delete MappingAuditApplication
        audit_apps = session.exec(
            select(MappingAuditApplication).where(
                MappingAuditApplication.audit_id == audit_id
            )
        ).all()
        for aa in audit_apps:
            session.delete(aa)

        # Delete MappingAuditUser
        for ua in user_audits:
            session.delete(ua)

        # Delete the Audit itself
        session.delete(audit)
        session.commit()

        # Clean up audit storage directory
        audit_dir = Path("storage/audits") / f"audit_{audit_id}"
        if audit_dir.exists():
            shutil.rmtree(audit_dir, ignore_errors=True)

        return {
            "message": f"Audit '{audit_name}' and all associated data deleted successfully",
            "audit_id": audit_id
        }

    except HTTPException:
        session.rollback()
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=400, detail=f"Error deleting audit: {str(e)}")


def update_audit_comprehensive(
    audit_id: int,
    audit_update: 'AuditUpdate',
    session: Session
) -> Dict[str, Any]:
    """Update audit name and/or description."""
    audit = session.get(Audit, audit_id)
    if not audit:
        raise HTTPException(status_code=404, detail="Audit not found")

    update_data = audit_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(audit, field, value)

    session.add(audit)
    session.commit()
    session.refresh(audit)

    return {
        "id": audit.id,
        "name": audit.name,
        "description": audit.description,
        "message": "Audit updated successfully"
    }
