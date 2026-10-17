import asyncio
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

import main
from adapters.cells import CENTROID_SQL, CellRepository
from adapters.channels import WebChannel
from adapters.firestore_repos import (
    CASES,
    MESSAGES,
    CaseRepository,
    CaseworkStore,
    TaskRepository,
    VolunteerRepository,
)
from adapters.gemini import ModelGateway
from bara_agent.tools.request_human_review import RequestHumanReview
from casework.escalation import EscalationRejected
from casework.review import NotInReview, ReviewDesk, ReviewRejected, UnknownReviewCase
from contracts import (
    Case,
    ClockSettings,
    GeoPoint,
    Message,
    ReviewRequest,
    Task,
    Volunteer,
)
from domain.clock import Clock
from tests.fakes import (
    FakeModels,
    FakeVerifier,
    FakeWarehouse,
    InMemoryClockStore,
    InMemoryCollection,
    InMemoryTransactor,
    make_case,
    make_escalation,
    make_task,
    make_volunteer,
)

NOW = datetime(2026, 10, 17, 12, 0, tzinfo=UTC)
OPS = {"Authorization": "Bearer ops"}


class FakeEscalator:
    def __init__(self, error=None, cases=None):
        self.error = error
        self.cases = cases
        self.calls = []

    async def escalate(self, case_id, reason):
        self.calls.append((case_id, reason))
        if self.error is not None:
            raise self.error
        self.cases.update(case_id, {"status": "escalated"})
        return make_escalation()


class FakeAssigner:
    def __init__(self, cases):
        self.cases = cases
        self.requests = []

    async def assign(self, request):
        self.requests.append(request)
        self.cases.update(request.case_id, {"status": "assigned"})


class World:
    def __init__(
        self, status="human_review", escalator_error=None, tasks=True, people=True
    ):
        self.cases = InMemoryCollection(Case)
        self.cases.put("c1", make_case(id="c1", status=status))
        self.messages = InMemoryCollection(Message)
        self.escalator = FakeEscalator(escalator_error, self.cases)
        self.assigner = FakeAssigner(self.cases)
        task_docs = InMemoryCollection(Task)
        if tasks:
            task_docs.put("t1", make_task(id="t1", type="dam_repair", status="done"))
        volunteers = InMemoryCollection(Volunteer)
        if people:
            volunteers.put(
                "far",
                make_volunteer(
                    id="far", role="repair_team", home=GeoPoint(lat=0.9, lon=101.4)
                ),
            )
            volunteers.put(
                "near",
                make_volunteer(
                    id="near", role="repair_team", home=GeoPoint(lat=0.5001, lon=101.4)
                ),
            )
            volunteers.put(
                "other",
                make_volunteer(
                    id="other", role="volunteer", home=GeoPoint(lat=0.5, lon=101.4)
                ),
            )
        clock = Clock(
            InMemoryClockStore(ClockSettings(offset_seconds=0, updated_by="t")),
            lambda: NOW,
        )
        ids = iter(f"m{n}" for n in range(1, 50))
        self.desk = ReviewDesk(
            cases=CaseRepository(self.cases),
            tasks=TaskRepository(task_docs),
            volunteers=VolunteerRepository(volunteers),
            cells=CellRepository(
                FakeWarehouse({CENTROID_SQL: [{"lat": 0.5, "lon": 101.4}]})
            ),
            casework=CaseworkStore(
                InMemoryTransactor({CASES: self.cases, MESSAGES: self.messages})
            ),
            assigner=self.assigner,
            escalator=self.escalator,
            channel=WebChannel(clock, lambda: next(ids)),
            clock=clock,
        )

    def resolve(self, action, note="Checked by phone.", case_id="c1"):
        request = ReviewRequest(action=action, note=note)
        return asyncio.run(self.desk.resolve(case_id, request, "ops-1"))


def test_close_closes_the_case_records_who_and_keeps_the_note():
    world = World()

    case = world.resolve("close")

    assert case.status == "closed"
    assert case.closed_by == "ops-1"
    assert case.closed_at == NOW
    note = world.messages.get("m1")
    assert (note.thread, note.to_id, note.case_id, note.text) == (
        "ops",
        "ops",
        "c1",
        "Checked by phone.",
    )


def test_assign_gives_the_nearest_person_for_the_last_task_type_a_new_task():
    world = World()

    case = world.resolve("assign", note="Go back and check the gate.")

    assert case.status == "assigned"
    assert case.closed_by is None
    [request] = world.assigner.requests
    assert (request.case_id, request.assignee_id, request.task_type) == (
        "c1",
        "near",
        "dam_repair",
    )
    assert request.instructions_hint == "Go back and check the gate."
    assert world.messages.get("m1").text == "Go back and check the gate."


def test_assign_without_a_prior_task_is_rejected_and_the_case_stays_in_review():
    world = World(tasks=False)

    with pytest.raises(ReviewRejected):
        world.resolve("assign")

    assert world.cases.get("c1").status == "human_review"


def test_assign_with_nobody_available_is_rejected():
    world = World(people=False)

    with pytest.raises(ReviewRejected, match="nobody is available"):
        world.resolve("assign")

    assert world.assigner.requests == []


def test_a_note_appears_in_the_case_timeline():
    from domain.case_view import note_entry

    world = World()
    world.resolve("close", note="Checked by phone.")

    entry = note_entry(world.messages.get("m1"))

    assert entry.text == "Review note: Checked by phone."
    assert entry.at == NOW


