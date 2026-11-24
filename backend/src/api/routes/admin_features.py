"""Admin/instigator endpoints for managing tenant-wide feature catalogues.

Two catalogues live in this module:

* `targetfeatures`     — labels/metrics a model produces.
* `underlyingfeatures` — input columns/attributes used by metrics.

Both are tenant-wide reference tables that, before these endpoints existed,
could only be created as a side effect of audit/dataset flows. The admin
panel needs direct CRUD on each catalogue, which is what this module
provides. The per-audit endpoints in events.py still create rows in these
tables on the fly when an instigator/auditor adds a feature mid-audit —
that's expected; both flows share the same catalogue.
"""
from typing import Annotated, Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel
from sqlmodel import select

from src.api.deps import (
    SessionDep,
    get_audit_instigator_access,
    get_current_instigator_or_superuser,
)
from src.models import (
    Audit,
    AuditRoles,
    Entities,
    Events,
    EventsCategory,
    MappingAuditEntities,
    MappingAuditOutcomeUser,
    MappingAuditUser,
    MappingDatasetFeatures,
    MappingEventsAuditStatus,
    MappingEventsCategory,
    MappingEventsEntities,
    MappingTaxonomyCategory,
    MappingMetricsEvents,
    MappingUserEvents,
    MappingUserMetrics,
    MappingModelTargetFeatures,
    MappingOutcomeEvaluationValues,
    MappingUserAuditFeatures,
    MappingUserAuditTargetFeatures,
    Metrics,
    MetricsTargetFeatures,
    MetricsValues,
    MetricsUnderlyingFeatures,
    QualitativeMetrics,
    QuantitativeMetrics,
    TargetFeatures,
    TaxonomyGroups,
    UnderlyingFeatures,
    User,
    UserEventCustomisations,
    UserMetricThresholds,
)

InstigatorOrAdmin = Annotated[User, Depends(get_current_instigator_or_superuser)]


router = APIRouter(prefix="/admin", tags=["Admin — Feature Catalogues"])


# ---------------------------------------------------------------------------
# Target features
# ---------------------------------------------------------------------------

def _resolve_function_name(target_feature: str) -> str | None:
    """Resolve function_name from METRICS_REGISTRY, mirroring the per-audit flow."""
    from src.services.performance_service.functions import METRICS_REGISTRY
    key = target_feature.lower().replace(" ", "_")
    if key in METRICS_REGISTRY:
        return METRICS_REGISTRY[key].__name__
    return None


@router.get("/target-features/", response_model=List[TargetFeatures])
def list_target_features(session: SessionDep, current_user: InstigatorOrAdmin):
    """List every target feature in the tenant catalogue."""
    return session.exec(select(TargetFeatures).order_by(TargetFeatures.id)).all()


@router.post("/target-features/", response_model=TargetFeatures, status_code=201)
def create_target_feature(
    payload: dict,
    session: SessionDep,
    current_user: InstigatorOrAdmin,
):
    """Create a new target feature in the tenant catalogue.

    Body: {"target_feature": "<name>", "function_name": "<optional>"}
    If function_name is omitted, it is resolved from METRICS_REGISTRY.
    """
    name = (payload.get("target_feature") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="target_feature is required")

    existing = session.exec(
        select(TargetFeatures).where(TargetFeatures.target_feature == name)
    ).first()
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"Target feature '{name}' already exists (id={existing.id})",
        )

    function_name = payload.get("function_name") or _resolve_function_name(name)
    feature = TargetFeatures(target_feature=name, function_name=function_name)
    session.add(feature)
    session.commit()
    session.refresh(feature)
    return feature


@router.patch("/target-features/{target_feature_id}", response_model=TargetFeatures)
def update_target_feature(
    target_feature_id: int,
    payload: dict,
    session: SessionDep,
    current_user: InstigatorOrAdmin,
):
    """Rename a target feature or update its function_name."""
    feature = session.get(TargetFeatures, target_feature_id)
    if not feature:
        raise HTTPException(status_code=404, detail="Target feature not found")

    if "target_feature" in payload:
        new_name = (payload.get("target_feature") or "").strip()
        if not new_name:
            raise HTTPException(status_code=400, detail="target_feature cannot be empty")
        if new_name != feature.target_feature:
            clash = session.exec(
                select(TargetFeatures).where(TargetFeatures.target_feature == new_name)
            ).first()
            if clash:
                raise HTTPException(
                    status_code=409,
                    detail=f"Target feature '{new_name}' already exists (id={clash.id})",
                )
            feature.target_feature = new_name

    if "function_name" in payload:
        feature.function_name = payload.get("function_name")

    session.add(feature)
    session.commit()
    session.refresh(feature)
    return feature


