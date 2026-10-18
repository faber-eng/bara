from datetime import UTC, datetime

import pytest

from adapters.firestore_repos import CaseRepository, TaskRepository, VolunteerRepository
from casework.assignment import AssignmentRejected
from casework.messenger import MessengerFailed
from contracts import (
    Case,
    FireQuiet,
    FireQuietEvent,
    GeoPoint,
    QuietCell,
    Task,
    TopFeature,
    Volunteer,
)
from events import MalformedPush
from fire_events import FireQuietHandler, RecheckIncomplete
from tests.fakes import (
    InMemoryCollection,
    make_drying_ranked_event,
    make_task,
    make_volunteer,
)

NOW = datetime(2026, 7, 30, 1, 0, tzinfo=UTC)
CENTROIDS = {
    "c-a": GeoPoint(lat=0.55, lon=102.15),
    "c-b": GeoPoint(lat=0.56, lon=102.16),
    "c-c": GeoPoint(lat=0.50, lon=102.30),
}


class FixedClock:
    def now(self):
        return NOW


class FakeCells:
    def centroid(self, cell_id):
        return CENTROIDS.get(cell_id)


class FakeAssigner:
    def __init__(self, cases, tasks=None, fail_for=()):
        self.requests = []
        self._cases = cases
        self._tasks = tasks
        self._fail_for = set(fail_for)

    async def assign(self, request):
        self.requests.append(request)
        if request.target_cell_id in self._fail_for:
            raise AssignmentRejected("refused")
        case = self._cases.get(request.case_id)
        self._cases.put(case.id, case.model_copy(update={"status": "assigned"}))
        if self._tasks is not None:
            task = make_task(
                id=f"t-{request.target_cell_id}",
                case_id=case.id,
                assignee_id=request.assignee_id,
                target=CENTROIDS[request.target_cell_id],
            )
            self._tasks.put(task.id, task)


def quiet_event(**overrides):
    cells = [
        QuietCell(
            cell_id=cell_id,
            p_reignite=p,
            top_features=[TopFeature(feature="drying_score", attribution=0.4)],
        )
        for cell_id, p in (("c-b", 0.74), ("c-a", 0.82), ("c-c", 0.68))
    ]
    fields = {
        "id": "evt-9",
        "occurred_at": NOW,
        "region": "riau",
        "example": True,
        "type": "fire.quiet",
        "payload": FireQuiet(event_id="fire-1", cells=cells),
    }
    return FireQuietEvent(**{**fields, **overrides})


class World:
    def __init__(self, patrols=None, fail_for=(), spots=3, hours=48, open_tasks=()):
        self.case_store = InMemoryCollection(Case)
        people = InMemoryCollection(Volunteer)
        for person in patrols if patrols is not None else default_patrols():
            people.put(person.id, person)
        self.cases = CaseRepository(self.case_store)
        self.task_store = InMemoryCollection(Task)
        for task in open_tasks:
            self.task_store.put(task.id, task)
        self.assigner = FakeAssigner(self.case_store, self.task_store, fail_for)
        self.handler = FireQuietHandler(
            cases=self.cases,
            tasks=TaskRepository(self.task_store),
            volunteers=VolunteerRepository(people),
            cells=FakeCells(),
            assigner=self.assigner,
            clock=FixedClock(),
            spots=spots,
            recheck_hours=hours,
            region="riau",
        )

    def deliver(self, event=None, message_id="m-1"):
        self.handler.handle(message_id, event or quiet_event())

    def all_cases(self):
        return self.case_store.where()


def default_patrols():
    return [
        make_volunteer(
            id="near-a",
            role="patrol",
            example=True,
            home=GeoPoint(lat=0.551, lon=102.151),
        ),
        make_volunteer(
            id="near-c",
            role="patrol",
            example=True,
            home=GeoPoint(lat=0.501, lon=102.301),
        ),
        make_volunteer(id="vol-1", role="volunteer", example=True),
    ]


