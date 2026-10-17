from datetime import UTC, datetime

import pytest

from adapters.firestore_repos import CaseRepository, EventLog, RankedDamRepository
from contracts import Case, ProcessedEvent, RankedDam
from events import (
    DryingRankedHandler,
    EventDispatcher,
    MalformedPush,
    UnhandledTopic,
    decode_push,
)
from tests.fakes import (
    InMemoryCollection,
    make_case,
    make_drying_ranked_event,
    make_ranked_dam,
    push_body,
)

NOW = datetime(2026, 10, 17, 13, 0, tzinfo=UTC)


class FakeAgent:
    def __init__(self, fail_for: set[str] | None = None):
        self.runs: list[tuple[str, str, str]] = []
        self._fail_for = fail_for or set()

    async def run_case(self, trigger: str, case_id: str, run_id: str):
        self.runs.append((trigger, case_id, run_id))
        if case_id in self._fail_for:
            raise RuntimeError("model down")


class FixedClock:
    def now(self) -> datetime:
        return NOW


class World:
    def __init__(self, dams: list[RankedDam], open_cases=(), fail_for=None, limit=3):
        self.case_store = InMemoryCollection(Case)
        for case in open_cases:
            self.case_store.put(case.id, case)
        dam_store = InMemoryCollection(RankedDam)
        for dam in dams:
            dam_store.put(dam.dam_id, dam)
        self.agent = FakeAgent(fail_for)
        self.cases = CaseRepository(self.case_store)
        self.event_store = InMemoryCollection(ProcessedEvent)
        self.handler = DryingRankedHandler(
            cases=self.cases,
            ranked_dams=RankedDamRepository(lambda region: dam_store),
            agent=self.agent,
            clock=FixedClock(),
            max_cases=limit,
        )
        self.dispatcher = EventDispatcher(
            EventLog(self.event_store, lambda: NOW),
            {"drying.ranked": self.handler},
        )

    def deliver(self, message_id="m-1", event=None, topic="drying.ranked"):
        event = event or make_drying_ranked_event()
        return self.dispatcher.dispatch(topic, message_id, event)

    def all_cases(self) -> list[Case]:
        return self.case_store.where()


def five_dams() -> list[RankedDam]:
    return [
        make_ranked_dam(dam_id=f"dam-{n}", cell_id=f"cell-{n}", rank=n)
        for n in range(1, 6)
    ]


def test_the_top_three_dams_each_get_a_case_and_one_agent_run():
    world = World(five_dams())

    outcome = world.deliver()

    assert outcome == "processed"
    cases = sorted(world.all_cases(), key=lambda case: case.dam_id)
    assert [case.dam_id for case in cases] == ["dam-1", "dam-2", "dam-3"]
    assert {case.type for case in cases} == {"dam_risk"}
    assert {case.status for case in cases} == {"open"}
    assert [run[0] for run in world.agent.runs] == ["drying.ranked"] * 3


def test_a_case_carries_the_dam_cell_score_event_and_clock_time():
    world = World([make_ranked_dam(dam_id="dam-9", cell_id="c9", drying_score=88.5)])

    world.deliver(event=make_drying_ranked_event(id="evt-7"))

    case = world.all_cases()[0]
    assert (case.region, case.cell_id, case.dam_id) == ("riau", "c9", "dam-9")
    assert case.event_id == "evt-7"
    assert case.risk.drying_score == 88.5
    assert case.risk.p_reignite is None
    assert case.opened_at == NOW
    assert case.closed_by is None


def test_the_run_id_is_message_id_then_case_id():
    world = World([make_ranked_dam()])

    world.deliver(message_id="m-42")

    case = world.all_cases()[0]
    assert world.agent.runs == [("drying.ranked", case.id, f"m-42-{case.id}")]


def test_the_same_message_delivered_twice_creates_one_case_and_one_run():
    world = World(five_dams())

    first = world.deliver(message_id="m-1")
    second = world.deliver(message_id="m-1")

    assert (first, second) == ("processed", "duplicate")
    assert len(world.all_cases()) == 3
    assert len(world.agent.runs) == 3


def test_a_dam_with_an_open_case_is_skipped():
    existing = make_case(id="old", dam_id="dam-2", status="assigned")
    world = World(five_dams(), open_cases=[existing])

    world.deliver()

    new = [case for case in world.all_cases() if case.id != "old"]
    assert sorted(case.dam_id for case in new) == ["dam-1", "dam-3"]
    assert len(world.agent.runs) == 2