@router.delete("/target-features/{target_feature_id}")
def delete_target_feature(
    target_feature_id: int,
    session: SessionDep,
    current_user: InstigatorOrAdmin,
):
    """Delete a target feature from the catalogue.

    Refuses if any mapping table still references it — callers must unlink
    first, otherwise we'd cascade-delete audit data the user didn't ask to lose.
    """
    feature = session.get(TargetFeatures, target_feature_id)
    if not feature:
        raise HTTPException(status_code=404, detail="Target feature not found")

    refs = {
        "model_mappings": session.exec(
            select(MappingModelTargetFeatures).where(
                MappingModelTargetFeatures.target_feature_id == target_feature_id
            )
        ).first(),
        "user_audit_mappings": session.exec(
            select(MappingUserAuditTargetFeatures).where(
                MappingUserAuditTargetFeatures.target_feature_id == target_feature_id
            )
        ).first(),
        "metric_mappings": session.exec(
            select(MetricsTargetFeatures).where(
                MetricsTargetFeatures.target_feature_id == target_feature_id
            )
        ).first(),
    }
    blockers = [k for k, v in refs.items() if v is not None]
    if blockers:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Target feature is still referenced by: {', '.join(blockers)}. "
                f"Unlink it from all audits/datasets/metrics before deleting."
            ),
        )

    session.delete(feature)
    session.commit()
    return {"deleted_id": target_feature_id}


# ---------------------------------------------------------------------------
# Underlying features
# ---------------------------------------------------------------------------


@router.get("/underlying-features/", response_model=List[UnderlyingFeatures])
def list_underlying_features(session: SessionDep, current_user: InstigatorOrAdmin):
    """List every underlying feature in the tenant catalogue."""
    return session.exec(select(UnderlyingFeatures).order_by(UnderlyingFeatures.id)).all()


@router.post("/underlying-features/", response_model=UnderlyingFeatures, status_code=201)
def create_underlying_feature(
    payload: dict,
    session: SessionDep,
    current_user: InstigatorOrAdmin,
):
    """Create a new underlying feature in the tenant catalogue.

    Body: {"feature_name": "<name>"}
    """
    name = (payload.get("feature_name") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="feature_name is required")

    existing = session.exec(
        select(UnderlyingFeatures).where(UnderlyingFeatures.feature_name == name)
    ).first()
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"Underlying feature '{name}' already exists (id={existing.id})",
        )

    feature = UnderlyingFeatures(feature_name=name)
    session.add(feature)
    session.commit()
    session.refresh(feature)
    return feature


@router.patch("/underlying-features/{feature_id}", response_model=UnderlyingFeatures)
def update_underlying_feature(
    feature_id: int,
    payload: dict,
    session: SessionDep,
    current_user: InstigatorOrAdmin,
):
    """Rename an underlying feature."""
    feature = session.get(UnderlyingFeatures, feature_id)
    if not feature:
        raise HTTPException(status_code=404, detail="Underlying feature not found")

    if "feature_name" in payload:
        new_name = (payload.get("feature_name") or "").strip()
        if not new_name:
            raise HTTPException(status_code=400, detail="feature_name cannot be empty")
        if new_name != feature.feature_name:
            clash = session.exec(
                select(UnderlyingFeatures).where(UnderlyingFeatures.feature_name == new_name)
            ).first()
            if clash:
                raise HTTPException(
                    status_code=409,
                    detail=f"Underlying feature '{new_name}' already exists (id={clash.id})",
                )
            feature.feature_name = new_name

    session.add(feature)
    session.commit()
    session.refresh(feature)
    return feature


@router.delete("/underlying-features/{feature_id}")
def delete_underlying_feature(
    feature_id: int,
    session: SessionDep,
    current_user: InstigatorOrAdmin,
):
    """Delete an underlying feature from the catalogue.

    Refuses if any mapping table still references it — same reasoning as the
    target-features delete: a CASCADE here would silently drop audit data.
    """
    feature = session.get(UnderlyingFeatures, feature_id)
    if not feature:
        raise HTTPException(status_code=404, detail="Underlying feature not found")

    refs = {
        "dataset_mappings": session.exec(
            select(MappingDatasetFeatures).where(
                MappingDatasetFeatures.underlying_feature_id == feature_id
            )
        ).first(),
        "user_audit_mappings": session.exec(
            select(MappingUserAuditFeatures).where(
                MappingUserAuditFeatures.underlying_feature_id == feature_id
            )
        ).first(),
        "metric_mappings": session.exec(
            select(MetricsUnderlyingFeatures).where(
                MetricsUnderlyingFeatures.feature_id == feature_id
            )
        ).first(),
    }
    blockers = [k for k, v in refs.items() if v is not None]
    if blockers:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Underlying feature is still referenced by: {', '.join(blockers)}. "
                f"Unlink it from all audits/datasets/metrics before deleting."
            ),
        )

    session.delete(feature)
    session.commit()
    return {"deleted_id": feature_id}


# ---------------------------------------------------------------------------
# Event categories
# ---------------------------------------------------------------------------
#
# EventsCategory rows are created as a side effect of the per-audit category
# flow (events.py `/categories`), but there was no way to edit one afterwards.
# The admin panel needs to rename/redescribe categories directly. Partial
# update: only the fields present in the body are changed.


class EventCategoryCreate(BaseModel):
    event_name: str
    description: str = ""


class EventCategoryUpdate(BaseModel):
    event_name: Optional[str] = None
    description: Optional[str] = None


