from fastapi import APIRouter, Request

from adapters.gemini import ModelGateway
from config import Settings
from contracts import Health, HealthModels

router = APIRouter(prefix="/api")


@router.get("/health", response_model=Health)
def health(request: Request) -> Health:
    settings: Settings = request.app.state.settings
    gateway: ModelGateway = request.app.state.gateway
    return Health(
        status="ok",
        models=HealthModels(
            reasoning=settings.models.reasoning.model, fast=settings.models.fast.model
        ),
        fallback_used=gateway.fallback_used,
        git_sha=settings.git_sha,
    )
