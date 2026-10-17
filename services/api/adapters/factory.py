import logging
from dataclasses import dataclass
from datetime import UTC, datetime

from google.cloud import (
    bigquery,
    firestore,
    pubsub_v1,
    secretmanager,
    storage,
    tasks_v2,
)

from adapters.bigquery import DATASET, Warehouse
from adapters.cells import CellRepository
from adapters.firestore_repos import (
    CASES,
    MESSAGES,
    TASKS,
    UPLOADS,
    VERDICT_CACHE,
    AgentRunRepository,
    CaseRepository,
    CaseworkStore,
    DamRepository,
    EventLog,
    EvidenceRepository,
    FirestoreClockStore,
    MessageRepository,
    RankedDamRepository,
    RankingRepository,
    ResetRepository,
    TaskRepository,
    UploadRepository,
    VerdictCache,
    VolunteerRepository,
    build_agent_repositories,
)
from adapters.identity import ClaimsAdmin, FirebaseClaimsAdmin
from adapters.pubsub import EventPublisher
from adapters.secrets import SecretManagerReader, SecretReader
from adapters.storage import AdcSigningAuth, EvidenceStorage
from adapters.store import FirestoreCollection, FirestoreTransactor
from adapters.tasks import DeadlineScheduler
from config import Settings
from contracts import (
    AgentRun,
    Case,
    ClockSettings,
    Contact,
    Dam,
    Escalation,
    Evidence,
    Message,
    PendingUpload,
    ProcessedEvent,
    Task,
    VerdictCacheEntry,
    Volunteer,
)
from domain.clock import Clock
from domain.scenario import Scenario
from scenario_reset import ScenarioResetter

logger = logging.getLogger(__name__)

DEADLINE_QUEUE = "task-deadlines"


@dataclass(frozen=True)
class Adapters:
    clock: Clock
    tasks: TaskRepository
    cases: CaseRepository
    casework: CaseworkStore
    events: EventLog
    warehouse: Warehouse
    storage: EvidenceStorage
    publisher: EventPublisher
    scheduler: DeadlineScheduler | None
    cells: CellRepository
    rankings: RankingRepository
    ranked_dams: RankedDamRepository
    evidence: EvidenceRepository
    uploads: UploadRepository
    messages: MessageRepository
    verdicts: VerdictCache
    volunteers: VolunteerRepository
    dams: DamRepository
    agent_runs: AgentRunRepository
    secrets: SecretReader
    claims: ClaimsAdmin


def utcnow() -> datetime:
    return datetime.now(UTC)


def build_scheduler(settings: Settings) -> DeadlineScheduler | None:
    if settings.api_url is None:
        logger.warning(
            "deadline scheduler disabled",
            extra={"fields": {"reason": "BARA_API_URL is not set"}},
        )
        return None
    return DeadlineScheduler(
        tasks_v2.CloudTasksClient(),
        project=settings.project,
        location=settings.region,
        queue=DEADLINE_QUEUE,
        api_url=settings.api_url,
        invoker_email=settings.tasks_invoker_email,
    )


def build_scenario_resetter(
    db: firestore.Client, scenario: Scenario
) -> ScenarioResetter:
    clock_store = FirestoreClockStore(
        FirestoreCollection(db, "settings", ClockSettings)
    )
    repository = ResetRepository(
        volunteers=FirestoreCollection(db, "volunteers", Volunteer),
        contacts=FirestoreCollection(db, "contacts", Contact),
        dams=FirestoreCollection(db, "dams", Dam),
        cases=FirestoreCollection(db, CASES, Case),
        tasks=FirestoreCollection(db, TASKS, Task),
        evidence=FirestoreCollection(db, "evidence", Evidence),
        messages=FirestoreCollection(db, MESSAGES, Message),
        escalations=FirestoreCollection(db, "escalations", Escalation),
        agent_runs_for=lambda case_id: FirestoreCollection(
            db, f"cases/{case_id}/agent_runs", AgentRun
        ),
    )
    return ScenarioResetter(
        repository=repository, clock=Clock(clock_store, utcnow), scenario=scenario
    )


def build_adapters(settings: Settings) -> Adapters:
    db = firestore.Client(project=settings.project)
    clock_store = FirestoreClockStore(
        FirestoreCollection(db, "settings", ClockSettings)
    )
    bucket = storage.Client(project=settings.project).bucket(settings.evidence_bucket)
    warehouse = Warehouse(
        bigquery.Client(project=settings.project), settings.project, DATASET
    )
    agent_repos = build_agent_repositories(db)
    return Adapters(
        clock=Clock(clock_store, utcnow),
        tasks=TaskRepository(FirestoreCollection(db, TASKS, Task)),
        cases=CaseRepository(FirestoreCollection(db, CASES, Case)),
        casework=CaseworkStore(FirestoreTransactor(db)),
        events=EventLog(FirestoreCollection(db, "events", ProcessedEvent), utcnow),
        warehouse=warehouse,
        storage=EvidenceStorage(bucket, AdcSigningAuth),
        publisher=EventPublisher(pubsub_v1.PublisherClient(), settings.project),
        scheduler=build_scheduler(settings),
        cells=CellRepository(warehouse),
        rankings=agent_repos.rankings,
        ranked_dams=agent_repos.ranked_dams,
        evidence=agent_repos.evidence,
        uploads=UploadRepository(FirestoreCollection(db, UPLOADS, PendingUpload)),
        messages=MessageRepository(FirestoreCollection(db, MESSAGES, Message)),
        verdicts=VerdictCache(
            FirestoreCollection(db, VERDICT_CACHE, VerdictCacheEntry)
        ),
        volunteers=agent_repos.volunteers,
        dams=agent_repos.dams,
        agent_runs=agent_repos.agent_runs,
        secrets=SecretManagerReader(
            secretmanager.SecretManagerServiceClient(), settings.project
        ),
        claims=FirebaseClaimsAdmin(),
    )
