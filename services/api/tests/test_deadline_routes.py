from datetime import UTC, datetime
from types import SimpleNamespace

from fastapi.testclient import TestClient

import main
from adapters.gemini import ModelGateway
from auth import InvalidToken, VerifierUnavailable
from casework.deadline import OverduePublishFailed, SweptTask
from config import JudgeMode
from contracts import ClockSettings
from domain.clock import Clock
from tests.fakes import FakeModels, FakeVerifier, InMemoryClockStore

REAL_NOW = datetime(2026, 10, 17, 12, 0, tzinfo=UTC)
PUSH = {"Authorization": "Bearer push-token"}


class FakeDeadlines:
    def __init__(self, clock, outcome="case_overdue", error=None):
        self._clock = clock
        self.outcome = outcome
        self.error = error
        self.handled = []
        self.sweeps = []

    def handle_deadline(self, task_id):
        self.handled.append(task_id)
        if self.error is not None:
            raise self.error
        return self.outcome

    def sweep_due(self):
        self.sweeps.append(self._clock.now())
        return [SweptTask("t1", "case_overdue")]


class FakeOidc:
    def __init__(self, claims=None, error=None):
        self._claims = claims
        self._error = error
        self.audiences = []

    def verify(self, token, audience):
        self.audiences.append(audience)
        if self._error is not None:
            raise self._error
        return self._claims


def make_client(settings, judge=True, oidc=None, **deadline_options):
    configured = settings.model_copy(
        update={"judge_mode": JudgeMode(enabled=judge, max_resets_per_hour=20)}
    )
    gateway = ModelGateway(
        configured.models, {"reasoning": FakeModels([]), "fast": FakeModels([])}
    )
    verifier = FakeVerifier(
        {
            "judge-claim": {"uid": "j1", "role": "judge"},
            "ops-claim": {"uid": "o1", "role": "ops"},
            "plain": {"uid": "u3"},
        }
    )
    app = main.build_app(configured, gateway, verifier)
    store = InMemoryClockStore(ClockSettings(offset_seconds=0, updated_by="seed"))
    clock = Clock(store, lambda: REAL_NOW)
    app.state.adapters = SimpleNamespace(clock=clock)
    app.state.deadlines = FakeDeadlines(clock, **deadline_options)
    app.state.push_verifier = oidc or FakeOidc(
        {"email": configured.tasks_invoker_email, "email_verified": True}
    )
    return TestClient(app), app.state.deadlines


def advance(client, body, token="judge-claim", headers=None):
    return client.post(
        "/api/judge/advance",
        json=body,
        headers={"Authorization": f"Bearer {token}", **(headers or {})},
    )


def test_a_judge_advances_the_clock_then_sweeps_and_gets_the_clock_state(settings):
    client, deadlines = make_client(settings)

    response = advance(client, {"hours": 48})

    assert response.status_code == 200
    assert response.json() == {
        "now": "2026-10-19T12:00:00Z",
        "offset_seconds": 172800,
        "judge_mode": True,
    }
    assert deadlines.sweeps == [datetime(2026, 10, 19, 12, 0, tzinfo=UTC)]


def test_the_judge_header_advances_while_judge_mode_is_on(settings):
    client, deadlines = make_client(settings)

    response = advance(client, {"hours": 1.5}, "plain", {"X-Bara-Role": "judge"})

    assert response.status_code == 200
    assert response.json()["offset_seconds"] == 5400
    assert len(deadlines.sweeps) == 1


def test_advance_is_refused_with_judge_mode_off(settings):
    client, deadlines = make_client(settings, judge=False)

    response = advance(client, {"hours": 48})

    assert response.status_code == 403
    assert deadlines.sweeps == []


def test_ops_cannot_advance(settings):
    client, deadlines = make_client(settings)

    assert advance(client, {"hours": 48}, "ops-claim").status_code == 403
    assert deadlines.sweeps == []


def test_advance_without_a_token_is_401(settings):
    client, _ = make_client(settings)

    assert client.post("/api/judge/advance", json={"hours": 48}).status_code == 401


def test_bad_hours_are_422_and_leave_the_clock_alone(settings):
    client, deadlines = make_client(settings)

    codes = [
        advance(client, body).status_code
        for body in (
            {"hours": 0},
            {"hours": -5},
            {"hours": 24 * 365 + 1},
            {"hours": "soon"},
            {},
            {"hours": 1, "extra": True},
        )
    ]

    assert codes == [422] * 6
    assert deadlines.sweeps == []
    assert client.get("/api/clock").json()["offset_seconds"] == 0


def test_an_advance_past_the_total_limit_is_422(settings):
    client, deadlines = make_client(settings)
    for _ in range(10):
        assert advance(client, {"hours": 24 * 365}).status_code == 200

    response = advance(client, {"hours": 1})

    assert response.status_code == 422
    assert len(deadlines.sweeps) == 10


def test_the_clock_route_reads_the_same_state_after_an_advance(settings):
    client, _ = make_client(settings)

    advanced = advance(client, {"hours": 48}).json()

    assert client.get("/api/clock").json() == advanced


def deadline(client, task_id="t1", headers=PUSH):
    return client.post(f"/api/internal/deadline/{task_id}", headers=headers)


def test_cloud_tasks_runs_the_deadline_handler(settings):
    client, deadlines = make_client(settings)

    response = deadline(client)

    assert response.status_code == 200
    assert response.json() == {"outcome": "case_overdue"}
    assert deadlines.handled == ["t1"]


def test_the_deadline_call_checks_the_token_against_the_service_url(settings):
    oidc = FakeOidc({"email": settings.tasks_invoker_email, "email_verified": True})
    client, _ = make_client(settings, oidc=oidc)

    deadline(client)

    assert oidc.audiences == ["https://api.example.test"]


def test_a_skipped_task_is_still_200_so_cloud_tasks_stops(settings):
    client, _ = make_client(settings, outcome="skipped")

    response = deadline(client)

    assert response.status_code == 200
    assert response.json() == {"outcome": "skipped"}


def test_a_failed_publish_is_503_so_cloud_tasks_retries(settings):
    client, deadlines = make_client(
        settings, error=OverduePublishFailed("task.overdue for t1")
    )

    response = deadline(client)

    assert response.status_code == 503
    assert response.json() == {"detail": "publish_failed"}
    assert deadlines.handled == ["t1"]


def test_a_deadline_call_without_a_token_is_401(settings):
    client, deadlines = make_client(settings)

    assert deadline(client, headers={}).status_code == 401
    assert deadlines.handled == []


def test_a_deadline_call_from_another_account_is_403(settings):
    oidc = FakeOidc({"email": "someone@example.com", "email_verified": True})
    client, deadlines = make_client(settings, oidc=oidc)

    assert deadline(client).status_code == 403
    assert deadlines.handled == []


def test_a_verifier_outage_is_503_and_runs_nothing(settings):
    oidc = FakeOidc(error=VerifierUnavailable("down"))
    client, deadlines = make_client(settings, oidc=oidc)

    assert deadline(client).status_code == 503
    assert deadlines.handled == []


def test_a_deadline_call_with_a_bad_token_is_401(settings):
    client, deadlines = make_client(settings, oidc=FakeOidc(error=InvalidToken("x")))

    assert deadline(client).status_code == 401
    assert deadlines.handled == []
