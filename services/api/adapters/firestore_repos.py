from collections.abc import Callable
from datetime import datetime

from adapters.store import Collection, Filter
from contracts import (
    Case,
    ClockSettings,
    Contact,
    Dam,
    Escalation,
    EventType,
    Evidence,
    Message,
    ProcessedEvent,
    Task,
    Volunteer,
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
        return min(live, key=lambda case: case.opened_at)


class VolunteerRepository:
    def __init__(self, volunteers: Collection[Volunteer]):
        self._volunteers = volunteers

    def get(self, volunteer_id: str) -> Volunteer | None:
        return self._volunteers.get(volunteer_id)

    def create_if_absent(self, volunteer: Volunteer) -> bool:
        return self._volunteers.create_if_absent(volunteer.id, volunteer)


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
