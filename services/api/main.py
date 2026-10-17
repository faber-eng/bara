from fastapi import FastAPI

from adapters.gemini import ModelGateway, build_vertex_clients
from config import Settings, load_settings
from logs import configure_logging
from routes import health


def build_app(settings: Settings, gateway: ModelGateway) -> FastAPI:
    app = FastAPI(title="bara-api", version=settings.git_sha)
    app.state.settings = settings
    app.state.gateway = gateway
    app.include_router(health.router)
    return app


def create_app() -> FastAPI:
    configure_logging()
    settings = load_settings()
    gateway = ModelGateway(settings.models, build_vertex_clients(settings))
    return build_app(settings, gateway)
