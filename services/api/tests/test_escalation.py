import asyncio
from datetime import UTC, datetime

import pytest

from adapters.channels import WebChannel
from adapters.firestore_repos import (
    CASES,
    ESCALATIONS,
    MESSAGES,
    AgentRunRepository,
    CaseRepository,
    CaseworkStore,
    ContactRepository,
    DamRepository,
    EscalationRepository,
    EvidenceRepository,
    TaskRepository,
)
from adapters.storage import InvalidObjectName, SigningUnavailable
from casework.brief import Brief
from casework.escalation import (
    Acknowledger,
    BrigadeInbox,
    EscalationRejected,
    Escalator,
    NotYourEscalation,
    UnknownEscalation,
)
from contracts import (
    AgentRun,
    Case,
    ClockSettings,
    Contact,
    Dam,
    Escalation,
    EscalationPack,
    Evidence,
    GeoPoint,
    Message,
    Task,
)
from domain.clock import Clock
from tests.fakes import (
    InMemoryClockStore,
    InMemoryCollection,
    InMemoryTransactor,
    make_case,
    make_contact,
    make_dam,
    make_escalation,
    make_evidence,
    make_task,
    make_verdict,
)

NOW = datetime(2026, 10, 17, 12, 0, tzinfo=UTC)
DAM_POINT = GeoPoint(lat=0.533, lon=102.204)


class FakeBrief:
    def __init__(self):
        self.facts = []

    async def write(self, facts):
        self.facts.append(facts)
        return Brief("Kirim regu ke riau-0412.", "Send a crew to riau-0412.", "gemini")


class FakePublisher:
    def __init__(self, error=None):
        self.error = error
        self.published = []

    def publish(self, topic, event):
        if self.error is not None:
            raise self.error
        self.published.append((topic, event))
        return "m1"


class FakeCells:
    def centroid(self, cell_id):
        return GeoPoint(lat=0.4, lon=101.0)


class FakeSigner:
    def signed_get_url_for(self, uri):
        if uri.startswith("gs://broken/"):
            raise SigningUnavailable("signBlob denied")
        if not uri.startswith("gs://b/"):
            raise InvalidObjectName(uri)
        return uri.replace("gs://", "https://signed.test/")


def collection_of(model, *items):
    collection = InMemoryCollection(model)
    for item in items:
        collection.put(item.id, item)
    return collection


class World:
    def __init__(self, *, case=None, contacts=None, publisher=None, dam_id="d1"):
        self.cases = collection_of(
            Case,
            case
            or make_case(
                id="c1", status="reviewing", dam_id=dam_id, cell_id="riau-0412"
            ),
        )
        self.tasks = collection_of(Task, make_task(id="t1", case_id="c1"))
        self.evidence = collection_of(
            Evidence,
            make_evidence(id="e1", gcs_uri="gs://b/e1.jpg", verdict=make_verdict()),
        )
        self.dams = collection_of(Dam, make_dam(id="d1", point=DAM_POINT))
        self.contacts = collection_of(
            Contact, *(contacts if contacts is not None else [make_contact()])
        )
        self.escalations = InMemoryCollection(Escalation)
        self.messages = InMemoryCollection(Message)
        self.brief = FakeBrief()
        self.publisher = publisher or FakePublisher()
        ids = iter(["x1", "msg-1", "ev-1", "x2", "msg-2", "ev-2"])
        self.clock = Clock(
            InMemoryClockStore(ClockSettings(offset_seconds=0, updated_by="t")),
            lambda: NOW,
        )
        casework = CaseworkStore(
            InMemoryTransactor(
                {
                    CASES: self.cases,
                    ESCALATIONS: self.escalations,
                    MESSAGES: self.messages,
                }
            )
        )
        self.escalator = Escalator(
            cases=CaseRepository(self.cases),
            tasks=TaskRepository(self.tasks),
            evidence=EvidenceRepository(self.evidence),
            runs=AgentRunRepository(lambda case_id: InMemoryCollection(AgentRun)),
            dams=DamRepository(self.dams),
            contacts=ContactRepository(self.contacts),
            escalations=EscalationRepository(self.escalations),
            cells=FakeCells(),
            casework=casework,
            brief=self.brief,
            channel=WebChannel(self.clock, lambda: next(ids)),
            publisher=self.publisher,
            clock=self.clock,
            new_id=lambda: next(ids),
        )
        self.acknowledger = Acknowledger(
            escalations=EscalationRepository(self.escalations),
            cases=CaseRepository(self.cases),
            casework=casework,
            clock=self.clock,
        )
        self.inbox = BrigadeInbox(
            escalations=EscalationRepository(self.escalations), signer=FakeSigner()
        )

    def escalate(self, reason="Smoke wisps on the recheck."):
        return asyncio.run(self.escalator.escalate("c1", reason))