def test_one_reignition_case_opens_on_the_most_likely_cell():
    world = World()

    world.deliver()

    case = world.all_cases()[0]
    assert len(world.all_cases()) == 1
    assert case.type == "reignition"
    assert case.cell_id == "c-a"
    assert case.dam_id is None
    assert case.event_id == "fire-1"
    assert case.risk.p_reignite == 0.82
    assert case.risk.drying_score is None
    assert case.region == "riau"
    assert case.opened_at == NOW
    assert case.example is True


def test_each_of_the_three_cells_gets_a_patrol_recheck_due_in_48_hours():
    world = World()

    world.deliver()

    requests = world.assigner.requests
    assert [r.target_cell_id for r in requests] == ["c-a", "c-b", "c-c"]
    assert {r.task_type for r in requests} == {"patrol_recheck"}
    assert {r.deadline_hours for r in requests} == {48}
    assert {r.case_id for r in requests} == {world.all_cases()[0].id}
    assert {r.reassigns_overdue for r in requests} == {False}
    assert all("c-" in r.instructions_hint for r in requests)


def test_each_cell_goes_to_the_nearest_available_patrol():
    world = World()

    world.deliver()

    by_cell = {r.target_cell_id: r.assignee_id for r in world.assigner.requests}
    assert by_cell == {"c-a": "near-a", "c-b": "near-a", "c-c": "near-c"}


def test_a_real_patrol_is_used_when_it_is_the_nearest():
    patrols = default_patrols() + [
        make_volunteer(
            id="real",
            role="patrol",
            example=False,
            home=GeoPoint(lat=0.5501, lon=102.1501),
        )
    ]
    world = World(patrols=patrols)

    world.deliver()

    assert world.assigner.requests[0].assignee_id == "real"


def test_an_unavailable_patrol_is_not_used():
    patrols = [
        make_volunteer(id="away", role="patrol", available=False),
        make_volunteer(id="here", role="patrol", home=GeoPoint(lat=0.1, lon=102.0)),
    ]
    world = World(patrols=patrols)

    world.deliver()

    assert {r.assignee_id for r in world.assigner.requests} == {"here"}


def test_only_the_configured_number_of_cells_is_scheduled():
    world = World(spots=2)

    world.deliver()

    assert [r.target_cell_id for r in world.assigner.requests] == ["c-a", "c-b"]


def test_with_no_patrol_the_case_still_opens_and_nothing_is_scheduled(caplog):
    world = World(patrols=[])

    world.deliver()

    assert len(world.all_cases()) == 1
    assert world.assigner.requests == []
    assert any(
        getattr(r, "fields", {}).get("event") == "recheck_no_patrol"
        for r in caplog.records
    )


def test_a_refused_assignment_does_not_stop_the_other_cells_and_is_not_retried(caplog):
    world = World(fail_for={"c-b"})

    world.deliver()

    assert [r.target_cell_id for r in world.assigner.requests] == ["c-a", "c-b", "c-c"]
    assert any(
        getattr(r, "fields", {}).get("event") == "recheck_not_scheduled"
        for r in caplog.records
    )


def test_a_messenger_failure_finishes_the_other_cells_then_raises_for_a_retry():
    class Failing(FakeAssigner):
        async def assign(self, request):
            if request.target_cell_id == "c-a":
                self.requests.append(request)
                raise MessengerFailed("down")
            await super().assign(request)

    world = World()
    failing = Failing(world.case_store, world.task_store)
    world.handler._assigner = failing

    with pytest.raises(RecheckIncomplete):
        world.deliver()

    assert [r.target_cell_id for r in failing.requests] == ["c-a", "c-b", "c-c"]
    assert sorted(t.id for t in world.task_store.where()) == ["t-c-b", "t-c-c"]


def test_the_retry_schedules_only_the_cells_that_have_no_task():
    class FailOnce(FakeAssigner):
        failed = False

        async def assign(self, request):
            if request.target_cell_id == "c-b" and not self.failed:
                self.failed = True
                raise RuntimeError("network")
            await super().assign(request)

    world = World()
    world.handler._assigner = FailOnce(world.case_store, world.task_store)

    with pytest.raises(RecheckIncomplete):
        world.deliver()
    world.deliver(message_id="m-1-retry")

    assert len(world.all_cases()) == 1
    assert sorted(t.id for t in world.task_store.where()) == ["t-c-a", "t-c-b", "t-c-c"]
    retry_cells = [r.target_cell_id for r in world.handler._assigner.requests]
    assert retry_cells == ["c-a", "c-c", "c-b"]


