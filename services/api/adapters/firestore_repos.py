from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from google.cloud import firestore

from adapters.store import Collection, Filter, FirestoreCollection
from contracts import (
    AgentRun,
    Case,
    ClockSettings,
    Contact,
    Dam,
    Escalation,
    EventType,
    Evidence,
    Message,
    ProcessedEvent,
    RankedCell,
    RankedDam,
    Task,
    Volunteer,
    VolunteerRole,
)
from domain.clock import is_due
from domain.reset_scope import ResetSnapshot

CLOCK_DOCUMENT = "clock"
IN_QUERY_LIMIT = 30


class TaskRepository:
    def __init__(self, tasks: Collection[Task]):
        self._tasks = tasks

    def due(self, now: datetime) -> list[Task]:
        open_tasks = self._tasks.where(Filter("status", "==", "open"))
        return [task for task in open_tasks if is_due(task.deadline_at, now)]


class CaseRepository:
    def __init__(self, cases: Collection[Case]):
        self._cases = cases

    def open_for_dam(self, dam_id: str) -> Case | None:
        for_dam = self._cases.where(Filter("dam_id", "==", dam_id))
        live = [case for case in for_dam if case.status != "closed"]
        if not live:
            return None
        return min(live, key=lambda case: (case.opened_at, case.id))

    def get(self, case_id: str) -> Case | None:
        return self._cases.get(case_id)

    def create(self, case: Case) -> bool:
        return self._cases.create_if_absent(case.id, case)

    def delete(self, case_id: str) -> None:
        self._cases.delete_many([case_id])


class VolunteerRepository:
    def __init__(self, volunteers: Collection[Volunteer]):
        self._volunteers = volunteers

    def get(self, volunteer_id: str) -> Volunteer | None:
        return self._volunteers.get(volunteer_id)

    def create_if_absent(self, volunteer: Volunteer) -> bool:
        return self._volunteers.create_if_absent(volunteer.id, volunteer)

    def available(self, role: VolunteerRole) -> list[Volunteer]:
        return self._volunteers.where(
            Filter("role", "==", role), Filter("available", "==", True)
        )


class EventLog:
    def __init__(
        self, events: Collection[ProcessedEvent], utcnow: Callable[[], datetime]
    ):
        self._events = events
        self._utcnow = utcnow

    def claim(self, message_id: str, event_type: EventType) -> bool:
        entry = ProcessedEvent(
            id=message_id, type=event_type, processed_at=self._utcnow()
        )
        return self._events.create_if_absent(message_id, entry)


class FirestoreClockStore:
    def __init__(self, settings: Collection[ClockSettings]):
        self._settings = settings

    def get(self) -> ClockSettings | None:
        return self._settings.get(CLOCK_DOCUMENT)

    def put(self, settings: ClockSettings) -> None:
        self._settings.put(CLOCK_DOCUMENT, settings)

    def add_seconds(self, seconds: int, updated_by: str) -> None:
        self._settings.add(
            CLOCK_DOCUMENT, "offset_seconds", seconds, {"updated_by": updated_by}
        )


class ResetRepository:
    def __init__(
        self,
        volunteers: Collection[Volunteer],
        contacts: Collection[Contact],
        dams: Collection[Dam],
        cases: Collection[Case],
        tasks: Collection[Task],
        evidence: Collection[Evidence],
        messages: Collection[Message],
        escalations: Collection[Escalation],
    ):
        self._volunteers = volunteers
        self._contacts = contacts
        self._dams = dams
        self._cases = cases
        self._tasks = tasks
        self._evidence = evidence
        self._messages = messages
        self._escalations = escalations

    def snapshot(self) -> ResetSnapshot:
        cases = self._cases.where(Filter("example", "==", True))
        case_ids = [case.id for case in cases]
        return ResetSnapshot(
            volunteers=self._volunteers.where(Filter("example", "==", True)),
            contacts=self._contacts.where(Filter("example", "==", True)),
            dams=self._dams.where(Filter("example", "==", True)),
            cases=cases,
            tasks=children(self._tasks, case_ids),
            evidence=children(self._evidence, case_ids),
            messages=children(self._messages, case_ids),
            escalations=children(self._escalations, case_ids),
        )


def children[T](collection: Collection[T], case_ids: list[str]) -> list[T]:
    found: list[T] = []
    for start in range(0, len(case_ids), IN_QUERY_LIMIT):
        chunk = case_ids[start : start + IN_QUERY_LIMIT]
        found.extend(collection.where(Filter("case_id", "in", chunk)))
    return found


class RankingRepository:
    def __init__(self, cells_for: Callable[[str], Collection[RankedCell]]):
        self._cells_for = cells_for

    def top(self, region: str, limit: int) -> list[RankedCell]:
        return self._cells_for(region).where(Filter("rank", "<=", limit))


class RankedDamRepository:
    def __init__(self, dams_for: Callable[[str], Collection[RankedDam]]):
        self._dams_for = dams_for

    def top(self, region: str, limit: int) -> list[RankedDam]:
        ranked = self._dams_for(region).where(Filter("rank", "<=", limit))
        return sorted(ranked, key=lambda dam: dam.rank)


class DamRepository:
    def __init__(self, dams: Collection[Dam]):
        self._dams = dams

    def in_region(self, region: str) -> list[Dam]:
        return self._dams.where(Filter("region", "==", region))

    def get(self, dam_id: str) -> Dam | None:
        return self._dams.get(dam_id)


class AgentRunRepository:
    def __init__(self, runs_for: Callable[[str], Collection[AgentRun]]):
        self._runs_for = runs_for

    def save(self, case_id: str, run: AgentRun) -> None:
        self._runs_for(case_id).put(run.id, run)


@dataclass(frozen=True)
class AgentRepositories:
    rankings: RankingRepository
    ranked_dams: RankedDamRepository
    volunteers: VolunteerRepository
    dams: DamRepository
    agent_runs: AgentRunRepository


def build_agent_repositories(db: firestore.Client) -> AgentRepositories:
    return AgentRepositories(
        rankings=RankingRepository(
            lambda region: FirestoreCollection(
                db, f"rankings/{region}/cells", RankedCell
            )
        ),
        ranked_dams=RankedDamRepository(
            lambda region: FirestoreCollection(db, f"rankings/{region}/dams", RankedDam)
        ),
        volunteers=VolunteerRepository(
            FirestoreCollection(db, "volunteers", Volunteer)
        ),
        dams=DamRepository(FirestoreCollection(db, "dams", Dam)),
        agent_runs=AgentRunRepository(
            lambda case_id: FirestoreCollection(
                db, f"cases/{case_id}/agent_runs", AgentRun
            )
        ),
    )