@router.get("/event-categories/", response_model=List[EventsCategory])
def list_event_categories(session: SessionDep, current_user: InstigatorOrAdmin):
    """List every event category in the tenant catalogue."""
    return session.exec(select(EventsCategory).order_by(EventsCategory.id)).all()


@router.post("/event-categories/", response_model=EventsCategory, status_code=201)
def create_event_category(
    payload: EventCategoryCreate,
    session: SessionDep,
    current_user: InstigatorOrAdmin,
):
    """Create a new event category in the tenant catalogue.

    Refuses with 409 if a category with the same name already exists — the
    per-audit flow (`/events/categories`) and this admin flow share one
    catalogue, so a name collision would be ambiguous.
    """
    name = payload.event_name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="event_name is required")

    existing = session.exec(
        select(EventsCategory).where(EventsCategory.event_name == name)
    ).first()
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"Event category '{name}' already exists (id={existing.id})",
        )

    category = EventsCategory(event_name=name, description=payload.description or "")
    session.add(category)
    session.commit()
    session.refresh(category)
    return category


@router.patch("/event-categories/{category_id}", response_model=EventsCategory)
def update_event_category(
    category_id: int,
    payload: EventCategoryUpdate,
    session: SessionDep,
    current_user: InstigatorOrAdmin,
):
    """Rename an event category or update its description (partial update)."""
    category = session.get(EventsCategory, category_id)
    if not category:
        raise HTTPException(status_code=404, detail="Event category not found")

    if payload.event_name is not None:
        new_name = payload.event_name.strip()
        if not new_name:
            raise HTTPException(status_code=400, detail="event_name cannot be empty")
        category.event_name = new_name

    if payload.description is not None:
        category.description = payload.description

    session.add(category)
    session.commit()
    session.refresh(category)
    return category


# ---------------------------------------------------------------------------
# Taxonomy groups
# ---------------------------------------------------------------------------
#
# Taxonomy groups classify event categories (mappingtaxonomycategory). They
# had no CRUD surface at all — the admin panel needs at least to list and edit
# them so the instigator can maintain the taxonomy the audit reports against.


class TaxonomyGroupCreate(BaseModel):
    event_name: str
    description: str = ""
    reason: Optional[str] = None


class TaxonomyGroupUpdate(BaseModel):
    event_name: Optional[str] = None
    description: Optional[str] = None
    reason: Optional[str] = None


@router.get("/taxonomy-groups/", response_model=List[TaxonomyGroups])
def list_taxonomy_groups(session: SessionDep, current_user: InstigatorOrAdmin):
    """List every taxonomy group in the tenant catalogue."""
    return session.exec(select(TaxonomyGroups).order_by(TaxonomyGroups.id)).all()


@router.post("/taxonomy-groups/", response_model=TaxonomyGroups, status_code=201)
def create_taxonomy_group(
    payload: TaxonomyGroupCreate,
    session: SessionDep,
    current_user: InstigatorOrAdmin,
):
    """Create a new taxonomy group in the tenant catalogue.

    Refuses with 409 if a group with the same name already exists.
    """
    name = payload.event_name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="event_name is required")

    existing = session.exec(
        select(TaxonomyGroups).where(TaxonomyGroups.event_name == name)
    ).first()
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"Taxonomy group '{name}' already exists (id={existing.id})",
        )

    group = TaxonomyGroups(
        event_name=name,
        description=payload.description or "",
        reason=payload.reason,
    )
    session.add(group)
    session.commit()
    session.refresh(group)
    return group


@router.patch("/taxonomy-groups/{taxonomy_id}", response_model=TaxonomyGroups)
def update_taxonomy_group(
    taxonomy_id: int,
    payload: TaxonomyGroupUpdate,
    session: SessionDep,
    current_user: InstigatorOrAdmin,
):
    """Rename a taxonomy group or update its description/reason (partial update)."""
    group = session.get(TaxonomyGroups, taxonomy_id)
    if not group:
        raise HTTPException(status_code=404, detail="Taxonomy group not found")

    if payload.event_name is not None:
        new_name = payload.event_name.strip()
        if not new_name:
            raise HTTPException(status_code=400, detail="event_name cannot be empty")
        group.event_name = new_name

    if payload.description is not None:
        group.description = payload.description

    if payload.reason is not None:
        group.reason = payload.reason

    session.add(group)
    session.commit()
    session.refresh(group)
    return group


# ---------------------------------------------------------------------------
# Instigator edit of audit setup (events / metrics / entities)
# ---------------------------------------------------------------------------
#
# There are two edit paths for setup entities, and they must not be conflated:
#
#   * Auditor path (already exists in events.py / metrics.py): an auditor edits
#     the event/metric THEY created, authorised by ownership through
#     MappingUserEvents / MappingUserMetrics. Left untouched.
#
#   * Instigator path (below): the audit instigator, from the admin panel,
#     edits ANY event/metric/entity used in their audit regardless of who
#     created it. Authorised by get_audit_instigator_access on the audit_id in
#     the path.
#
# Events, Metrics and Entities are tenant-wide rows linked to an audit through
# mapping tables — they carry no audit_id of their own. So each endpoint:
#   1. verifies the row is actually linked to the given audit (else 404), and
#   2. edits the shared row in place, returning the bare updated entity (so the
#      body matches the auditor-facing PUT /events, /metrics edits) plus an
#      `X-Also-Used-By-Audits` response header — a comma-separated list of the
#      other audits that reference the same row — so the panel can warn the
#      instigator that the edit is not isolated to this audit.


