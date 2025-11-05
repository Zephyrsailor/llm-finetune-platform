"""Aggregate API router."""

from fastapi import APIRouter

from app.api import (
    auth,
    dashboard,
    datasets,
    workspaces,
    training,
    training_monitor,
    training_snapshots,
    training_experiments,
    evaluation,
    model_registry,
    deployment,
    inference,
    runtime_monitor,
    governance,
    notifications,
    knowledge,
)

api_router = APIRouter()


@api_router.get("/health", tags=["utility"])
async def health_check() -> dict[str, str]:
    """Return basic health information for readiness probes."""
    return {"status": "ok"}


api_router.include_router(auth.router)
api_router.include_router(dashboard.router)
api_router.include_router(datasets.router)
api_router.include_router(workspaces.router)
api_router.include_router(training.router)
api_router.include_router(training_monitor.router)
api_router.include_router(training_snapshots.router)
api_router.include_router(training_experiments.router)
api_router.include_router(evaluation.router)
api_router.include_router(model_registry.router)
api_router.include_router(deployment.router)
api_router.include_router(inference.router)
api_router.include_router(runtime_monitor.router)
api_router.include_router(governance.router)
api_router.include_router(notifications.router)
api_router.include_router(knowledge.router)
