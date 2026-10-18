from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime

from google.cloud import firestore

from adapters.store import (
    Collection,
    Filter,
    FirestoreCollection,
    Guard,
    GuardFailed,
    Missing,
    Precondition,
    Put,
    Transactor,
    Update,
    Write,
)
from contracts import (
    AgentRun,
    Bulletin,
    Case,
    CaseStatus,
    ClockSettings,
    Contact,
    Dam,
    DamState,
    Escalation,
    EventType,
    Evidence,
    Message,
    PendingUpload,
    ProcessedEvent,
    RankedCell,
    RankedDam,
    RankExplanation,
    RankingRun,
    Task,
    Verdict,
    VerdictCacheEntry,
    Volunteer,
    VolunteerRole,
)
from domain.clock import is_due
from domain.reset_scope import ResetScope, ResetSnapshot
from domain.scenario import Scenario

CLOCK_DOCUMENT = "clock"
TASKS = "tasks"
HOLDING_STATUSES = ("open", "overdue")
CASES = "cases"
MESSAGES = "messages"
EVIDENCE = "evidence"
UPLOADS = "uploads"
DAMS = "dams"
VERDICT_CACHE = "verdict_cache"
ESCALATIONS = "escalations"
CONTACTS = "contacts"
IN_QUERY_LIMIT = 30


class TaskRepository:
    def __init__(self, tasks: Collection[Task]):
        self._tasks = tasks

    def get(self, task_id: str) -> Task | None:
        return self._tasks.get(task_id)

    def save(self, task: Task) -> None:
        self._tasks.put(task.id, task)

    def set_cloud_task_name(self, task_id: str, name: str) -> None:
        self._tasks.update(task_id, {"cloud_task_name": name})

    def for_assignee(self, assignee_id: str) -> list[Task]:
        return self._tasks.where(Filter("assignee_id", "==", assignee_id))

    def for_case(self, case_id: str) -> list[Task]:
        return self._tasks.where(Filter("case_id", "==", case_id))

    def due(self, now: datetime) -> list[Task]:
        open_tasks = self._tasks.where(Filter("status", "==", "open"))
        return [task for task in open_tasks if is_due(task.deadline_at, now)]

    def for_cases(self, case_ids: list[str]) -> list[Task]:
        return children(self._tasks, case_ids)

    def open_assignees(self) -> set[str]:
        held = matching(self._tasks, "status", list(HOLDING_STATUSES))
        return {task.assignee_id for task in held}


class EvidenceRepository:
    def __init__(self, evidence: Collection[Evidence]):
        self._evidence = evidence

    def for_cases(self, case_ids: list[str]) -> list[Evidence]:
        return children(self._evidence, case_ids)

    def get(self, evidence_id: str) -> Evidence | None:
        return self._evidence.get(evidence_id)

    def for_uploader(self, uploaded_by: str) -> list[Evidence]:
        return self._evidence.where(Filter("uploaded_by", "==", uploaded_by))


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

    def search(self, region: str | None, status: str | None) -> list[Case]:
        filters = []
        if region is not None:
            filters.append(Filter("region", "==", region))
        if status is not None:
            filters.append(Filter("status", "==", status))
        found = self._cases.where(*filters)
        return sorted(found, key=lambda case: (case.opened_at, case.id), reverse=True)

    def in_cell(self, cell_id: str) -> list[Case]:
        return self._cases.where(Filter("cell_id", "==", cell_id))

    def live_in_cell(self, cell_id: str) -> Case | None:
        live = [case for case in self.in_cell(cell_id) if case.status != "closed"]
        if not live:
            return None
        return min(live, key=lambda case: (case.opened_at, case.id))

    def mark_closed(self, case_id: str, closed_by: str, closed_at: datetime) -> None:
        self._cases.update(
            case_id,
            {"status": "closed", "closed_by": closed_by, "closed_at": closed_at},
        )

    def create(self, case: Case) -> bool:
        return self._cases.create_if_absent(case.id, case)

    def delete(self, case_id: str) -> None:
        self._cases.delete_many([case_id])


class CaseChanged(Exception):
    pass


@dataclass(frozen=True)
class StatusChange:
    case_id: str
    expected: CaseStatus
    next: CaseStatus


@dataclass(frozen=True)
class DamCheck:
    dam_id: str
    state: DamState
    checked_at: datetime


def status_writes(change: StatusChange | None) -> tuple[list[Guard], list[Write]]:
    if change is None:
        return [], []
    guard = Guard(CASES, change.case_id, "status", change.expected)
    return [guard], [Update(CASES, change.case_id, {"status": change.next})]