def _also_used_header(response: Response, referencing: set[int], audit_id: int) -> None:
    """Set X-Also-Used-By-Audits to the other audits sharing this row (if any)."""
    others = sorted(referencing - {audit_id})
    if others:
        response.headers["X-Also-Used-By-Audits"] = ",".join(str(a) for a in others)


def _audits_referencing_event(session, event_id: int) -> set[int]:
    """All audit_ids that reference this event, via any of its mapping tables."""
    ids: set[int] = set()
    # MappingEventsAuditStatus carries audit_id directly.
    ids.update(
        session.exec(
            select(MappingEventsAuditStatus.audit_id).where(
                MappingEventsAuditStatus.event_id == event_id,
                MappingEventsAuditStatus.audit_id.is_not(None),
            )
        ).all()
    )
    # MappingEventsEntities carries audit_id directly.
    ids.update(
        session.exec(
            select(MappingEventsEntities.audit_id).where(
                MappingEventsEntities.event_id == event_id,
                MappingEventsEntities.audit_id.is_not(None),
            )
        ).all()
    )
    # MappingUserEvents links via the auditor row → audit_id.
    ids.update(
        session.exec(
            select(MappingAuditUser.audit_id)
            .join(
                MappingUserEvents,
                MappingUserEvents.user_audit_id == MappingAuditUser.id,
            )
            .where(MappingUserEvents.event_id == event_id)
        ).all()
    )
    ids.discard(None)
    return ids


def _audits_referencing_metric(session, metric_id: int) -> set[int]:
    """All audit_ids that reference this metric, via any of its mapping tables."""
    ids: set[int] = set()
    ids.update(
        session.exec(
            select(MappingEventsAuditStatus.audit_id).where(
                MappingEventsAuditStatus.metric_id == metric_id,
                MappingEventsAuditStatus.audit_id.is_not(None),
            )
        ).all()
    )
    ids.update(
        session.exec(
            select(MappingAuditUser.audit_id)
            .join(
                MappingMetricsEvents,
                MappingMetricsEvents.user_audit_id == MappingAuditUser.id,
            )
            .where(MappingMetricsEvents.metric_id == metric_id)
        ).all()
    )
    ids.update(
        session.exec(
            select(MappingAuditUser.audit_id)
            .join(
                MappingUserMetrics,
                MappingUserMetrics.user_audit_id == MappingAuditUser.id,
            )
            .where(MappingUserMetrics.metric_id == metric_id)
        ).all()
    )
    ids.discard(None)
    return ids


def _audits_referencing_entity(session, entity_id: int) -> set[int]:
    """All audit_ids that reference this entity, via any of its mapping tables."""
    ids: set[int] = set()
    ids.update(
        session.exec(
            select(MappingAuditEntities.audit_id).where(
                MappingAuditEntities.entity_id == entity_id
            )
        ).all()
    )
    ids.update(
        session.exec(
            select(MappingEventsEntities.audit_id).where(
                MappingEventsEntities.entity_id == entity_id,
                MappingEventsEntities.audit_id.is_not(None),
            )
        ).all()
    )
    ids.discard(None)
    return ids


class AdminEventUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    cause: Optional[str] = None
    reason: Optional[str] = None
    likelihood: Optional[float] = None
    magnitude: Optional[float] = None
    valence: Optional[float] = None


class AdminMetricUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    reason: Optional[str] = None
    # Metric-type detail, edited on the QuantitativeMetrics/QualitativeMetrics
    # row when present. Pass only the one that applies to this metric.
    formula: Optional[str] = None
    definition: Optional[str] = None


class AdminEntityUpdate(BaseModel):
    name: Optional[str] = None
    num_individuals: Optional[int] = None


