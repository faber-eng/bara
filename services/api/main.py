import uuid

import firebase_admin
from fastapi import FastAPI
from fastapi.middleware.gzip import GZipMiddleware
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
from adapters.reignition import ReignitionScores
from adapters.trigger_gate import FirestoreTriggerGateStore
from area_queries import AreaQueries
from auth import FirebaseTokenVerifier, TokenVerifier
from bara_agent.agent import build_tools
from bara_agent.run import AgentService
from bara_agent.tools.get_area_facts import GetAreaFacts
from case_queries import CaseQueries
from casework.assignment import TaskAssigner
from casework.brief import BriefWriter
from casework.deadline import DeadlineHandler
from casework.escalation import Acknowledger, BrigadeInbox, Escalator
from casework.evidence_check import EvidenceChecker
from casework.evidence_intake import EvidenceIntake
from casework.evidence_reader import EvidenceReader
from casework.explanation_batch import ExplanationPrecomputer
from casework.inbox import InboxReader
from casework.messenger import Messenger
from casework.rank_explanation import RankExplainer
from casework.review import ReviewDesk
from casework.trigger_gate import TriggerGate
from config import Settings, full_flow_region, load_settings, region_timezones
from domain.scenario import load_scenario
from events import DryingRankedHandler, EventDispatcher
from evidence_events import EvidenceReceivedHandler
from fire_events import FireQuietHandler
from logs import configure_logging
from overdue_events import TaskOverdueHandler
from public_queries import PublicQueries
from push_auth import GoogleOidcVerifier
from ratelimit import FailureLimiter, RequestLimiter
from routes import (
    brigade,
    clock,
    deadline,
    events,
    health,
    join,
    judge_advance,
    judge_probe,
    judge_reset,
    judge_trigger,
    ops_areas,
    ops_cases,
    public,
    samples,
    tiles,
    volunteer,
)
from run_stream import RunStreamer
from scenario_reset import ScenarioResetter
from stream_cors import StreamOnlyCors
from trigger import JudgeTrigger

JOIN_MAX_FAILURES = 5
JOIN_WINDOW_SECONDS = 15 * 60
RESET_WINDOW_SECONDS = 60 * 60
PUBLIC_MAX_REQUESTS = 60
PUBLIC_WINDOW_SECONDS = 60
GZIP_MIN_BYTES = 1024
GZIP_LEVEL = 5


def cors_origins(settings: Settings) -> list[str]:
    return [
        f"https://{settings.project}.web.app",
        f"https://{settings.project}.firebaseapp.com",
        "http://localhost:5173",
    ]


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
    app.state.public_limiter = RequestLimiter(
        PUBLIC_MAX_REQUESTS, PUBLIC_WINDOW_SECONDS
    )
    app.add_middleware(
        GZipMiddleware, minimum_size=GZIP_MIN_BYTES, compresslevel=GZIP_LEVEL
    )
    app.add_middleware(StreamOnlyCors, allow_origins=cors_origins(settings))
    app.include_router(health.router)
    app.include_router(clock.router)
    app.include_router(join.router)
    app.include_router(samples.router)
    app.include_router(judge_probe.router)
    app.include_router(tiles.router)
    app.include_router(public.router)
    app.include_router(events.router)
    app.include_router(judge_trigger.router)
    app.include_router(judge_reset.router)
    app.include_router(judge_advance.router)
    app.include_router(deadline.router)
    app.include_router(ops_cases.router)
    app.include_router(ops_areas.router)
    app.include_router(volunteer.router)
    app.include_router(brigade.router)
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


def build_checker(
    settings: Settings, adapters: Adapters, gateway: ModelGateway
) -> EvidenceChecker:
    return EvidenceChecker(
        evidence=adapters.evidence,
        tasks=adapters.tasks,
        cases=adapters.cases,
        storage=adapters.storage,
        cache=adapters.verdicts,
        casework=adapters.casework,
        reader=EvidenceReader(gateway),
        clock=adapters.clock,
        model=settings.models.for_role("fast").model,
        human_review_confidence=settings.tasks.human_review_confidence,
        location_tolerance_m=settings.tasks.location_tolerance_m,
    )


def build_escalator(adapters: Adapters, gateway: ModelGateway) -> Escalator:
    return Escalator(
        cases=adapters.cases,
        tasks=adapters.tasks,
        evidence=adapters.evidence,
        runs=adapters.agent_runs,
        dams=adapters.dams,
        contacts=adapters.contacts,
        escalations=adapters.escalations,
        cells=adapters.cells,
        casework=adapters.casework,
        brief=BriefWriter(gateway),
        channel=WebChannel(adapters.clock, new_id),
        publisher=adapters.publisher,
        clock=adapters.clock,
        new_id=new_id,
    )