class CaseworkStore:
    def __init__(self, transactor: Transactor):
        self._transactor = transactor

    def commit_assignment(
        self,
        *,
        expected_status: CaseStatus,
        next_status: CaseStatus,
        task: Task,
        message: Message,
        reassigned_task_ids: Sequence[str],
    ) -> None:
        writes: list[Write] = [
            Put(TASKS, task.id, task),
            Put(MESSAGES, message.id, message),
            Update(CASES, task.case_id, {"status": next_status}),
        ]
        for task_id in reassigned_task_ids:
            writes.append(Update(TASKS, task_id, {"status": "reassigned"}))
        guard = Guard(CASES, task.case_id, "status", expected_status)
        self._commit(
            [guard], writes, f"case {task.case_id} is no longer {expected_status}"
        )

    def commit_evidence(
        self,
        *,
        evidence: Evidence,
        done_at: datetime | None,
        case_change: StatusChange | None,
    ) -> None:
        guards: list[Precondition] = [Missing(EVIDENCE, evidence.id)]
        writes: list[Write] = [Put(EVIDENCE, evidence.id, evidence)]
        if done_at is not None:
            guards.append(Guard(TASKS, evidence.task_id, "status", "open"))
            writes.append(
                Update(TASKS, evidence.task_id, {"status": "done", "done_at": done_at})
            )
        case_guards, case_writes = status_writes(case_change)
        self._commit(
            guards + case_guards,
            writes + case_writes,
            f"evidence {evidence.id} or its task or case changed",
        )

    def commit_overdue(self, *, task_id: str, case_change: StatusChange | None) -> None:
        case_guards, case_writes = status_writes(case_change)
        self._commit(
            [Guard(TASKS, task_id, "status", "open"), *case_guards],
            [Update(TASKS, task_id, {"status": "overdue"}), *case_writes],
            f"task {task_id} or its case changed",
        )

    def move_case(self, change: StatusChange) -> None:
        guards, writes = status_writes(change)
        self._commit(
            guards, writes, f"case {change.case_id} is no longer {change.expected}"
        )

    def commit_verdict(
        self,
        *,
        evidence_id: str,
        verdict: Verdict,
        location_ok: bool | None,
        case_change: StatusChange | None,
        dam_check: DamCheck | None,
        smoke_case_id: str | None,
    ) -> None:
        unread = Guard(EVIDENCE, evidence_id, "verdict", None)
        writes: list[Write] = [
            Update(
                EVIDENCE,
                evidence_id,
                {"verdict": verdict.model_dump(), "location_ok": location_ok},
            )
        ]
        case_guards, case_writes = status_writes(case_change)
        if dam_check is not None:
            writes.append(
                Update(
                    DAMS,
                    dam_check.dam_id,
                    {
                        "last_state": dam_check.state,
                        "last_checked_at": dam_check.checked_at,
                    },
                )
            )
        if smoke_case_id is not None:
            writes.append(
                Update(CASES, smoke_case_id, {"history_flags.smoke_seen": True})
            )
        self._commit(
            [unread, *case_guards],
            writes + case_writes,
            f"evidence {evidence_id} or its case changed",
        )

    def commit_escalation(
        self, *, escalation: Escalation, message: Message, case_change: StatusChange
    ) -> None:
        guards, case_writes = status_writes(case_change)
        writes: list[Write] = [
            Put(ESCALATIONS, escalation.id, escalation),
            Put(MESSAGES, message.id, message),
            *case_writes,
        ]
        self._commit(
            guards,
            writes,
            f"case {case_change.case_id} is no longer {case_change.expected}",
        )

    def commit_review(
        self,
        *,
        case_id: str,
        message: Message,
        closed_by: str,
        closed_at: datetime,
    ) -> None:
        fields = {"status": "closed", "closed_by": closed_by, "closed_at": closed_at}
        self._commit(
            [Guard(CASES, case_id, "status", "human_review")],
            [Put(MESSAGES, message.id, message), Update(CASES, case_id, fields)],
            f"case {case_id} is no longer human_review",
        )

    def save_note(self, message: Message) -> None:
        self._commit([], [Put(MESSAGES, message.id, message)], "note not saved")

    def save_messages(self, messages: Sequence[Message]) -> None:
        writes = [Put(MESSAGES, message.id, message) for message in messages]
        self._commit([], writes, "messages not saved")

    def commit_ack(
        self,
        *,
        escalation_id: str,
        acknowledged_at: datetime,
        case_change: StatusChange | None,
    ) -> None:
        unacked = Guard(ESCALATIONS, escalation_id, "acknowledged_at", None)
        case_guards, case_writes = status_writes(case_change)
        writes: list[Write] = [
            Update(ESCALATIONS, escalation_id, {"acknowledged_at": acknowledged_at}),
            *case_writes,
        ]
        self._commit(
            [unacked, *case_guards],
            writes,
            f"escalation {escalation_id} or its case changed",
        )

    def _commit(
        self, guards: Sequence[Precondition], writes: Sequence[Write], reason: str
    ) -> None:
        try:
            self._transactor.commit(guards, writes)
        except GuardFailed as error:
            raise CaseChanged(reason) from error