@router.patch("/audits/{audit_id}/events/{event_id}", response_model=Events)
def instigator_update_event(
    audit_id: int,
    event_id: int,
    payload: AdminEventUpdate,
    session: SessionDep,
    response: Response,
    audit_access=Depends(get_audit_instigator_access),
):
    """Instigator edit of an event used in this audit (partial update).

    Verifies the event is linked to `audit_id`, then edits the shared Events
    row. Returns the bare updated event; other audits sharing the row are
    reported in the `X-Also-Used-By-Audits` response header.
    """
    referencing = _audits_referencing_event(session, event_id)
    if audit_id not in referencing:
        raise HTTPException(
            status_code=404,
            detail=f"Event {event_id} is not part of audit {audit_id}",
        )

    event = session.get(Events, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    data = payload.model_dump(exclude_unset=True)
    if "name" in data:
        name = (data["name"] or "").strip()
        if not name:
            raise HTTPException(status_code=400, detail="name cannot be empty")
        data["name"] = name
    if "likelihood" in data and data["likelihood"] is not None and not (
        0.0 <= data["likelihood"] <= 1.0
    ):
        raise HTTPException(status_code=400, detail="likelihood must be between 0 and 1")
    if "valence" in data and data["valence"] is not None and not (
        -1.0 <= data["valence"] <= 1.0
    ):
        raise HTTPException(status_code=400, detail="valence must be between -1 and 1")

    for field, value in data.items():
        setattr(event, field, value)

    session.add(event)
    session.commit()
    session.refresh(event)

    _also_used_header(response, referencing, audit_id)
    return event


@router.patch("/audits/{audit_id}/metrics/{metric_id}", response_model=Metrics)
def instigator_update_metric(
    audit_id: int,
    metric_id: int,
    payload: AdminMetricUpdate,
    session: SessionDep,
    response: Response,
    audit_access=Depends(get_audit_instigator_access),
):
    """Instigator edit of a metric used in this audit (partial update).

    Verifies the metric is linked to `audit_id`, edits the shared Metrics row,
    and — if formula/definition is supplied — the matching QuantitativeMetrics/
    QualitativeMetrics row. Returns the bare updated metric; other audits
    sharing the row are reported in the `X-Also-Used-By-Audits` header.
    """
    referencing = _audits_referencing_metric(session, metric_id)
    if audit_id not in referencing:
        raise HTTPException(
            status_code=404,
            detail=f"Metric {metric_id} is not part of audit {audit_id}",
        )

    metric = session.get(Metrics, metric_id)
    if not metric:
        raise HTTPException(status_code=404, detail="Metric not found")

    data = payload.model_dump(exclude_unset=True)

    if "name" in data:
        name = (data["name"] or "").strip()
        if not name:
            raise HTTPException(status_code=400, detail="name cannot be empty")
        metric.name = name
    if "description" in data:
        metric.description = data["description"]
    if "reason" in data:
        metric.reason = data["reason"]
    session.add(metric)

    if "formula" in data:
        quant = session.exec(
            select(QuantitativeMetrics).where(
                QuantitativeMetrics.metric_id == metric_id
            )
        ).first()
        if not quant:
            raise HTTPException(
                status_code=400,
                detail="Metric has no quantitative definition to set a formula on",
            )
        quant.formula = data["formula"]
        session.add(quant)

    if "definition" in data:
        qual = session.exec(
            select(QualitativeMetrics).where(
                QualitativeMetrics.metric_id == metric_id
            )
        ).first()
        if not qual:
            raise HTTPException(
                status_code=400,
                detail="Metric has no qualitative definition to edit",
            )
        qual.definition = data["definition"]
        session.add(qual)

    session.commit()
    session.refresh(metric)

    _also_used_header(response, referencing, audit_id)
    return metric


@router.patch("/audits/{audit_id}/entities/{entity_id}", response_model=Entities)
def instigator_update_entity(
    audit_id: int,
    entity_id: int,
    payload: AdminEntityUpdate,
    session: SessionDep,
    response: Response,
    audit_access=Depends(get_audit_instigator_access),
):
    """Instigator edit of an entity used in this audit (partial update).

    Verifies the entity is linked to `audit_id`, edits the shared Entities row,
    and returns the bare updated entity; other audits sharing the row are
    reported in the `X-Also-Used-By-Audits` header.
    """
    referencing = _audits_referencing_entity(session, entity_id)
    if audit_id not in referencing:
        raise HTTPException(
            status_code=404,
            detail=f"Entity {entity_id} is not part of audit {audit_id}",
        )

    entity = session.get(Entities, entity_id)
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")

    data = payload.model_dump(exclude_unset=True)
    if "name" in data:
        name = (data["name"] or "").strip()
        if not name:
            raise HTTPException(status_code=400, detail="name cannot be empty")
        entity.name = name
    if "num_individuals" in data and data["num_individuals"] is not None:
        if data["num_individuals"] < 0:
            raise HTTPException(
                status_code=400, detail="num_individuals must be non-negative"
            )
        entity.num_individuals = data["num_individuals"]

    session.add(entity)
    session.commit()
    session.refresh(entity)

    _also_used_header(response, referencing, audit_id)
    return entity


# ---------------------------------------------------------------------------
# Reactivate a submitted audit
# ---------------------------------------------------------------------------
#
# When an auditor submits, application.py `/audits/{id}/submit` stamps
# submitted_at and computes duration_seconds on their MappingAuditUser row.
# The instigator sometimes needs to reopen a submitted audit so the auditor
# can revise their answers — e.g. it was submitted early by mistake, or the
# instigator changed an event/metric after submission.
#
# Reactivation is the exact inverse of submit: clear submitted_at and
# duration_seconds while preserving started_at and active_seconds. It never
# touches the auditor's recorded verdicts, results, or customisations — it
# only reopens the window in which they can edit them.


class ReactivateResult(BaseModel):
    audit_id: int
    reactivated_user_audit_ids: List[int]
    count: int


@router.post("/audits/{audit_id}/reactivate", response_model=ReactivateResult)
def reactivate_submitted_audit(
    audit_id: int,
    session: SessionDep,
    user_audit_id: Optional[int] = None,
    audit_access=Depends(get_audit_instigator_access),
):
    """Reopen a submitted audit so its auditors can edit their answers again.

    Clears submitted_at/duration_seconds on the matching MappingAuditUser
    rows; started_at and active_seconds are preserved, and no verdict, metric
    result, outcome, or customisation is modified.

    By default every submitted auditor on the audit is reactivated. Pass
    `?user_audit_id=<id>` to reopen a single auditor's submission. Only the
    audit instigator (or a tenant admin) may do this — enforced by
    get_audit_instigator_access.

    Idempotent: rows that were never submitted are left untouched and not
    counted.
    """
    stmt = select(MappingAuditUser).where(
        MappingAuditUser.audit_id == audit_id,
        MappingAuditUser.submitted_at.is_not(None),
    )
    if user_audit_id is not None:
        stmt = stmt.where(MappingAuditUser.id == user_audit_id)

    rows = session.exec(stmt).all()

    if user_audit_id is not None and not rows:
        # Distinguish "no such auditor row on this audit" from "already open".
        exists = session.exec(
            select(MappingAuditUser).where(
                MappingAuditUser.audit_id == audit_id,
                MappingAuditUser.id == user_audit_id,
            )
        ).first()
        if not exists:
            raise HTTPException(
                status_code=404,
                detail=f"No auditor (user_audit_id={user_audit_id}) on audit {audit_id}",
            )

    reactivated: List[int] = []
    for row in rows:
        row.submitted_at = None
        row.duration_seconds = None
        session.add(row)
        reactivated.append(row.id)

    session.commit()

    return ReactivateResult(
        audit_id=audit_id,
        reactivated_user_audit_ids=reactivated,
        count=len(reactivated),
    )


# ---------------------------------------------------------------------------
# Audit results report
# ---------------------------------------------------------------------------


def _metric_type(formula: str | None, definition: str | None) -> str:
    """Classify a metric from the presence of its quantitative/qualitative row."""
    has_quant = formula is not None
    has_qual = definition is not None
    if has_quant and has_qual:
        return "both"
    if has_quant:
        return "quantitative"
    if has_qual:
        return "qualitative"
    return "unclassified"


def _metric_type_from_ids(metric_id: int, quant_ids: set, qual_ids: set) -> str:
    """Same classification as _metric_type but from pre-fetched id sets."""
    has_quant = metric_id in quant_ids
    has_qual = metric_id in qual_ids
    if has_quant and has_qual:
        return "both"
    if has_quant:
        return "quantitative"
    if has_qual:
        return "qualitative"
    return "unclassified"


def _event_categories_lookup(session) -> dict[int, list[dict]]:
    """Build {event_id: [category, ...]} for the whole tenant.

    An event maps to many categories (mappingeventscategory), and each
    category may belong to a taxonomy group (mappingtaxonomycategory →
    taxonomygroups). Fetched in one pass rather than joined into the main
    per-criterion query, which would fan the result out per category.
    """
    rows = session.exec(
        select(
            MappingEventsCategory.event_id,
            EventsCategory.id,
            EventsCategory.event_name,
            EventsCategory.description,
            TaxonomyGroups.id,
            TaxonomyGroups.event_name,
        )
        .join(EventsCategory, EventsCategory.id == MappingEventsCategory.category_id)
        .join(
            MappingTaxonomyCategory,
            MappingTaxonomyCategory.category_id == EventsCategory.id,
            isouter=True,
        )
        .join(
            TaxonomyGroups,
            TaxonomyGroups.id == MappingTaxonomyCategory.taxonomy_id,
            isouter=True,
        )
        .order_by(MappingEventsCategory.event_id, EventsCategory.id)
    ).all()

    lookup: dict[int, list[dict]] = {}
    for event_id, cat_id, cat_name, cat_desc, tax_id, tax_name in rows:
        lookup.setdefault(event_id, []).append({
            "id": cat_id,
            "name": cat_name,
            "description": cat_desc,
            "taxonomy_group_id": tax_id,
            "taxonomy_group_name": tax_name,
        })
    return lookup


@router.get("/audit-results/{audit_id}")
def audit_results_report(
    session: SessionDep,
    current_user: InstigatorOrAdmin,
    audit_id: int | None = None,
):
    """Structured per-auditor results for one audit (or all audits).

    Returns audits → auditors → audit criteria, where each criterion is one
    (event, metric) the auditor evaluated, with their verdict, comments,
    metric/outcome results, the full event & metric detail (incl. metric
    type), and any per-auditor custom event values / custom threshold. Each
    auditor also carries their overall `audit_recommendation`, and each audit
    lists events/metrics that exist but are `unused` in that audit.

    Pass `?audit_id=1` to scope to a single audit; omit it for every audit.

    Shape:
        [
          {audit_id, audit_name,
           unused: {events: [{id, name, ...}], metrics: [{id, name, ...}]},
           auditors: [
            {user_audit_id, email, full_name, role, submitted_at,
             duration_seconds,
             audit_criteria: [
               {event: {id, name, description, cause, reason,
                        likelihood, magnitude, valence,
                        custom_likelihood, custom_magnitude, custom_valence,
                        is_customised,
                        categories: [{id, name, description,
                                      taxonomy_group_id, taxonomy_group_name}]},
                metric: {id, name, description, reason, metric_type,
                         formula, definition},
                recommendation, status, audit_status_notes,
                metric_result_output,
                metric_threshold, custom_threshold, is_threshold_customised,
                outcome_meet_requirement, outcome_output, outcome_notes}
             ],
             audit_recommendation: {status, recommendation, notes}}
          ]}
        ]
    """
    # One row per (auditor × event × metric). Mirrors the reporting SQL:
    # the verdict table (MappingEventsAuditStatus) is the spine, with the
    # numeric metric value and outcome-evaluation joined on the same
    # (user_audit, event, metric) triple. Event/metric detail, metric-type
    # tables, and per-auditor customisations are joined in alongside.
    stmt = (
        select(
            MappingAuditUser.audit_id,
            Audit.name,
            MappingAuditUser.id,
            User.email,
            User.full_name,
            AuditRoles.role,
            MappingAuditUser.submitted_at,
            MappingAuditUser.duration_seconds,
            # Full event detail.
            Events.id,
            Events.name,
            Events.description,
            Events.cause,
            Events.reason,
            Events.likelihood,
            Events.magnitude,
            Events.valence,
            # Full metric detail + type.
            Metrics.id,
            Metrics.name,
            Metrics.description,
            Metrics.reason,
            QuantitativeMetrics.formula,
            QualitativeMetrics.definition,
            # Verdict + results.
            MappingEventsAuditStatus.recommendation,
            MappingEventsAuditStatus.status,
            MappingEventsAuditStatus.notes,
            MetricsValues.output,
            MetricsValues.threshold,
            MappingOutcomeEvaluationValues.meet_requirement,
            MappingOutcomeEvaluationValues.output,
            MappingOutcomeEvaluationValues.notes,
            # Per-auditor overall outcome.
            MappingAuditOutcomeUser.status,
            MappingAuditOutcomeUser.recommendation,
            MappingAuditOutcomeUser.notes,
            # Per-auditor customisations.
            UserEventCustomisations.custom_likelihood,
            UserEventCustomisations.custom_magnitude,
            UserEventCustomisations.custom_valence,
            UserMetricThresholds.custom_threshold,
        )
        .join(User, User.id == MappingAuditUser.user_id)
        .join(Audit, Audit.id == MappingAuditUser.audit_id)
        .join(AuditRoles, AuditRoles.id == MappingAuditUser.roles_id, isouter=True)
        .join(
            MappingAuditOutcomeUser,
            MappingAuditOutcomeUser.user_audit_id == MappingAuditUser.id,
            isouter=True,
        )
        .join(
            MappingEventsAuditStatus,
            MappingEventsAuditStatus.user_audit_id == MappingAuditUser.id,
            isouter=True,
        )
        .join(Events, Events.id == MappingEventsAuditStatus.event_id, isouter=True)
        .join(Metrics, Metrics.id == MappingEventsAuditStatus.metric_id, isouter=True)
        .join(QuantitativeMetrics, QuantitativeMetrics.metric_id == Metrics.id, isouter=True)
        .join(QualitativeMetrics, QualitativeMetrics.metric_id == Metrics.id, isouter=True)
        .join(
            MappingMetricsEvents,
            (MappingMetricsEvents.user_audit_id == MappingAuditUser.id)
            & (MappingMetricsEvents.event_id == MappingEventsAuditStatus.event_id)
            & (MappingMetricsEvents.metric_id == MappingEventsAuditStatus.metric_id),
            isouter=True,
        )
        .join(MetricsValues, MetricsValues.id == MappingMetricsEvents.values_id, isouter=True)
        .join(
            MappingOutcomeEvaluationValues,
            (MappingOutcomeEvaluationValues.user_audit_id == MappingAuditUser.id)
            & (MappingOutcomeEvaluationValues.event_id == MappingEventsAuditStatus.event_id)
            & (MappingOutcomeEvaluationValues.metric_id == MappingEventsAuditStatus.metric_id),
            isouter=True,
        )
        .join(
            UserEventCustomisations,
            (UserEventCustomisations.user_audit_id == MappingAuditUser.id)
            & (UserEventCustomisations.event_id == MappingEventsAuditStatus.event_id),
            isouter=True,
        )
        .join(
            UserMetricThresholds,
            (UserMetricThresholds.user_audit_id == MappingAuditUser.id)
            & (UserMetricThresholds.event_id == MappingEventsAuditStatus.event_id)
            & (UserMetricThresholds.metric_id == MappingEventsAuditStatus.metric_id),
            isouter=True,
        )
        .order_by(
            MappingAuditUser.audit_id,
            User.email,
            Events.id,
            Metrics.id,
        )
    )
    if audit_id is not None:
        stmt = stmt.where(MappingAuditUser.audit_id == audit_id)

    rows = session.exec(stmt).all()

    # event_id → [category, ...] for attaching to every event in the response.
    categories_by_event = _event_categories_lookup(session)

    # Fold the flat rows into audits → auditors → audit_criteria. Track which
    # event/metric ids actually appear per audit so we can compute "unused".
    audits: dict[int, dict[str, Any]] = {}
    used_events: dict[int, set] = {}
    used_metrics: dict[int, set] = {}
    for (
        aud_id, audit_name, user_audit_id, email, full_name, role,
        submitted_at, duration_seconds,
        event_id, event_name, event_description, event_cause, event_reason,
        event_likelihood, event_magnitude, event_valence,
        metric_id, metric_name, metric_description, metric_reason,
        metric_formula, metric_definition,
        recommendation, status, audit_status_notes,
        metric_output, metric_threshold,
        outcome_meet_requirement, outcome_output, outcome_notes,
        overall_status, overall_recommendation, overall_notes,
        custom_likelihood, custom_magnitude, custom_valence, custom_threshold,
    ) in rows:
        audit = audits.setdefault(aud_id, {
            "audit_id": aud_id,
            "audit_name": audit_name,
            "_auditors": {},
        })
        used_events.setdefault(aud_id, set())
        used_metrics.setdefault(aud_id, set())
        auditor = audit["_auditors"].setdefault(user_audit_id, {
            "user_audit_id": user_audit_id,
            "email": email,
            "full_name": full_name,
            "role": role,
            "submitted_at": submitted_at,
            "duration_seconds": duration_seconds,
            "audit_criteria": [],
            # Overall outcome is one row per auditor; same values repeat across
            # the criterion rows, so capture it once on first sight.
            "audit_recommendation": {
                "status": overall_status,
                "recommendation": overall_recommendation,
                "notes": overall_notes,
            },
        })
        # An auditor with no verdict rows still appears, with empty criteria.
        if event_id is not None or metric_id is not None:
            if event_id is not None:
                used_events[aud_id].add(event_id)
            if metric_id is not None:
                used_metrics[aud_id].add(metric_id)
            is_event_customised = any(
                v is not None
                for v in (custom_likelihood, custom_magnitude, custom_valence)
            )
            auditor["audit_criteria"].append({
                "event": {
                    "id": event_id,
                    "name": event_name,
                    "description": event_description,
                    "cause": event_cause,
                    "reason": event_reason,
                    "likelihood": event_likelihood,
                    "magnitude": event_magnitude,
                    "valence": event_valence,
                    "custom_likelihood": custom_likelihood,
                    "custom_magnitude": custom_magnitude,
                    "custom_valence": custom_valence,
                    "is_customised": is_event_customised,
                    "categories": categories_by_event.get(event_id, []),
                },
                "metric": {
                    "id": metric_id,
                    "name": metric_name,
                    "description": metric_description,
                    "reason": metric_reason,
                    "metric_type": _metric_type(metric_formula, metric_definition),
                    "formula": metric_formula,
                    "definition": metric_definition,
                },
                "recommendation": recommendation,
                "status": status,
                "audit_status_notes": audit_status_notes,
                "metric_result_output": metric_output,
                "metric_threshold": metric_threshold,
                "custom_threshold": custom_threshold,
                "is_threshold_customised": custom_threshold is not None,
                "outcome_meet_requirement": outcome_meet_requirement,
                "outcome_output": outcome_output,
                "outcome_notes": outcome_notes,
            })

    # For each audit, list events/metrics that exist in the tenant but were
    # not used (evaluated) anywhere in that audit.
    all_events = session.exec(select(Events)).all()
    all_metrics = session.exec(select(Metrics)).all()
    # Single-column .exec() returns scalars, not 1-tuples — don't unpack.
    qmetric_ids = set(session.exec(select(QuantitativeMetrics.metric_id)).all())
    dmetric_ids = set(session.exec(select(QualitativeMetrics.metric_id)).all())

    result = []
    for a in audits.values():
        aid = a["audit_id"]
        unused_events = [
            {
                "id": e.id, "name": e.name, "description": e.description,
                "cause": e.cause, "reason": e.reason,
                "likelihood": e.likelihood, "magnitude": e.magnitude,
                "valence": e.valence,
                "categories": categories_by_event.get(e.id, []),
            }
            for e in all_events if e.id not in used_events.get(aid, set())
        ]
        unused_metrics = [
            {
                "id": m.id, "name": m.name, "description": m.description,
                "reason": m.reason,
                "metric_type": _metric_type_from_ids(m.id, qmetric_ids, dmetric_ids),
            }
            for m in all_metrics if m.id not in used_metrics.get(aid, set())
        ]
        result.append({
            "audit_id": aid,
            "audit_name": a["audit_name"],
            "unused": {"events": unused_events, "metrics": unused_metrics},
            "auditors": list(a["_auditors"].values()),
        })
    return result