def test_escalate_stores_the_escalation_moves_the_case_and_publishes():
    world = World()

    escalation = world.escalate()

    assert world.escalations.get("x1") == escalation
    assert world.cases.get("c1").status == "escalated"
    assert escalation.contact_id == "ct1"
    assert escalation.brief_id == "Kirim regu ke riau-0412."
    assert escalation.brief_en == "Send a crew to riau-0412."
    assert escalation.acknowledged_at is None
    topic, event = world.publisher.published[0]
    assert topic == "case.escalated"
    assert event.payload.escalation_id == "x1"
    assert event.example == world.cases.get("c1").example


def test_the_pack_holds_the_photos_the_dam_map_and_the_timeline():
    world = World()

    pack = world.escalate().pack

    assert pack.photos == ["gs://b/e1.jpg"]
    assert pack.map_url.endswith("query=0.533,102.204")
    assert pack.timeline[0].text.startswith("Case opened")


def test_a_case_without_a_dam_maps_the_cell_centroid():
    world = World(dam_id=None)

    pack = world.escalate().pack

    assert pack.map_url.endswith("query=0.4,101.0")


def test_the_brief_gets_the_case_facts_and_the_reason():
    world = World()

    world.escalate("Overdue twice.")

    facts = world.brief.facts[0]
    assert facts.reason == "Overdue twice."
    assert facts.cell_id == "riau-0412"
    assert facts.dam_id == "d1"


def test_the_brigade_gets_a_web_message_in_its_thread():
    world = World()

    world.escalate()

    message = world.messages.get("msg-1")
    assert message.thread == "brigade"
    assert message.to_id == "ct1"
    assert message.case_id == "c1"
    assert message.text == "Kirim regu ke riau-0412."


def test_a_second_escalate_returns_the_open_escalation():
    world = World()
    first = world.escalate()

    second = world.escalate()

    assert second == first
    assert len(world.publisher.published) == 1


def test_a_closed_case_cannot_be_escalated():
    world = World(case=make_case(id="c1", status="closed"))

    with pytest.raises(EscalationRejected):
        world.escalate()

    assert world.escalations.where() == []


def test_a_region_without_a_contact_cannot_escalate():
    world = World(contacts=[])

    with pytest.raises(EscalationRejected):
        world.escalate()

    assert world.cases.get("c1").status == "reviewing"


def test_a_contact_of_another_region_is_not_used():
    world = World(contacts=[make_contact(id="ct-jambi", region="jambi")])

    with pytest.raises(EscalationRejected):
        world.escalate()


def test_a_publish_failure_keeps_the_escalation():
    world = World(publisher=FakePublisher(RuntimeError("down")))

    world.escalate()

    assert world.cases.get("c1").status == "escalated"


def test_ack_moves_the_case_from_escalated_to_monitoring():
    world = World()
    world.escalate()

    acked = world.acknowledger.ack("x1", owner_id=None)

    assert acked.acknowledged_at == NOW
    assert world.escalations.get("x1").acknowledged_at == NOW
    assert world.cases.get("c1").status == "monitoring"


def test_a_repeat_ack_returns_the_acknowledged_escalation():
    world = World()
    world.escalate()
    first = world.acknowledger.ack("x1", owner_id=None)

    second = world.acknowledger.ack("x1", owner_id=None)

    assert second.acknowledged_at == first.acknowledged_at
    assert world.cases.get("c1").status == "monitoring"


