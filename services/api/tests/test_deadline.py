from datetime import UTC, datetime, timedelta

import pytest

from adapters.firestore_repos import (
    CASES,
    TASKS,
    CaseRepository,
    CaseworkStore,
    TaskRepository,
)
from casework.deadline import DeadlineHandler, OverduePublishFailed, SweptTask
from contracts import Case, ClockSettings, Task
from domain.clock import Clock
from tests.fakes import (
    InMemoryClockStore,
    InMemoryCollection,
    InMemoryTransactor,
    make_case,
    make_task,
)

NOW = datetime(2026, 10, 17, 12, 0, tzinfo=UTC)
PAST = NOW - timedelta(hours=1)
FUTURE = NOW + timedelta(hours=1)


class FakePublisher:
    def __init__(self, error=None):
        self.error = error
        self.published = []

    def publish(self, topic, event):
        if self.error is not None:
            raise self.error
        self.published.append((topic, event))
        return "m1"


def due_task(**overrides):
    return make_task(**{"id": "t1", "case_id": "c1", "deadline_at": PAST, **overrides})


class CaseMovesAfterRead:
    def __init__(self, cases):
        self._cases = cases

    def get(self, case_id):
        case = self._cases.get(case_id)
        self._cases.update(case_id, {"status": "reviewing"})
        return case


class World:
    def __init__(self, *, tasks=None, cases=None, publisher=None, case_reader=None):
        self.tasks = InMemoryCollection(Task)
        for task in tasks if tasks is not None else [due_task()]:
            self.tasks.put(task.id, task)
        self.cases = InMemoryCollection(Case)
        for case in cases if cases is not None else [make_case(status="assigned")]:
            self.cases.put(case.id, case)
        self.publisher = publisher or FakePublisher()
        ids = iter(f"ev-{n}" for n in range(100))
        self.handler = DeadlineHandler(
            tasks=TaskRepository(self.tasks),
            cases=(case_reader or CaseRepository)(self.cases),
            casework=CaseworkStore(
                InMemoryTransactor({TASKS: self.tasks, CASES: self.cases})
            ),
            publisher=self.publisher,
            clock=Clock(
                InMemoryClockStore(ClockSettings(offset_seconds=0, updated_by="t")),
                lambda: NOW,
            ),
            new_id=lambda: next(ids),
        )


def test_a_due_open_task_goes_overdue_with_its_assigned_case_and_publishes():
    world = World()

    outcome = world.handler.handle_deadline("t1")

    assert outcome == "case_overdue"
    assert world.tasks.get("t1").status == "overdue"
    assert world.cases.get("c1").status == "overdue"
    [(topic, event)] = world.publisher.published
    assert topic == "task.overdue"
    assert event.type == "task.overdue"
    assert event.id == "ev-0"
    assert event.occurred_at == NOW
    assert event.region == "riau"
    assert event.payload.model_dump() == {
        "task_id": "t1",
        "case_id": "c1",
        "attempt": 1,
    }


@pytest.mark.parametrize("example", [True, False])
def test_the_event_carries_the_example_flag_of_the_case(example):
    world = World(cases=[make_case(status="assigned", example=example)])

    world.handler.handle_deadline("t1")

    [(_, event)] = world.publisher.published
    assert event.example is example


def test_the_event_carries_the_attempt_of_the_task():
    world = World(tasks=[due_task(attempt=2)])

    world.handler.handle_deadline("t1")

    [(_, event)] = world.publisher.published
    assert event.payload.attempt == 2


def test_a_deadline_exactly_now_is_due():
    world = World(tasks=[due_task(deadline_at=NOW)])

    assert world.handler.handle_deadline("t1") == "case_overdue"


def test_a_task_not_yet_due_is_left_open():
    world = World(tasks=[due_task(deadline_at=FUTURE)])

    assert world.handler.handle_deadline("t1") == "not_due"
    assert world.tasks.get("t1").status == "open"
    assert world.cases.get("c1").status == "assigned"
    assert world.publisher.published == []


@pytest.mark.parametrize("status", ["done", "reassigned", "cancelled"])
def test_a_closed_task_is_skipped(status):
    world = World(tasks=[due_task(status=status)])

    assert world.handler.handle_deadline("t1") == "skipped"
    assert world.tasks.get("t1").status == status
    assert world.publisher.published == []


def test_an_unknown_task_is_skipped():
    world = World()

    assert world.handler.handle_deadline("nope") == "skipped"
    assert world.publisher.published == []


@pytest.mark.parametrize("status", ["reviewing", "escalated", "monitoring"])
def test_a_case_the_machine_cannot_move_keeps_its_status_and_no_event_is_sent(status):
    world = World(cases=[make_case(status=status)])

    outcome = world.handler.handle_deadline("t1")

    assert outcome == "task_overdue"
    assert world.tasks.get("t1").status == "overdue"
    assert world.cases.get("c1").status == status
    assert world.publisher.published == []


def test_a_task_whose_case_is_gone_goes_overdue_alone():
    world = World(cases=[])

    assert world.handler.handle_deadline("t1") == "task_overdue"
    assert world.tasks.get("t1").status == "overdue"
    assert world.publisher.published == []


def test_a_second_call_after_the_agent_acted_does_nothing():
    world = World()
    world.handler.handle_deadline("t1")
    world.cases.update("c1", {"status": "escalated"})

    assert world.handler.handle_deadline("t1") == "skipped"
    assert len(world.publisher.published) == 1


def test_a_publish_failure_raises_and_a_retry_publishes_once():
    publisher = FakePublisher(RuntimeError("down"))
    world = World(publisher=publisher)

    with pytest.raises(OverduePublishFailed):
        world.handler.handle_deadline("t1")
    assert world.tasks.get("t1").status == "overdue"
    assert world.cases.get("c1").status == "overdue"
    publisher.error = None

    assert world.handler.handle_deadline("t1") == "case_overdue"
    assert len(publisher.published) == 1


def test_a_case_that_moved_between_read_and_commit_leaves_the_task_open():
    world = World(case_reader=CaseMovesAfterRead)

    assert world.handler.handle_deadline("t1") == "skipped"
    assert world.tasks.get("t1").status == "open"
    assert world.publisher.published == []


def test_a_real_case_follows_the_same_path():
    world = World(cases=[make_case(status="assigned", example=False)])

    assert world.handler.handle_deadline("t1") == "case_overdue"
    assert world.cases.get("c1").status == "overdue"


def test_the_sweep_handles_every_due_open_task_and_survives_a_failure():
    publisher = FakePublisher(RuntimeError("down"))
    world = World(
        tasks=[
            due_task(id="t1", case_id="c1"),
            due_task(id="t2", case_id="c2"),
            due_task(id="t3", case_id="c1", deadline_at=FUTURE),
            due_task(id="t4", case_id="c1", status="done"),
        ],
        cases=[
            make_case(id="c1", status="assigned"),
            make_case(id="c2", status="reviewing"),
        ],
        publisher=publisher,
    )

    swept = world.handler.sweep_due()

    assert sorted(swept, key=lambda item: item.task_id) == [
        SweptTask("t1", None),
        SweptTask("t2", "task_overdue"),
    ]
    assert world.tasks.get("t2").status == "overdue"
    assert world.tasks.get("t3").status == "open"
    assert world.tasks.get("t4").status == "done"


def test_a_sweep_with_nothing_due_is_empty():
    world = World(tasks=[due_task(deadline_at=FUTURE)])

    assert world.handler.sweep_due() == []
