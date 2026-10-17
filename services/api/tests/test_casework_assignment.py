import asyncio
import logging
from datetime import UTC, datetime, timedelta

import pytest

from adapters.cells import CENTROID_SQL, CellRepository
from adapters.channels import WebChannel
from adapters.firestore_repos import (
    CASES,
    MESSAGES,
    TASKS,
    CaseRepository,
    CaseworkStore,
    DamRepository,
    TaskRepository,
    VolunteerRepository,
)
from casework.assignment import (
    AssignmentRejected,
    AssignmentRequest,
    TaskAssigner,
)
from casework.messenger import ComposedMessage, MessengerFailed
from contracts import (
    Case,
    ClockSettings,
    Dam,
    GeoPoint,
    Message,
    Task,
    Volunteer,
)
from domain.clock import Clock
from tests.fakes import (
    FakeWarehouse,
    InMemoryClockStore,
    InMemoryCollection,
    InMemoryTransactor,
    make_case,
    make_dam,
    make_task,
    make_volunteer,
)

REAL_NOW = datetime(2026, 10, 17, 12, 0, tzinfo=UTC)
OFFSET = -3600
SIM_NOW = REAL_NOW + timedelta(seconds=OFFSET)
DAM_POINT = GeoPoint(lat=0.61, lon=102.21)
CENTROID = {"lat": 0.55, "lon": 102.3}
DEFAULTS = {"dam_check": 72, "dam_repair": 168, "patrol_recheck": 24}


class FakeMessenger:
    def __init__(self, outcome=None, during=None):
        self.outcome = outcome or ComposedMessage(
            text="Cek sekat.", text_en="Check the dam.", lang="id"
        )
        self.during = during
        self.briefs = []

    async def compose(self, brief):
        self.briefs.append(brief)
        if self.during is not None:
            self.during()
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome


class FakeScheduler:
    def __init__(self, error: Exception | None = None):
        self.error = error
        self.scheduled = []

    def schedule(self, task_id, at):
        if self.error is not None:
            raise self.error
        self.scheduled.append((task_id, at))
        return f"queues/q/tasks/{task_id}-{int(at.timestamp())}"


def collection_with(model, items, key):
    collection = InMemoryCollection(model)
    for item in items:
        collection.put(getattr(item, key), item)
    return collection


class World:
    def __init__(
        self,
        *,
        case=None,
        volunteers=None,
        messenger=None,
        scheduler="default",
        tasks=(),
        dams=None,
        timezones=None,
        centroids=(CENTROID,),
        commit_error=None,
    ):
        self.cases = collection_with(Case, [case or make_case(dam_id="dam-7")], "id")
        self.tasks = collection_with(Task, list(tasks), "id")
        self.messages = InMemoryCollection(Message)
        self.transactor = InMemoryTransactor(
            {CASES: self.cases, TASKS: self.tasks, MESSAGES: self.messages},
            error=commit_error,
        )
        self.volunteers = collection_with(
            Volunteer, volunteers or [make_volunteer(id="v1", language="id")], "id"
        )
        self.messenger = messenger or FakeMessenger()
        self.scheduler = FakeScheduler() if scheduler == "default" else scheduler
        clock = Clock(
            InMemoryClockStore(ClockSettings(offset_seconds=OFFSET, updated_by="t")),
            lambda: REAL_NOW,
        )
        ids = iter(["task-1", "msg-1", "task-2", "msg-2"])
        new_id = lambda: next(ids)
        self.assigner = TaskAssigner(
            cases=CaseRepository(self.cases),
            volunteers=VolunteerRepository(self.volunteers),
            dams=DamRepository(
                collection_with(
                    Dam,
                    [make_dam(id="dam-7", point=DAM_POINT)] if dams is None else dams,
                    "id",
                )
            ),
            cells=CellRepository(FakeWarehouse({CENTROID_SQL: list(centroids)})),
            tasks=TaskRepository(self.tasks),
            casework=CaseworkStore(self.transactor),
            channel=WebChannel(clock, new_id),
            messenger=self.messenger,
            scheduler=self.scheduler,
            clock=clock,
            default_deadline_hours=DEFAULTS,
            timezones={"riau": "Asia/Jakarta"} if timezones is None else timezones,
            new_id=new_id,
        )

    def assign(self, **overrides):
        fields = {
            "case_id": "c1",
            "assignee_id": "v1",
            "task_type": "dam_check",
            "instructions_hint": "Check the left side.",
            "deadline_hours": None,
        }
        request = AssignmentRequest(**{**fields, **overrides})
        return asyncio.run(self.assigner.assign(request))

    def nothing_written(self) -> bool:
        return self.tasks.where() == [] and self.messages.where() == []


def test_one_call_creates_the_task_the_message_and_the_cloud_task():
    world = World()

    assignment = world.assign()

    task = world.tasks.get("task-1")
    deadline = SIM_NOW + timedelta(hours=72)
    assert task == assignment.task
    assert task.case_id == "c1"
    assert task.type == "dam_check"
    assert task.assignee_id == "v1"
    assert task.target == DAM_POINT
    assert task.deadline_at == deadline
    assert task.status == "open"
    assert task.attempt == 1
    assert task.created_at == SIM_NOW
    assert task.done_at is None
    real_at = deadline - timedelta(seconds=OFFSET)
    assert world.scheduler.scheduled == [("task-1", real_at)]
    assert task.cloud_task_name == f"queues/q/tasks/task-1-{int(real_at.timestamp())}"
    message = world.messages.get("msg-1")
    assert message == assignment.message
    assert message.to_id == "v1"
    assert message.case_id == "c1"
    assert message.lang == "id"
    assert message.text == "Cek sekat."
    assert world.cases.get("c1").status == "assigned"


