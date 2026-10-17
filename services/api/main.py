import firebase_admin
from fastapi import FastAPI

from adapters.earthengine import EarthEngineTiles
from adapters.factory import build_adapters, utcnow
from adapters.gemini import ModelGateway, build_vertex_clients
from auth import FirebaseTokenVerifier, TokenVerifier
from config import Settings, load_settings
from logs import configure_logging
from ratelimit import FailureLimiter
from routes import health, join, judge_probe, samples, tiles

JOIN_MAX_FAILURES = 5
JOIN_WINDOW_SECONDS = 15 * 60


def build_app(
    settings: Settings, gateway: ModelGateway, verifier: TokenVerifier
) -> FastAPI:
    app = FastAPI(title="bara-api", version=settings.git_sha)
    app.state.settings = settings
    app.state.gateway = gateway
    app.state.verifier = verifier
    app.state.join_limiter = FailureLimiter(JOIN_MAX_FAILURES, JOIN_WINDOW_SECONDS)
    app.include_router(health.router)
    app.include_router(join.router)
    app.include_router(samples.router)
    app.include_router(judge_probe.router)
    app.include_router(tiles.router)
    return app


def build_token_verifier(settings: Settings) -> TokenVerifier:
    firebase_admin.initialize_app(options={"projectId": settings.project})
    return FirebaseTokenVerifier()


def create_app() -> FastAPI:
    configure_logging()
    settings = load_settings()
    gateway = ModelGateway(settings.models, build_vertex_clients(settings))
    app = build_app(settings, gateway, build_token_verifier(settings))
    app.state.adapters = build_adapters(settings)
    app.state.tiles = EarthEngineTiles(settings.project, settings.config_dir)
    app.state.utcnow = utcnow
    return app