class EscalationRepository:
    def __init__(self, escalations: Collection[Escalation]):
        self._escalations = escalations

    def get(self, escalation_id: str) -> Escalation | None:
        return self._escalations.get(escalation_id)

    def open_for_contact(self, contact_id: str) -> list[Escalation]:
        return self._escalations.where(
            Filter("contact_id", "==", contact_id),
            Filter("acknowledged_at", "==", None),
        )

    def for_case(self, case_id: str) -> list[Escalation]:
        return self._escalations.where(Filter("case_id", "==", case_id))

    def for_cases(self, case_ids: list[str]) -> list[Escalation]:
        return children(self._escalations, case_ids)

    def open_for_case(self, case_id: str) -> Escalation | None:
        for escalation in self.for_case(case_id):
            if escalation.acknowledged_at is None:
                return escalation
        return None


class ContactRepository:
    def __init__(self, contacts: Collection[Contact]):
        self._contacts = contacts

    def for_region(self, region: str) -> list[Contact]:
        return self._contacts.where(Filter("region", "==", region))

    def get(self, contact_id: str) -> Contact | None:
        return self._contacts.get(contact_id)

    def create_if_absent(self, contact: Contact) -> bool:
        return self._contacts.create_if_absent(contact.id, contact)


class MessageRepository:
    def __init__(self, messages: Collection[Message]):
        self._messages = messages

    def to(self, recipient_id: str) -> list[Message]:
        return self._messages.where(Filter("to_id", "==", recipient_id))

    def notes_for_case(self, case_id: str) -> list[Message]:
        return self._messages.where(
            Filter("case_id", "==", case_id), Filter("thread", "==", "ops")
        )


class UploadRepository:
    def __init__(self, uploads: Collection[PendingUpload]):
        self._uploads = uploads

    def get(self, evidence_id: str) -> PendingUpload | None:
        return self._uploads.get(evidence_id)

    def save(self, upload: PendingUpload) -> None:
        self._uploads.put(upload.id, upload)


class VerdictCache:
    def __init__(self, entries: Collection[VerdictCacheEntry]):
        self._entries = entries

    def get(self, key: str) -> VerdictCacheEntry | None:
        return self._entries.get(key)

    def put(self, entry: VerdictCacheEntry) -> None:
        self._entries.put(entry.id, entry)


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

    def names(self, volunteer_ids: list[str]) -> dict[str, str]:
        found = matching(self._volunteers, "id", volunteer_ids)
        return {volunteer.id: volunteer.name for volunteer in found}


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

    def release(self, message_id: str) -> None:
        self._events.delete_many([message_id])


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
        agent_runs_for: Callable[[str], Collection[AgentRun]],
    ):
        self._agent_runs_for = agent_runs_for
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
        volunteers = self._volunteers.where(Filter("example", "==", True))
        contacts = self._contacts.where(Filter("example", "==", True))
        people = [person.id for person in volunteers] + [c.id for c in contacts]
        return ResetSnapshot(
            volunteers=volunteers,
            contacts=contacts,
            dams=self._dams.where(Filter("example", "==", True)),
            cases=cases,
            tasks=children(self._tasks, case_ids),
            evidence=children(self._evidence, case_ids),
            messages=children(self._messages, case_ids)
            + caseless_messages(self._messages, people),
            escalations=children(self._escalations, case_ids),
        )

    def delete(self, scope: ResetScope) -> None:
        for case_id in sorted(scope.case_ids):
            runs = self._agent_runs_for(case_id)
            runs.delete_many([run.id for run in runs.where()])
        self._tasks.delete_many(scope.task_ids)
        self._evidence.delete_many(scope.evidence_ids)
        self._messages.delete_many(scope.message_ids)
        self._escalations.delete_many(scope.escalation_ids)
        self._cases.delete_many(scope.case_ids)
        self._volunteers.delete_many(scope.volunteer_ids)
        self._contacts.delete_many(scope.contact_ids)
        self._dams.delete_many(scope.dam_ids)

    def seed(self, scenario: Scenario) -> None:
        self._volunteers.put_many({v.id: v for v in scenario.spec.volunteers})
        self._contacts.put_many({c.id: c for c in scenario.spec.contacts})
        self._dams.put_many({dam.id: dam for dam in scenario.dams})


