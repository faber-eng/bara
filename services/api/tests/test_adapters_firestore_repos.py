from datetime import UTC, datetime, timedelta

from adapters.firestore_repos import (
    CaseRepository,
    EventLog,
    FirestoreClockStore,
    TaskRepository,
)
from adapters.store import FirestoreCollection
from contracts import Case, ClockSettings, ProcessedEvent, Task
from tests.fakes import (
    InMemoryCollection,
    StubFirestoreClient,
    make_case,
    make_task,
)

NOW = datetime(2026, 10, 20, 12, 0, tzinfo=UTC)


def make_task_repo(*tasks):
    collection = InMemoryCollection(Task)
    for task in tasks:
        collection.put(task.id, task)
    return TaskRepository(collection)


def test_due_returns_open_tasks_with_deadline_at_or_before_now():
    past = make_task(id="past", deadline_at=NOW - timedelta(hours=1))
    exact = make_task(id="exact", deadline_at=NOW)
    future = make_task(id="future", deadline_at=NOW + timedelta(hours=1))

    due = make_task_repo(past, exact, future).due(NOW)

    assert sorted(task.id for task in due) == ["exact", "past"]


def test_due_skips_tasks_that_are_not_open():
    done = make_task(id="done", status="done", deadline_at=NOW - timedelta(hours=1))
    overdue = make_task(id="od", status="overdue", deadline_at=NOW - timedelta(hours=1))

    assert make_task_repo(done, overdue).due(NOW) == []


def test_due_with_no_tasks_is_empty():
    assert make_task_repo().due(NOW) == []


def make_case_repo(*cases):
    collection = InMemoryCollection(Case)
    for case in cases:
        collection.put(case.id, case)
    return CaseRepository(collection)


def test_open_for_dam_finds_the_case_that_is_not_closed():
    live = make_case(id="live", dam_id="dam-1", status="assigned")

    assert make_case_repo(live).open_for_dam("dam-1") == live


def test_open_for_dam_ignores_closed_cases_and_other_dams():
    closed = make_case(id="closed", dam_id="dam-1", status="closed")
    other = make_case(id="other", dam_id="dam-2", status="open")

    assert make_case_repo(closed, other).open_for_dam("dam-1") is None


def test_event_log_claims_a_message_once():
    log = EventLog(InMemoryCollection(ProcessedEvent), lambda: NOW)

    first = log.claim("m1", "hotspot.detected")
    second = log.claim("m1", "hotspot.detected")

    assert (first, second) == (True, False)


def test_event_log_records_type_and_time():
    collection = InMemoryCollection(ProcessedEvent)

    EventLog(collection, lambda: NOW).claim("m1", "fire.quiet")

    assert collection.get("m1") == ProcessedEvent(
        id="m1", type="fire.quiet", processed_at=NOW
    )


def test_event_log_keeps_different_messages_apart():
    log = EventLog(InMemoryCollection(ProcessedEvent), lambda: NOW)

    assert log.claim("m1", "fire.quiet") is True
    assert log.claim("m2", "fire.quiet") is True


def test_clock_store_round_trips_settings_under_the_clock_document():
    collection = InMemoryCollection(ClockSettings)
    store = FirestoreClockStore(collection)
    assert store.get() is None

    settings = ClockSettings(offset_seconds=3600, updated_by="judge")
    store.put(settings)

    assert store.get() == settings
    assert collection.get("clock") == settings


def test_clock_store_add_seconds_creates_then_accumulates():
    collection = InMemoryCollection(ClockSettings)
    store = FirestoreClockStore(collection)

    store.add_seconds(3600, "a")
    store.add_seconds(60, "b")

    assert store.get() == ClockSettings(offset_seconds=3660, updated_by="b")


def test_clock_store_add_seconds_uses_a_firestore_increment():
    client = StubFirestoreClient()
    store = FirestoreClockStore(FirestoreCollection(client, "settings", ClockSettings))

    store.add_seconds(100, "a")
    store.add_seconds(50, "b")

    assert client.stores["settings"]["clock"] == {
        "offset_seconds": 150,
        "updated_by": "b",
    }


def test_volunteer_create_if_absent_creates_once_and_keeps_the_first():
    from adapters.firestore_repos import VolunteerRepository
    from contracts import Volunteer
    from tests.fakes import make_volunteer

    repo = VolunteerRepository(InMemoryCollection(Volunteer))

    assert repo.create_if_absent(make_volunteer(id="u1", name="First")) is True
    assert repo.create_if_absent(make_volunteer(id="u1", name="Second")) is False
    assert repo.get("u1").name == "First"
