from fastapi import APIRouter

from src.api.routes import (
    login,
    users,
    ml_pipeline,
    mappings,
    entities,
    events,
    metrics,
    application,
    evaluation,
    upload,
    dataset,
    tenants,
    admin_features,
    demo,
)

api_router = APIRouter()
api_router.include_router(login.router)
api_router.include_router(users.router)
api_router.include_router(ml_pipeline.router)
api_router.include_router(entities.router)
api_router.include_router(events.router)
api_router.include_router(metrics.router)
api_router.include_router(mappings.router)
api_router.include_router(application.router)
api_router.include_router(evaluation.router)
api_router.include_router(upload.router)
api_router.include_router(dataset.router)
api_router.include_router(tenants.router)
api_router.include_router(admin_features.router)
api_router.include_router(demo.router)