def build_review_desk(
    settings: Settings,
    adapters: Adapters,
    gateway: ModelGateway,
    escalator: Escalator,
) -> ReviewDesk:
    return ReviewDesk(
        cases=adapters.cases,
        tasks=adapters.tasks,
        volunteers=adapters.volunteers,
        cells=adapters.cells,
        casework=adapters.casework,
        assigner=build_assigner(settings, adapters, gateway),
        escalator=escalator,
        channel=WebChannel(adapters.clock, new_id),
        clock=adapters.clock,
    )


def build_acknowledger(adapters: Adapters) -> Acknowledger:
    return Acknowledger(
        escalations=adapters.escalations,
        cases=adapters.cases,
        casework=adapters.casework,
        clock=adapters.clock,
    )


def build_brigade_inbox(adapters: Adapters) -> BrigadeInbox:
    return BrigadeInbox(escalations=adapters.escalations, signer=adapters.storage)


def build_intake(adapters: Adapters) -> EvidenceIntake:
    return EvidenceIntake(
        tasks=adapters.tasks,
        cases=adapters.cases,
        uploads=adapters.uploads,
        evidence=adapters.evidence,
        casework=adapters.casework,
        storage=adapters.storage,
        scheduler=adapters.scheduler,
        publisher=adapters.publisher,
        clock=adapters.clock,
        new_id=new_id,
    )


def build_inbox(adapters: Adapters) -> InboxReader:
    return InboxReader(
        tasks=adapters.tasks, messages=adapters.messages, evidence=adapters.evidence
    )


def build_agent_service(
    settings: Settings,
    adapters: Adapters,
    gateway: ModelGateway,
    checker: EvidenceChecker,
    escalator: Escalator,
) -> AgentService:
    return AgentService(
        model=build_agent_model(settings),
        tools=build_tools(
            rankings=adapters.rankings,
            cells=adapters.cells,
            dams=adapters.dams,
            volunteers=adapters.volunteers,
            assigner=build_assigner(settings, adapters, gateway),
            checker=checker,
            escalator=escalator,
            reviewer=build_review_desk(settings, adapters, gateway, escalator),
            radius_m=settings.grid_cell_m,
        ),
        cases=adapters.cases,
        dams=adapters.dams,
        runs=adapters.agent_runs,
        clock=adapters.clock,
        max_llm_calls=settings.agent.max_llm_calls,
    )


def build_dispatcher(
    settings: Settings,
    adapters: Adapters,
    agent: AgentService,
    checker: EvidenceChecker,
    assigner: TaskAssigner,
    escalator: Escalator,
    explanations: ExplanationPrecomputer,
) -> EventDispatcher:
    drying_ranked = DryingRankedHandler(
        cases=adapters.cases,
        ranked_dams=adapters.ranked_dams,
        agent=agent,
        explanations=explanations,
        clock=adapters.clock,
        max_cases=settings.agent.max_cases_per_trigger,
    )
    fire_quiet = FireQuietHandler(
        cases=adapters.cases,
        tasks=adapters.tasks,
        volunteers=adapters.volunteers,
        cells=adapters.cells,
        assigner=assigner,
        clock=adapters.clock,
        spots=settings.reignition.recheck_spots_per_fire,
        recheck_hours=settings.reignition.recheck_after_hours,
    )
    evidence_received = EvidenceReceivedHandler(checker=checker, agent=agent)
    task_overdue = TaskOverdueHandler(
        cases=adapters.cases,
        tasks=adapters.tasks,
        evidence=adapters.evidence,
        agent=agent,
        escalator=escalator,
    )
    return EventDispatcher(
        adapters.events,
        {
            "drying.ranked": drying_ranked,
            "fire.quiet": fire_quiet,
            "evidence.received": evidence_received,
            "task.overdue": task_overdue,
        },
    )


def build_deadlines(adapters: Adapters) -> DeadlineHandler:
    return DeadlineHandler(
        tasks=adapters.tasks,
        cases=adapters.cases,
        casework=adapters.casework,
        publisher=adapters.publisher,
        scheduler=adapters.scheduler,
        clock=adapters.clock,
        new_id=new_id,
    )


def build_trigger(settings: Settings, adapters: Adapters) -> JudgeTrigger:
    return JudgeTrigger(
        rankings=adapters.rankings,
        ranked_dams=adapters.ranked_dams,
        publisher=adapters.publisher,
        clock=adapters.clock,
        new_id=lambda: uuid.uuid4().hex,
        region=full_flow_region(settings.config_dir),
        scenario=load_scenario(settings.scenario_dir),
    )