def test_a_case_that_left_review_during_a_refused_escalation_is_not_in_review():
    world = World(
        escalator_error=EscalationRejected("a closed case cannot be escalated")
    )
    world.escalator.error = None

    async def close_then_refuse(case_id, reason):
        world.cases.update(case_id, {"status": "closed"})
        raise EscalationRejected("a closed case cannot be escalated")

    world.escalator.escalate = close_then_refuse

    with pytest.raises(NotInReview):
        world.resolve("escalate")


def test_escalate_goes_through_the_escalator_with_the_note_as_reason():
    world = World()

    case = world.resolve("escalate", note="Smoke confirmed by the village head.")

    assert world.escalator.calls == [("c1", "Smoke confirmed by the village head.")]
    assert case.status == "escalated"
    assert world.messages.get("m1").text == "Smoke confirmed by the village head."


def test_a_rejected_escalation_keeps_the_case_in_review_and_saves_no_note():
    world = World(escalator_error=EscalationRejected("no brigade contact in riau"))

    with pytest.raises(EscalationRejected):
        world.resolve("escalate")

    assert world.cases.get("c1").status == "human_review"
    assert world.messages.get("m1") is None


@pytest.mark.parametrize("status", ["open", "reviewing", "closed", "escalated"])
def test_only_a_case_in_human_review_can_be_resolved(status):
    world = World(status=status)

    with pytest.raises(NotInReview):
        world.resolve("close")

    assert world.cases.get("c1").status == status


def test_an_unknown_case_is_unknown():
    with pytest.raises(UnknownReviewCase):
        World().resolve("close", case_id="nope")


def test_a_review_request_moves_a_reviewing_case_to_human_review():
    world = World(status="reviewing")

    world.desk.request("c1", "location mismatch")

    assert world.cases.get("c1").status == "human_review"


def test_a_second_review_request_is_a_no_op():
    world = World(status="human_review")

    world.desk.request("c1", "again")

    assert world.cases.get("c1").status == "human_review"


@pytest.mark.parametrize("status", ["closed", "assigned", "escalated"])
def test_a_case_that_cannot_go_to_review_is_rejected(status):
    world = World(status=status)

    with pytest.raises(ReviewRejected):
        world.desk.request("c1", "why")


def test_request_for_an_unknown_case_is_rejected():
    with pytest.raises(ReviewRejected):
        World().desk.request("nope", "why")


def test_the_tool_flags_the_case_and_reports_the_status():
    world = World(status="reviewing")
    tool = RequestHumanReview(world.desk)

    result = asyncio.run(tool.request_human_review("c1", "location mismatch"))

    assert result == {"case_id": "c1", "status": "human_review"}
    assert world.cases.get("c1").status == "human_review"


def test_the_tool_returns_an_error_for_a_closed_case():
    tool = RequestHumanReview(World(status="closed").desk)

    result = asyncio.run(tool.request_human_review("c1", "why"))

    assert result == {"error": "a closed case cannot go to human review"}


def test_the_tool_summary():
    assert (
        RequestHumanReview.summarize({"case_id": "c1", "status": "human_review"})
        == "case c1 sent to a person"
    )


def client(settings, world) -> TestClient:
    gateway = ModelGateway(
        settings.models, {"reasoning": FakeModels([]), "fast": FakeModels([])}
    )
    verifier = FakeVerifier(
        {
            "ops": {"uid": "ops-1", "role": "ops"},
            "volunteer": {"uid": "v1", "role": "volunteer"},
        }
    )
    app = main.build_app(settings, gateway, verifier)
    app.state.review_desk = world.desk
    return TestClient(app)


def post(settings, world, body, headers=OPS, case_id="c1"):
    return client(settings, world).post(
        f"/api/cases/{case_id}/review", json=body, headers=headers
    )


def test_the_route_closes_a_case_in_review(settings):
    world = World()

    response = post(settings, world, {"action": "close", "note": "All good."})

    assert response.status_code == 200
    assert response.json()["status"] == "closed"
    assert response.json()["closed_by"] == "ops-1"


def test_the_route_refuses_a_volunteer(settings):
    response = post(
        settings,
        World(),
        {"action": "close", "note": "x"},
        headers={"Authorization": "Bearer volunteer"},
    )

    assert response.status_code == 403


@pytest.mark.parametrize(
    "body",
    [
        {"action": "close"},
        {"action": "close", "note": "   "},
        {"action": "reopen", "note": "x"},
    ],
)
def test_the_route_needs_an_action_and_a_note(settings, body):
    assert post(settings, World(), body).status_code == 422


def test_the_route_is_409_for_a_case_not_in_review(settings):
    response = post(settings, World(status="open"), {"action": "close", "note": "x"})

    assert (response.status_code, response.json()["detail"]) == (409, "not_in_review")


def test_the_route_is_404_for_an_unknown_case(settings):
    response = post(settings, World(), {"action": "close", "note": "x"}, case_id="nope")

    assert response.status_code == 404


def test_the_route_is_409_when_the_escalation_is_refused(settings):
    world = World(escalator_error=EscalationRejected("no contact"))

    response = post(settings, world, {"action": "escalate", "note": "x"})

    assert (response.status_code, response.json()["detail"]) == (
        409,
        "escalation_rejected",
    )


def test_the_route_is_409_when_assign_has_nobody_to_ask(settings):
    response = post(settings, World(people=False), {"action": "assign", "note": "x"})

    assert (response.status_code, response.json()["detail"]) == (
        409,
        "review_rejected",
    )
