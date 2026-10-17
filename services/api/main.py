import firebase_admin
from fastapi import FastAPI

from adapters.earthengine import EarthEngineTiles
from adapters.factory import Adapters, build_adapters, utcnow
from adapters.gemini import ModelGateway, build_agent_model, build_vertex_clients
from auth import FirebaseTokenVerifier, TokenVerifier
from bara_agent.agent import build_tools
from bara_agent.run import AgentService
from config import Settings, load_settings
from logs import configure_logging
from ratelimit import FailureLimiter
from routes import clock, health, join, judge_probe, samples, tiles

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
    app.include_router(clock.router)
    app.include_router(join.router)
    app.include_router(samples.router)
    app.include_router(judge_probe.router)
    app.include_router(tiles.router)
    return app


def build_token_verifier(settings: Settings) -> TokenVerifier:
    firebase_admin.initialize_app(options={"projectId": settings.project})
    return FirebaseTokenVerifier()


def build_agent_service(settings: Settings, adapters: Adapters) -> AgentService:
    return AgentService(
        model=build_agent_model(settings),
        tools=build_tools(
            rankings=adapters.rankings,
            cells=adapters.cells,
            dams=adapters.dams,
            volunteers=adapters.volunteers,
            radius_m=settings.grid_cell_m,
        ),
        cases=adapters.cases,
        dams=adapters.dams,
        runs=adapters.agent_runs,
        clock=adapters.clock,
        max_llm_calls=settings.agent.max_llm_calls,
    )


def create_app() -> FastAPI:
    configure_logging()
    settings = load_settings()
    gateway = ModelGateway(settings.models, build_vertex_clients(settings))
    app = build_app(settings, gateway, build_token_verifier(settings))
    app.state.adapters = build_adapters(settings)
    app.state.agent = build_agent_service(settings, app.state.adapters)
    app.state.tiles = EarthEngineTiles(settings.project, settings.config_dir)
    app.state.utcnow = utcnow
    return app