def test_the_messenger_gets_the_volunteer_language_place_and_local_deadline():
    world = World(volunteers=[make_volunteer(id="v1", language="en")])

    world.assign(deadline_hours=48)

    sent = world.messenger.briefs[0]
    assert sent.language == "en"
    assert sent.task_type == "dam_check"
    assert sent.place == "dam-7"
    assert sent.target == DAM_POINT
    assert sent.deadline_local == "Monday 19 October 2026, 18:00 WIB"
    assert sent.hint == "Check the left side."


def test_a_requested_deadline_is_used():
    world = World()

    assignment = world.assign(deadline_hours=24)

    assert assignment.task.deadline_at == SIM_NOW + timedelta(hours=24)


def test_a_case_without_a_dam_targets_the_cell_centroid():
    world = World(case=make_case(dam_id=None))

    assignment = world.assign()

    assert assignment.task.target == GeoPoint(**CENTROID)
    assert world.messenger.briefs[0].place is None


def test_an_assigned_case_stays_assigned_and_gets_a_second_task():
    world = World(case=make_case(dam_id="dam-7", status="assigned"))

    world.assign()

    assert world.cases.get("c1").status == "assigned"
    assert world.tasks.get("task-1") is not None


@pytest.mark.parametrize(
    ("overrides", "reason"),
    [
        ({"case_id": "nope"}, "unknown case"),
        ({"assignee_id": "nobody"}, "unknown person"),
        ({"deadline_hours": 0}, "deadline"),
    ],
)
def test_a_bad_request_is_rejected_and_writes_nothing(overrides, reason):
    world = World()

    with pytest.raises(AssignmentRejected, match=reason):
        world.assign(**overrides)

    assert world.nothing_written()
    assert world.messenger.briefs == []


def test_an_unavailable_person_is_rejected():
    world = World(volunteers=[make_volunteer(id="v1", available=False)])

    with pytest.raises(AssignmentRejected, match="not available"):
        world.assign()

    assert world.nothing_written()


@pytest.mark.parametrize("status", ["escalated", "closed", "resolved_pending_human"])
def test_a_case_that_cannot_be_assigned_is_rejected(status):
    world = World(case=make_case(dam_id="dam-7", status=status))

    with pytest.raises(AssignmentRejected, match=status):
        world.assign()

    assert world.nothing_written()
    assert world.cases.get("c1").status == status


def test_a_messenger_failure_writes_nothing():
    world = World(messenger=FakeMessenger(MessengerFailed("too many sentences")))

    with pytest.raises(MessengerFailed):
        world.assign()

    assert world.nothing_written()
    assert world.scheduler.scheduled == []
    assert world.cases.get("c1").status == "open"


def test_without_a_scheduler_the_task_is_kept_and_a_warning_logged(caplog):
    world = World(scheduler=None)

    with caplog.at_level(logging.WARNING):
        assignment = world.assign()

    assert world.tasks.get("task-1").cloud_task_name is None
    assert assignment.task.cloud_task_name is None
    assert any(
        getattr(r, "fields", {}).get("event") == "deadline_not_scheduled"
        for r in caplog.records
    )
    assert world.cases.get("c1").status == "assigned"


def test_a_scheduler_error_keeps_the_task_and_logs_an_error(caplog):
    world = World(scheduler=FakeScheduler(RuntimeError("tasks down")))

    with caplog.at_level(logging.ERROR):
        world.assign()

    assert world.tasks.get("task-1").cloud_task_name is None
    errors = [r for r in caplog.records if r.levelno == logging.ERROR]
    assert errors[0].fields["event"] == "deadline_schedule_failed"
    assert errors[0].fields["task_id"] == "task-1"
    assert world.messages.get("msg-1") is not None


def test_a_failed_commit_writes_nothing_and_schedules_nothing():
    world = World(commit_error=RuntimeError("firestore down"))

    with pytest.raises(RuntimeError):
        world.assign()

    assert world.nothing_written()
    assert world.scheduler.scheduled == []
    assert world.cases.get("c1").status == "open"


def test_a_case_changed_during_the_model_call_is_rejected_and_kept():
    holder = {}

    def escalate():
        holder["world"].cases.update("c1", {"status": "escalated"})

    world = World(messenger=FakeMessenger(during=escalate))
    holder["world"] = world

    with pytest.raises(AssignmentRejected, match="no longer open"):
        world.assign()

    assert world.nothing_written()
    assert world.scheduler.scheduled == []
    assert world.cases.get("c1").status == "escalated"


def test_a_task_on_an_overdue_case_is_the_next_attempt_and_reassigns_the_old_one():
    old = make_task(id="t-old", case_id="c1", status="overdue", attempt=1)
    world = World(case=make_case(dam_id="dam-7", status="overdue"), tasks=[old])

    assignment = world.assign()

    assert assignment.task.attempt == 2
    assert world.tasks.get("t-old").status == "reassigned"
    assert world.cases.get("c1").status == "assigned"


@pytest.mark.parametrize(
    ("world_overrides", "reason"),
    [
        ({"dams": []}, "unknown dam"),
        ({"timezones": {}}, "no timezone"),
    ],
)
def test_missing_reference_data_is_rejected_and_writes_nothing(world_overrides, reason):
    world = World(**world_overrides)

    with pytest.raises(AssignmentRejected, match=reason):
        world.assign()

    assert world.nothing_written()


def test_a_case_without_a_dam_in_an_unknown_cell_is_rejected():
    world = World(case=make_case(dam_id=None), centroids=())

    with pytest.raises(AssignmentRejected, match="unknown cell"):
        world.assign()

    assert world.nothing_written()
