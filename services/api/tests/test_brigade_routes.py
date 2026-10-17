import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from casework.escalation import (
    EscalationRejected,
    NotYourEscalation,
    UnknownEscalation,
)
from config import JudgeMode
from routes import brigade
from tests.fakes import FakeVerifier, make_escalation

TOKENS = {
    "ct1": {"uid": "ct1", "role": "brigade"},
    "v1": {"uid": "v1", "role": "volunteer"},
    "judge-anon": {"uid": "J"},
}


class StubInbox:
    def __init__(self):
        self.read_for = []

    def read(self, contact_id):
        self.read_for.append(contact_id)
        return [make_escalation(id="x1", contact_id=contact_id)]


class StubAcknowledger:
    def __init__(self, error=None):
        self.error = error
        self.calls = []

    def ack(self, escalation_id, owner_id):
        self.calls.append((escalation_id, owner_id))
        if self.error is not None:
            raise self.error
        return make_escalation(id=escalation_id)


def make_client(settings, inbox=None, acknowledger=None, judge=False):
    app = FastAPI()
    app.state.settings = settings.model_copy(
        update={"judge_mode": JudgeMode(enabled=judge, max_resets_per_hour=20)}
    )
    app.state.verifier = FakeVerifier(TOKENS)
    app.state.brigade_inbox = inbox or StubInbox()
    app.state.acknowledger = acknowledger or StubAcknowledger()
    app.include_router(brigade.router)
    return TestClient(app)


def bearer(token, **headers):
    return {"Authorization": f"Bearer {token}", **headers}


def test_the_contact_reads_its_inbox(settings):
    inbox = StubInbox()

    response = make_client(settings, inbox=inbox).get(
        "/api/brigade/ct1/inbox", headers=bearer("ct1")
    )

    assert response.status_code == 200
    assert response.json()[0]["id"] == "x1"
    assert inbox.read_for == ["ct1"]


@pytest.mark.parametrize(
    ("token", "path"),
    [("ct1", "/api/brigade/ct2/inbox"), ("v1", "/api/brigade/v1/inbox")],
)
def test_another_contact_or_role_is_403_on_the_inbox(settings, token, path):
    inbox = StubInbox()

    response = make_client(settings, inbox=inbox).get(path, headers=bearer(token))

    assert response.status_code == 403
    assert inbox.read_for == []


def test_a_judge_brigade_header_reads_any_contact_inbox(settings):
    response = make_client(settings, judge=True).get(
        "/api/brigade/contact-daops-pekanbaru/inbox",
        headers=bearer("judge-anon", **{"X-Bara-Role": "brigade"}),
    )

    assert response.status_code == 200


def test_a_claimed_contact_acks_as_its_own_owner(settings):
    acknowledger = StubAcknowledger()

    response = make_client(settings, acknowledger=acknowledger).post(
        "/api/brigade/escalations/x1/ack", headers=bearer("ct1")
    )

    assert response.status_code == 200
    assert response.json()["id"] == "x1"
    assert acknowledger.calls == [("x1", "ct1")]


def test_a_judge_ack_has_no_owner(settings):
    acknowledger = StubAcknowledger()

    make_client(settings, acknowledger=acknowledger, judge=True).post(
        "/api/brigade/escalations/x1/ack",
        headers=bearer("judge-anon", **{"X-Bara-Role": "brigade"}),
    )

    assert acknowledger.calls == [("x1", None)]


def test_a_volunteer_cannot_ack(settings):
    acknowledger = StubAcknowledger()

    response = make_client(settings, acknowledger=acknowledger).post(
        "/api/brigade/escalations/x1/ack", headers=bearer("v1")
    )

    assert response.status_code == 403
    assert acknowledger.calls == []


@pytest.mark.parametrize(
    ("error", "status"),
    [
        (UnknownEscalation("x1"), 404),
        (NotYourEscalation("x1"), 403),
        (EscalationRejected("changed"), 409),
    ],
)
def test_ack_errors_map_to_statuses(settings, error, status):
    client = make_client(settings, acknowledger=StubAcknowledger(error))

    response = client.post("/api/brigade/escalations/x1/ack", headers=bearer("ct1"))

    assert response.status_code == status
