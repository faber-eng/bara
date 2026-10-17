import base64
from datetime import UTC, datetime

from fastapi.testclient import TestClient

import main
from adapters.firestore_repos import CaseRepository, EventLog, RankedDamRepository
from adapters.gemini import ModelGateway
from contracts import Case, ProcessedEvent, RankedDam
from events import DryingRankedHandler, EventDispatcher
from tests.fakes import (
    FakeModels,
    FakeVerifier,
    InMemoryCollection,
    make_drying_ranked_event,
    make_ranked_dam,
    push_body,
)

NOW = datetime(2026, 10, 17, 13, 0, tzinfo=UTC)


class FakeOidc:
    def __init__(self, claims):
        self._claims = claims

    def verify(self, token, audience):
        return self._claims


class FakeAgent:
    def __init__(self):
        self.runs = []

    async def run_case(self, trigger, case_id, run_id):
        self.runs.append(run_id)


class FixedClock:
    def now(self):
        return NOW


def make_world(settings):
    cases = InMemoryCollection(Case)
    dams = InMemoryCollection(RankedDam)
    dams.put("dam-1", make_ranked_dam())
    agent = FakeAgent()
    handler = DryingRankedHandler(
        cases=CaseRepository(cases),
        ranked_dams=RankedDamRepository(lambda region: dams),
        agent=agent,
        clock=FixedClock(),
        max_cases=3,
    )
    events = InMemoryCollection(ProcessedEvent)
    dispatcher = EventDispatcher(
        EventLog(events, lambda: NOW), {"drying.ranked": handler}
    )
    gateway = ModelGateway(
        settings.models, {"reasoning": FakeModels([]), "fast": FakeModels([])}
    )
    app = main.build_app(settings, gateway, FakeVerifier({}))
    app.state.dispatcher = dispatcher
    app.state.push_verifier = FakeOidc(
        {"email": settings.tasks_invoker_email, "email_verified": True}
    )
    return TestClient(app), cases, agent


AUTH = {"Authorization": "Bearer push-token"}


def test_a_push_without_a_token_is_401(settings):
    client, cases, _ = make_world(settings)

    response = client.post(
        "/api/events/drying.ranked", json=push_body(make_drying_ranked_event())
    )

    assert response.status_code == 401
    assert cases.where() == []


def test_a_signed_push_opens_the_case_and_runs_the_agent(settings):
    client, cases, agent = make_world(settings)

    response = client.post(
        "/api/events/drying.ranked",
        json=push_body(make_drying_ranked_event(), "m-1"),
        headers=AUTH,
    )

    assert response.status_code == 200
    assert response.json() == {"status": "processed"}
    assert len(cases.where()) == 1
    assert agent.runs == ["m-1-case-m-1-dam-1"]


def test_the_same_message_pushed_twice_creates_one_case(settings):
    client, cases, agent = make_world(settings)
    body = push_body(make_drying_ranked_event(), "m-1")

    first = client.post("/api/events/drying.ranked", json=body, headers=AUTH)
    second = client.post("/api/events/drying.ranked", json=body, headers=AUTH)

    assert (first.status_code, second.status_code) == (200, 200)
    assert second.json() == {"status": "duplicate"}
    assert len(cases.where()) == 1
    assert len(agent.runs) == 1


def test_a_body_that_is_not_an_event_is_400(settings):
    client, _, _ = make_world(settings)
    garbage = base64.b64encode(b"{}").decode()

    response = client.post(
        "/api/events/drying.ranked",
        json={"message": {"data": garbage, "messageId": "m"}},
        headers=AUTH,
    )

    assert response.status_code == 400


def test_a_topic_without_a_handler_is_404(settings):
    client, _, _ = make_world(settings)

    response = client.post(
        "/api/events/fire.quiet",
        json=push_body(make_drying_ranked_event()),
        headers=AUTH,
    )

    assert response.status_code == 404


def test_an_event_on_the_wrong_topic_is_400(settings):
    client, _, _ = make_world(settings)
    quiet_topic_with_drying_event = make_drying_ranked_event()

    response = client.post(
        "/api/events/drying.ranked",
        json=push_body(
            quiet_topic_with_drying_event.model_copy(update={"type": "fire.quiet"})
        ),
        headers=AUTH,
    )

    assert response.status_code == 400
