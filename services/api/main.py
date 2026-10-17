import uuid

import firebase_admin
from fastapi import FastAPI
from google.cloud import firestore

from adapters.channels import WebChannel
from adapters.earthengine import EarthEngineTiles
from adapters.factory import (
    Adapters,
    build_adapters,
    build_scenario_resetter,
    utcnow,
)
from adapters.gemini import ModelGateway, build_agent_model, build_vertex_clients
from auth import FirebaseTokenVerifier, TokenVerifier
from bara_agent.agent import build_tools
from bara_agent.run import AgentService
from casework.assignment import TaskAssigner
from casework.messenger import Messenger
from config import Settings, full_flow_region, load_settings, region_timezones
from domain.scenario import load_scenario
from events import DryingRankedHandler, EventDispatcher
from logs import configure_logging
from push_auth import GoogleOidcVerifier
from ratelimit import FailureLimiter
from routes import (
    clock,
    events,
    health,
    join,
    judge_probe,
    judge_reset,
    judge_trigger,
    samples,
    tiles,
)
from scenario_reset import ScenarioResetter
from trigger import JudgeTrigger

JOIN_MAX_FAILURES = 5
JOIN_WINDOW_SECONDS = 15 * 60
RESET_WINDOW_SECONDS = 60 * 60


def build_app(
    settings: Settings, gateway: ModelGateway, verifier: TokenVerifier
) -> FastAPI:
    app = FastAPI(title="bara-api", version=settings.git_sha)
    app.state.settings = settings
    app.state.gateway = gateway
    app.state.verifier = verifier
    app.state.join_limiter = FailureLimiter(JOIN_MAX_FAILURES, JOIN_WINDOW_SECONDS)
    app.state.reset_limiter = FailureLimiter(
        settings.judge_mode.max_resets_per_hour, RESET_WINDOW_SECONDS
    )
    app.include_router(health.router)
    app.include_router(clock.router)
    app.include_router(join.router)
    app.include_router(samples.router)
    app.include_router(judge_probe.router)
    app.include_router(tiles.router)
    app.include_router(events.router)
    app.include_router(judge_trigger.router)
    app.include_router(judge_reset.router)
    return app


def build_token_verifier(settings: Settings) -> TokenVerifier:
    firebase_admin.initialize_app(options={"projectId": settings.project})
    return FirebaseTokenVerifier()


def new_id() -> str:
    return uuid.uuid4().hex


def build_assigner(
    settings: Settings, adapters: Adapters, gateway: ModelGateway
) -> TaskAssigner:
    return TaskAssigner(
        cases=adapters.cases,
        volunteers=adapters.volunteers,
        dams=adapters.dams,
        cells=adapters.cells,
        tasks=adapters.tasks,
        casework=adapters.casework,
        channel=WebChannel(adapters.clock, new_id),
        messenger=Messenger(gateway, settings.default_language),
        scheduler=adapters.scheduler,
        clock=adapters.clock,
        default_deadline_hours=settings.tasks.default_deadline_hours,
        timezones=region_timezones(settings.config_dir),
        new_id=new_id,
    )


def build_agent_service(
    settings: Settings, adapters: Adapters, gateway: ModelGateway
) -> AgentService:
    return AgentService(
        model=build_agent_model(settings),
        tools=build_tools(
            rankings=adapters.rankings,
            cells=adapters.cells,
            dams=adapters.dams,
            volunteers=adapters.volunteers,
            assigner=build_assigner(settings, adapters, gateway),
            radius_m=settings.grid_cell_m,
        ),
        cases=adapters.cases,
        dams=adapters.dams,
        runs=adapters.agent_runs,
        clock=adapters.clock,
        max_llm_calls=settings.agent.max_llm_calls,
    )


def build_dispatcher(
    settings: Settings, adapters: Adapters, agent: AgentService
) -> EventDispatcher:
    drying_ranked = DryingRankedHandler(
        cases=adapters.cases,
        ranked_dams=adapters.ranked_dams,
        agent=agent,
        clock=adapters.clock,
        max_cases=settings.agent.max_cases_per_trigger,
    )
    return EventDispatcher(adapters.events, {"drying.ranked": drying_ranked})


def build_trigger(settings: Settings, adapters: Adapters) -> JudgeTrigger:
    return JudgeTrigger(
        rankings=adapters.rankings,
        ranked_dams=adapters.ranked_dams,
        publisher=adapters.publisher,
        clock=adapters.clock,
        new_id=lambda: uuid.uuid4().hex,
        region=full_flow_region(settings.config_dir),
    )


def build_resetter(settings: Settings) -> ScenarioResetter:
    db = firestore.Client(project=settings.project)
    return build_scenario_resetter(db, load_scenario(settings.scenario_dir))


def create_app() -> FastAPI:
    configure_logging()
    settings = load_settings()
    gateway = ModelGateway(settings.models, build_vertex_clients(settings))
    app = build_app(settings, gateway, build_token_verifier(settings))
    app.state.adapters = build_adapters(settings)
    app.state.agent = build_agent_service(settings, app.state.adapters, gateway)
    app.state.dispatcher = build_dispatcher(
        settings, app.state.adapters, app.state.agent
    )
    app.state.trigger = build_trigger(settings, app.state.adapters)
    app.state.push_verifier = GoogleOidcVerifier()
    app.state.resetter = build_resetter(settings)
    app.state.tiles = EarthEngineTiles(settings.project, settings.config_dir)
    app.state.utcnow = utcnow
    return app
