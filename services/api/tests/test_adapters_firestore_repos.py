from datetime import UTC, datetime, timedelta

from adapters.firestore_repos import (
    CaseRepository,
    EventLog,
    FirestoreClockStore,
    TaskRepository,
    build_agent_repositories,
)
from adapters.store import FirestoreCollection
from contracts import Case, ClockSettings, ProcessedEvent, Task
from tests.fakes import (
    InMemoryCollection,
    StubFirestoreClient,
    make_agent_run,
    make_case,
    make_dam,
    make_ranked_cell,
    make_task,
    make_volunteer,
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


def test_volunteer_names_reads_the_display_names_of_the_ids_it_finds():
    from adapters.firestore_repos import VolunteerRepository
    from contracts import Volunteer
    from tests.fakes import make_volunteer

    collection = InMemoryCollection(Volunteer)
    for index in range(35):
        collection.put(f"u{index}", make_volunteer(id=f"u{index}", name=f"N{index}"))
    repo = VolunteerRepository(collection)

    wanted = [f"u{index}" for index in range(35)] + ["gone"]

    assert repo.names(wanted) == {f"u{index}": f"N{index}" for index in range(35)}
    assert repo.names([]) == {}


def test_get_returns_the_case_or_none():
    case = make_case(id="c1")
    repo = make_case_repo(case)

    assert repo.get("c1") == case
    assert repo.get("missing") is None


def firestore_repos():
    client = StubFirestoreClient()
    return client, build_agent_repositories(client)


def test_rankings_read_the_region_subcollection_up_to_the_limit():
    client, repos = firestore_repos()
    for rank in (1, 2, 3):
        cell = make_ranked_cell(cell_id=f"riau-{rank}", rank=rank)
        client.collection("rankings/riau/cells").document(cell.cell_id).set(
            cell.model_dump()
        )
    other = make_ranked_cell(cell_id="congo-1", region="congo_cuvette")
    client.collection("rankings/congo_cuvette/cells").document("congo-1").set(
        other.model_dump()
    )

    top = repos.rankings.top("riau", 2)

    assert sorted(cell.cell_id for cell in top) == ["riau-1", "riau-2"]


def test_available_volunteers_match_the_role_and_availability():
    client, repos = firestore_repos()
    people = [
        make_volunteer(id="ok"),
        make_volunteer(id="busy", available=False),
        make_volunteer(id="patrol", role="patrol"),
    ]
    for person in people:
        client.collection("volunteers").document(person.id).set(person.model_dump())

    assert [v.id for v in repos.volunteers.available("volunteer")] == ["ok"]


def test_dams_in_region_and_by_id():
    client, repos = firestore_repos()
    riau = make_dam(id="d1")
    congo = make_dam(id="d2", region="congo_cuvette")
    for dam in (riau, congo):
        client.collection("dams").document(dam.id).set(dam.model_dump())

    assert repos.dams.in_region("riau") == [riau]
    assert repos.dams.get("d2") == congo
    assert repos.dams.get("missing") is None


def test_agent_runs_are_stored_under_the_case():
    client, repos = firestore_repos()
    run = make_agent_run(id="r1")

    repos.agent_runs.save("c1", run)

    assert client.stores["cases/c1/agent_runs"]["r1"] == run.model_dump()


def test_ranked_dams_top_returns_the_best_ranks_in_order():
    from adapters.firestore_repos import RankedDamRepository
    from contracts import RankedDam
    from tests.fakes import make_ranked_dam

    collection = InMemoryCollection(RankedDam)
    for rank in (3, 1, 2, 4):
        collection.put(f"d{rank}", make_ranked_dam(dam_id=f"d{rank}", rank=rank))

    top = RankedDamRepository(lambda region: collection).top("riau", 3)

    assert [dam.dam_id for dam in top] == ["d1", "d2", "d3"]


def test_case_create_refuses_to_overwrite_an_existing_case():
    repo = make_case_repo()

    assert repo.create(make_case(id="c1", status="open")) is True
    assert repo.create(make_case(id="c1", status="closed")) is False
    assert repo.get("c1").status == "open"


def test_case_search_filters_by_region_and_status_newest_first():
    from datetime import UTC, datetime

    repo = make_case_repo(
        make_case(
            id="a",
            region="riau",
            status="open",
            opened_at=datetime(2026, 7, 1, tzinfo=UTC),
        ),
        make_case(
            id="b",
            region="riau",
            status="open",
            opened_at=datetime(2026, 7, 2, tzinfo=UTC),
        ),
        make_case(id="c", region="riau", status="closed"),
        make_case(id="d", region="other", status="open"),
    )

    assert [c.id for c in repo.search("riau", "open")] == ["b", "a"]
    assert {c.id for c in repo.search(None, None)} == {"a", "b", "c", "d"}
    assert {c.id for c in repo.search("riau", None)} == {"a", "b", "c"}


def test_mark_closed_updates_only_the_close_fields():
    from datetime import UTC, datetime

    repo = make_case_repo(make_case(id="a", status="human_review"))
    closed_at = datetime(2026, 7, 3, tzinfo=UTC)

    repo.mark_closed("a", "ops-1", closed_at)

    case = repo.get("a")
    assert (case.status, case.closed_by, case.closed_at) == (
        "closed",
        "ops-1",
        closed_at,
    )
    assert case.cell_id == "cell-1"


def test_tasks_and_evidence_load_for_many_cases_at_once():
    from adapters.firestore_repos import EvidenceRepository
    from contracts import Evidence
    from tests.fakes import make_evidence

    tasks = InMemoryCollection(Task)
    tasks.put("t1", make_task(id="t1", case_id="a"))
    tasks.put("t2", make_task(id="t2", case_id="b"))
    tasks.put("t3", make_task(id="t3", case_id="c"))
    evidence = InMemoryCollection(Evidence)
    evidence.put("e1", make_evidence(id="e1", case_id="a"))

    assert {t.id for t in TaskRepository(tasks).for_cases(["a", "b"])} == {"t1", "t2"}
    assert TaskRepository(tasks).for_cases([]) == []
    assert [e.id for e in EvidenceRepository(evidence).for_cases(["a"])] == ["e1"]


def test_ranking_runs_read_the_week_document_the_pipeline_writes():
    client, repos = firestore_repos()
    client.collection("rankings/riau/weeks").document("2026-W42").set(
        {
            "ran_at": datetime(2026, 10, 17, 12, tzinfo=UTC),
            "s1_pass_date": "2026-10-12",
            "cells": 200,
            "dams": 50,
        }
    )

    run = repos.ranking_runs.get("riau", "2026-W42")

    assert run is not None
    assert run.s1_pass_date.isoformat() == "2026-10-12"
    assert repos.ranking_runs.get("riau", "2026-W41") is None