def build_trigger_gate(settings: Settings) -> TriggerGate:
    db = firestore.Client(project=settings.project)
    return TriggerGate(FirestoreTriggerGateStore(db), utcnow)


def build_resetter(settings: Settings) -> ScenarioResetter:
    db = firestore.Client(project=settings.project)
    return build_scenario_resetter(db, load_scenario(settings.scenario_dir))


def build_case_queries(adapters: Adapters) -> CaseQueries:
    return CaseQueries(
        cases=adapters.cases,
        tasks=adapters.tasks,
        evidence=adapters.evidence,
        runs=adapters.agent_runs,
        escalations=adapters.escalations,
        messages=adapters.messages,
        signer=adapters.storage,
        clock=adapters.clock,
    )


def build_area_queries(settings: Settings, adapters: Adapters) -> AreaQueries:
    return AreaQueries(
        rankings=adapters.rankings,
        ranked_dams=adapters.ranked_dams,
        cells=adapters.cells,
        dams=adapters.dams,
        cases=adapters.cases,
        evidence=adapters.evidence,
        radius_m=settings.grid_cell_m,
    )


def build_run_streamer(adapters: Adapters) -> RunStreamer:
    return RunStreamer(cases=adapters.cases, runs=adapters.agent_runs, now=utcnow)


def build_rank_explainer(
    settings: Settings, adapters: Adapters, gateway: ModelGateway
) -> RankExplainer:
    return RankExplainer(
        model=gateway,
        facts=GetAreaFacts(adapters.cells, adapters.dams, settings.grid_cell_m),
        rankings=adapters.rankings,
    )


def build_explanation_precomputer(
    settings: Settings, adapters: Adapters, gateway: ModelGateway
) -> ExplanationPrecomputer:
    return ExplanationPrecomputer(
        explainer=build_rank_explainer(settings, adapters, gateway),
        rankings=adapters.rankings,
    )


def build_public_queries(settings: Settings, adapters: Adapters) -> PublicQueries:
    return PublicQueries(
        rankings=adapters.rankings,
        dams=adapters.dams,
        cases=adapters.cases,
        tasks=adapters.tasks,
        evidence=adapters.evidence,
        escalations=adapters.escalations,
        bulletins=adapters.bulletins,
        zones=region_timezones(settings.config_dir),
    )


def build_tiles(settings: Settings, adapters: Adapters) -> EarthEngineTiles:
    return EarthEngineTiles(
        settings.project,
        settings.config_dir,
        ReignitionScores(adapters.warehouse),
    )


def create_app() -> FastAPI:
    configure_logging()
    settings = load_settings()
    gateway = ModelGateway(settings.models, build_vertex_clients(settings))
    app = build_app(settings, gateway, build_token_verifier(settings))
    app.state.adapters = build_adapters(settings)
    checker = build_checker(settings, app.state.adapters, gateway)
    escalator = build_escalator(app.state.adapters, gateway)
    app.state.agent = build_agent_service(
        settings, app.state.adapters, gateway, checker, escalator
    )
    app.state.dispatcher = build_dispatcher(
        settings,
        app.state.adapters,
        app.state.agent,
        checker,
        build_assigner(settings, app.state.adapters, gateway),
        escalator,
        build_explanation_precomputer(settings, app.state.adapters, gateway),
    )
    app.state.evidence_intake = build_intake(app.state.adapters)
    app.state.inbox_reader = build_inbox(app.state.adapters)
    app.state.review_desk = build_review_desk(
        settings, app.state.adapters, gateway, escalator
    )
    app.state.acknowledger = build_acknowledger(app.state.adapters)
    app.state.brigade_inbox = build_brigade_inbox(app.state.adapters)
    app.state.trigger = build_trigger(settings, app.state.adapters)
    app.state.trigger_gate = build_trigger_gate(settings)
    app.state.deadlines = build_deadlines(app.state.adapters)
    app.state.push_verifier = GoogleOidcVerifier()
    app.state.resetter = build_resetter(settings)
    app.state.case_queries = build_case_queries(app.state.adapters)
    app.state.area_queries = build_area_queries(settings, app.state.adapters)
    app.state.run_streamer = build_run_streamer(app.state.adapters)
    app.state.rank_explainer = build_rank_explainer(
        settings, app.state.adapters, gateway
    )
    app.state.public_queries = build_public_queries(settings, app.state.adapters)
    app.state.tiles = build_tiles(settings, app.state.adapters)
    app.state.utcnow = utcnow
    return app
