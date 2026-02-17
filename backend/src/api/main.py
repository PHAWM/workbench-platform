from fastapi import APIRouter

from src.api.routes import ( 
    login, 
    users,
    ml_pipeline,
    entities,
    events,
    metrics,
    application,
    evaluation,
    upload
)

api_router = APIRouter()
api_router.include_router(login.router)
api_router.include_router(users.router)
api_router.include_router(entities.router)
api_router.include_router(events.router)
api_router.include_router(metrics.router)
api_router.include_router(application.router)
api_router.include_router(evaluation.router)
api_router.include_router(upload.router)
