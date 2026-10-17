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

from adapters.bigquery import Warehouse
from adapters.firestore_repos import (
    CaseRepository,
    EventLog,
    FirestoreClockStore,
    TaskRepository,
    VolunteerRepository,
)
from adapters.identity import ClaimsAdmin, FirebaseClaimsAdmin
from adapters.pubsub import EventPublisher
from adapters.secrets import SecretManagerReader, SecretReader
from adapters.storage import AdcSigningAuth, EvidenceStorage
from adapters.store import FirestoreCollection
from adapters.tasks import DeadlineScheduler
from config import Settings
from contracts import Case, ClockSettings, ProcessedEvent, Task, Volunteer
from domain.clock import Clock

logger = logging.getLogger(__name__)

DATASET = "bara"
DEADLINE_QUEUE = "task-deadlines"


@dataclass(frozen=True)
class Adapters:
    clock: Clock
    tasks: TaskRepository
    cases: CaseRepository
    events: EventLog
    warehouse: Warehouse
    storage: EvidenceStorage
    publisher: EventPublisher
    scheduler: DeadlineScheduler | None
    volunteers: VolunteerRepository
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


def build_adapters(settings: Settings) -> Adapters:
    db = firestore.Client(project=settings.project)
    clock_store = FirestoreClockStore(
        FirestoreCollection(db, "settings", ClockSettings)
    )
    bucket = storage.Client(project=settings.project).bucket(settings.evidence_bucket)
    return Adapters(
        clock=Clock(clock_store, utcnow),
        tasks=TaskRepository(FirestoreCollection(db, "tasks", Task)),
        cases=CaseRepository(FirestoreCollection(db, "cases", Case)),
        events=EventLog(FirestoreCollection(db, "events", ProcessedEvent), utcnow),
        warehouse=Warehouse(
            bigquery.Client(project=settings.project), settings.project, DATASET
        ),
        storage=EvidenceStorage(bucket, AdcSigningAuth),
        publisher=EventPublisher(pubsub_v1.PublisherClient(), settings.project),
        scheduler=build_scheduler(settings),
        volunteers=VolunteerRepository(
            FirestoreCollection(db, "volunteers", Volunteer)
        ),
        secrets=SecretManagerReader(
            secretmanager.SecretManagerServiceClient(), settings.project
        ),
        claims=FirebaseClaimsAdmin(),
    )