def test_ack_of_a_case_no_longer_escalated_only_marks_the_escalation():
    world = World(case=make_case(id="c1", status="closed"))
    world.escalations.put("x1", make_escalation())

    world.acknowledger.ack("x1", owner_id=None)

    assert world.escalations.get("x1").acknowledged_at == NOW
    assert world.cases.get("c1").status == "closed"


def test_ack_of_an_unknown_escalation_is_refused():
    with pytest.raises(UnknownEscalation):
        World().acknowledger.ack("nope", owner_id=None)


def test_ack_by_another_contact_is_refused():
    world = World()
    world.escalate()

    with pytest.raises(NotYourEscalation):
        world.acknowledger.ack("x1", owner_id="ct-other")

    assert world.cases.get("c1").status == "escalated"


def test_the_inbox_lists_the_contact_escalations_newest_first_with_signed_photos():
    world = World()
    older = make_escalation(
        id="x0",
        created_at=datetime(2026, 10, 16, tzinfo=UTC),
        pack=EscalationPack(photos=["gs://b/e0.jpg"], map_url="", timeline=[]),
    )
    newer = make_escalation(id="x9")
    other = make_escalation(id="x5", contact_id="ct-other")
    acked = make_escalation(id="x7", acknowledged_at=NOW)
    for item in (older, newer, other, acked):
        world.escalations.put(item.id, item)

    inbox = world.inbox.read("ct1")

    assert [item.id for item in inbox] == ["x9", "x0"]
    assert inbox[1].pack.photos == ["https://signed.test/b/e0.jpg"]


def test_a_photo_that_cannot_be_signed_is_left_out_of_the_inbox():
    world = World()
    pack = EscalationPack(
        photos=["gs://other/e0.jpg", "gs://broken/e2.jpg", "gs://b/e1.jpg"],
        map_url="",
        timeline=[],
    )
    world.escalations.put("x1", make_escalation(pack=pack))

    inbox = world.inbox.read("ct1")

    assert inbox[0].pack.photos == ["https://signed.test/b/e1.jpg"]


class RacingStore:
    def __init__(self, inner, before_commit):
        self._inner = inner
        self._before_commit = before_commit

    def commit_escalation(self, **kwargs):
        self._before_commit()
        self._inner.commit_escalation(**kwargs)

    def commit_ack(self, **kwargs):
        self._before_commit()
        self._inner.commit_ack(**kwargs)


def store_of(world):
    return CaseworkStore(
        InMemoryTransactor(
            {
                CASES: world.cases,
                ESCALATIONS: world.escalations,
                MESSAGES: world.messages,
            }
        )
    )


def test_the_loser_of_an_escalation_race_returns_the_winner():
    world = World()
    winner = make_escalation(id="x-win")

    def other_run_escalates_first():
        world.escalations.put(winner.id, winner)
        world.cases.update("c1", {"status": "escalated"})

    world.escalator._casework = RacingStore(store_of(world), other_run_escalates_first)

    assert world.escalate() == winner
    assert world.publisher.published == []


def test_a_race_that_leaves_no_escalation_is_rejected():
    world = World()

    def case_moves_on():
        world.cases.update("c1", {"status": "human_review"})

    world.escalator._casework = RacingStore(store_of(world), case_moves_on)

    with pytest.raises(EscalationRejected):
        world.escalate()


def test_the_loser_of_an_ack_race_returns_the_stored_ack():
    world = World()
    world.escalate()

    def other_ack_first():
        world.escalations.update("x1", {"acknowledged_at": NOW})

    world.acknowledger._casework = RacingStore(store_of(world), other_ack_first)

    assert world.acknowledger.ack("x1", owner_id=None).acknowledged_at == NOW


def test_an_ack_race_that_leaves_it_unacked_is_rejected():
    world = World()
    world.escalate()

    def case_moves_on():
        world.cases.update("c1", {"status": "monitoring"})

    world.acknowledger._casework = RacingStore(store_of(world), case_moves_on)

    with pytest.raises(EscalationRejected):
        world.acknowledger.ack("x1", owner_id=None)