def test_a_dam_whose_case_is_closed_gets_a_new_case():
    closed = make_case(id="old", dam_id="dam-1", status="closed")
    world = World([make_ranked_dam(dam_id="dam-1")], open_cases=[closed])

    world.deliver()

    assert len(world.all_cases()) == 2


@pytest.mark.parametrize("example", [True, False])
def test_the_case_copies_the_example_flag_of_the_event(example):
    world = World([make_ranked_dam()])

    world.deliver(event=make_drying_ranked_event(example=example))

    assert world.all_cases()[0].example is example


def test_the_number_of_cases_is_capped_at_the_limit():
    world = World(five_dams(), limit=2)

    world.deliver()

    assert sorted(case.dam_id for case in world.all_cases()) == ["dam-1", "dam-2"]


def test_no_ranked_dams_opens_nothing_and_still_claims_the_message():
    world = World([])

    assert world.deliver() == "processed"
    assert world.all_cases() == []
    assert world.deliver() == "duplicate"


def test_one_failed_agent_run_does_not_stop_the_other_cases(caplog):
    world = World(five_dams(), fail_for={"case-m-1-dam-1"})

    outcome = world.deliver()

    assert outcome == "processed"
    assert len(world.agent.runs) == 3
    assert any(
        getattr(record, "fields", {}).get("event") == "event_case_run_failed"
        for record in caplog.records
    )


def test_a_topic_without_a_handler_is_refused_and_not_claimed():
    world = World([])

    with pytest.raises(UnhandledTopic):
        world.dispatcher.dispatch("fire.quiet", "m-1", make_drying_ranked_event())

    assert world.event_store.get("m-1") is None


def test_an_event_whose_type_differs_from_the_topic_is_malformed():
    world = World([])
    event = make_drying_ranked_event()

    with pytest.raises(MalformedPush):
        world.dispatcher.dispatch(
            "drying.ranked", "m-1", event.model_copy(update={"type": "fire.quiet"})
        )


def test_decode_push_returns_message_id_and_event():
    event = make_drying_ranked_event(id="evt-3")

    decoded = decode_push(push_body(event, "m-9"))

    assert decoded.message_id == "m-9"
    assert decoded.event == event


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"message": {}},
        {"message": {"messageId": "m", "data": "!!not base64!!"}},
        {"message": {"messageId": "m", "data": "e30="}},
        {"message": {"messageId": "", "data": "e30="}},
    ],
)
def test_decode_push_rejects_a_body_that_is_not_a_known_event(body):
    with pytest.raises(MalformedPush):
        decode_push(body)


class LateCreateCases(CaseRepository):
    def __init__(self, collection, rival: Case):
        super().__init__(collection)
        self._rival = rival
        self._collection = collection

    def create(self, case: Case) -> bool:
        created = super().create(case)
        self._collection.put(self._rival.id, self._rival)
        return created


def test_two_messages_racing_for_one_dam_leave_one_case():
    rival = make_case(
        id="case-m-0-dam-1",
        dam_id="dam-1",
        status="open",
        opened_at=NOW.replace(hour=12),
    )
    world = World([make_ranked_dam(dam_id="dam-1")])
    world.cases = LateCreateCases(world.case_store, rival)
    world.handler._cases = world.cases

    world.deliver()

    assert [case.id for case in world.all_cases()] == ["case-m-0-dam-1"]
    assert world.agent.runs == []


def test_when_the_rival_case_is_later_this_message_keeps_its_case():
    rival = make_case(
        id="case-z", dam_id="dam-1", status="open", opened_at=NOW.replace(hour=15)
    )
    world = World([make_ranked_dam(dam_id="dam-1")])
    world.cases = LateCreateCases(world.case_store, rival)
    world.handler._cases = world.cases

    world.deliver()

    assert len(world.agent.runs) == 1
    assert "case-m-1-dam-1" in {case.id for case in world.all_cases()}


class RaisingHandler:
    def __init__(self):
        self.calls = 0

    def handle(self, message_id, event):
        self.calls += 1
        if self.calls == 1:
            raise RuntimeError("store down")


def test_a_handler_error_releases_the_claim_so_a_redelivery_runs_again():
    store = InMemoryCollection(ProcessedEvent)
    handler = RaisingHandler()
    dispatcher = EventDispatcher(
        EventLog(store, lambda: NOW), {"drying.ranked": handler}
    )

    with pytest.raises(RuntimeError):
        dispatcher.dispatch("drying.ranked", "m-1", make_drying_ranked_event())

    assert store.get("m-1") is None
    assert dispatcher.dispatch("drying.ranked", "m-1", make_drying_ranked_event()) == (
        "processed"
    )
    assert handler.calls == 2