def test_the_hint_names_the_configured_hours():
    world = World(hours=24)

    world.deliver()

    assert all("24 hours" in r.instructions_hint for r in world.assigner.requests)


@pytest.mark.parametrize("example", [True, False])
def test_the_case_copies_the_example_flag(example):
    world = World()

    world.deliver(quiet_event(example=example))

    assert world.all_cases()[0].example is example


def test_the_same_fire_event_opens_one_case_even_from_a_second_message():
    world = World()

    world.deliver(message_id="m-1")
    world.deliver(quiet_event(id="evt-10"), message_id="m-2")

    assert len(world.all_cases()) == 1
    assert len(world.assigner.requests) == 3


def test_an_event_with_no_cells_opens_nothing():
    world = World()
    empty = quiet_event(payload=FireQuiet(event_id="fire-1", cells=[]))

    world.deliver(empty)

    assert world.all_cases() == []


def test_another_event_type_is_malformed():
    world = World()

    with pytest.raises(MalformedPush):
        world.handler.handle("m-1", make_drying_ranked_event())


def test_the_cells_after_the_first_are_scheduled_together():
    import asyncio
    import time

    class Slow(FakeAssigner):
        active = 0
        peak = 0

        async def assign(self, request):
            Slow.active += 1
            Slow.peak = max(Slow.peak, Slow.active)
            await asyncio.sleep(0.2)
            Slow.active -= 1
            await super().assign(request)

    world = World()
    world.handler._assigner = Slow(world.case_store, world.task_store)

    started = time.perf_counter()
    world.deliver()
    elapsed = time.perf_counter() - started

    assert Slow.peak == 2
    assert len(world.task_store.where()) == 3
    assert elapsed < 0.55


def test_a_fire_of_a_region_without_the_full_flow_opens_no_case_and_no_task():
    world = World()
    event = quiet_event(region="congo_cuvette")

    world.deliver(event)

    assert world.all_cases() == []
    assert world.assigner.requests == []


def test_at_most_four_volunteer_messages_are_composed_at_once():
    import asyncio
    import time

    extra = {f"c-x{index}": CENTROIDS["c-c"] for index in range(8)}
    CENTROIDS.update(extra)

    class Slow(FakeAssigner):
        active = 0
        peak = 0

        async def assign(self, request):
            Slow.active += 1
            Slow.peak = max(Slow.peak, Slow.active)
            await asyncio.sleep(0.1)
            Slow.active -= 1
            await super().assign(request)

    cells = [
        QuietCell(
            cell_id=cell_id,
            p_reignite=0.9 - index / 100,
            top_features=[TopFeature(feature="drying_score", attribution=0.4)],
        )
        for index, cell_id in enumerate(["c-a", *extra])
    ]
    world = World(spots=9)
    world.handler._assigner = Slow(world.case_store, world.task_store)

    started = time.perf_counter()
    world.deliver(quiet_event(payload=FireQuiet(event_id="fire-1", cells=cells)))
    elapsed = time.perf_counter() - started
    for cell_id in extra:
        CENTROIDS.pop(cell_id)

    assert Slow.peak == 4
    assert len(world.task_store.where()) == 9
    assert elapsed < 0.1 * 3 + 0.25


def test_a_patrol_with_an_open_task_is_used_after_a_free_one():
    patrols = [
        make_volunteer(id="busy", role="patrol", home=GeoPoint(lat=0.551, lon=102.151)),
        make_volunteer(id="free", role="patrol", home=GeoPoint(lat=0.1, lon=102.0)),
    ]
    held = make_task(id="held", assignee_id="busy", status="open")
    world = World(patrols=patrols, spots=1, open_tasks=[held])

    world.deliver()

    assert {r.assignee_id for r in world.assigner.requests} == {"free"}