def matching[T](collection: Collection[T], field: str, values: list[str]) -> list[T]:
    found: list[T] = []
    for start in range(0, len(values), IN_QUERY_LIMIT):
        chunk = values[start : start + IN_QUERY_LIMIT]
        found.extend(collection.where(Filter(field, "in", chunk)))
    return found


def children[T](collection: Collection[T], case_ids: list[str]) -> list[T]:
    return matching(collection, "case_id", case_ids)


def caseless_messages(
    collection: Collection[Message], people: list[str]
) -> list[Message]:
    return [
        message
        for message in matching(collection, "to_id", people)
        if message.case_id is None
    ]


class RankingRepository:
    def __init__(
        self,
        cells_for: Callable[[str], Collection[RankedCell]],
        week_cells_for: Callable[[str, str], Collection[RankedCell]] | None = None,
    ):
        self._cells_for = cells_for
        self._week_cells_for = week_cells_for

    def top(self, region: str, limit: int) -> list[RankedCell]:
        return self._cells_for(region).where(Filter("rank", "<=", limit))

    def top_in_week(self, region: str, week: str, limit: int) -> list[RankedCell]:
        if self._week_cells_for is None:
            return []
        ranked = self._week_cells_for(region, week).where(Filter("rank", "<=", limit))
        return sorted(ranked, key=lambda cell: cell.rank)

    def cell(self, region: str, cell_id: str) -> RankedCell | None:
        return self._cells_for(region).get(cell_id)

    def set_explanation(
        self, region: str, cell_id: str, explanation: RankExplanation
    ) -> None:
        self._cells_for(region).update(
            cell_id, {"explanation": explanation.model_dump(mode="json")}
        )


class RankedDamRepository:
    def __init__(
        self,
        dams_for: Callable[[str], Collection[RankedDam]],
        week_dams_for: Callable[[str, str], Collection[RankedDam]] | None = None,
    ):
        self._dams_for = dams_for
        self._week_dams_for = week_dams_for

    def top_in_week(self, region: str, week: str, limit: int) -> list[RankedDam]:
        if self._week_dams_for is None:
            return []
        ranked = self._week_dams_for(region, week).where(Filter("rank", "<=", limit))
        return sorted(ranked, key=lambda dam: dam.rank)

    def top(self, region: str, limit: int) -> list[RankedDam]:
        ranked = self._dams_for(region).where(Filter("rank", "<=", limit))
        return sorted(ranked, key=lambda dam: dam.rank)

    def in_cell(self, region: str, cell_id: str) -> list[RankedDam]:
        found = self._dams_for(region).where(Filter("cell_id", "==", cell_id))
        return sorted(found, key=lambda dam: dam.rank)


class RankingRunRepository:
    def __init__(self, runs_for: Callable[[str], Collection[RankingRun]]):
        self._runs_for = runs_for

    def get(self, region: str, week: str) -> RankingRun | None:
        return self._runs_for(region).get(week)


class BulletinRepository:
    def __init__(self, bulletins: Collection[Bulletin]):
        self._bulletins = bulletins

    def get(self, bulletin_id: str) -> Bulletin | None:
        return self._bulletins.get(bulletin_id)

    def put(self, bulletin: Bulletin) -> None:
        self._bulletins.put(bulletin.id, bulletin)


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

    def for_case(self, case_id: str) -> list[AgentRun]:
        runs = self._runs_for(case_id).where()
        return sorted(runs, key=lambda run: (run.started_at, run.id))


@dataclass(frozen=True)
class AgentRepositories:
    rankings: RankingRepository
    ranked_dams: RankedDamRepository
    evidence: EvidenceRepository
    volunteers: VolunteerRepository
    dams: DamRepository
    agent_runs: AgentRunRepository
    ranking_runs: RankingRunRepository


def build_agent_repositories(db: firestore.Client) -> AgentRepositories:
    return AgentRepositories(
        rankings=RankingRepository(
            lambda region: FirestoreCollection(
                db, f"rankings/{region}/cells", RankedCell
            ),
            lambda region, week: FirestoreCollection(
                db, f"rankings/{region}/weeks/{week}/cells", RankedCell
            ),
        ),
        evidence=EvidenceRepository(FirestoreCollection(db, "evidence", Evidence)),
        ranked_dams=RankedDamRepository(
            lambda region: FirestoreCollection(
                db, f"rankings/{region}/dams", RankedDam
            ),
            lambda region, week: FirestoreCollection(
                db, f"rankings/{region}/weeks/{week}/dams", RankedDam
            ),
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
        ranking_runs=RankingRunRepository(
            lambda region: FirestoreCollection(
                db, f"rankings/{region}/weeks", RankingRun
            )
        ),
    )
