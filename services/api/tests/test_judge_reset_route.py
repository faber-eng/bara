from datetime import UTC, datetime
from types import SimpleNamespace

from fastapi.testclient import TestClient

import main
from adapters.gemini import ModelGateway
from config import JudgeMode
from contracts import ClockSettings
from domain.clock import Clock
from tests.fakes import FakeModels, FakeVerifier, InMemoryClockStore

REAL_NOW = datetime(2026, 10, 17, 12, 0, tzinfo=UTC)
JOBS: list[str] = []


class FakeResetter:
    def __init__(self, store):
        self._store = store
        self.calls: list[str] = []

    def reset(self, updated_by):
        self.calls.append(updated_by)
        self._store.put(ClockSettings(offset_seconds=0, updated_by="reset"))


def make_client(settings, judge=True, max_resets=20):
    configured = settings.model_copy(
        update={"judge_mode": JudgeMode(enabled=judge, max_resets_per_hour=max_resets)}
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
    store = InMemoryClockStore(ClockSettings(offset_seconds=172800, updated_by="judge"))
    app.state.adapters = SimpleNamespace(clock=Clock(store, lambda: REAL_NOW))
    app.state.resetter = FakeResetter(store)
    app.state.bulletin_job = lambda: JOBS.append("bulletin")
    return TestClient(app), app.state.resetter


def reset(client, token="judge-claim", headers=None):
    return client.post(
        "/api/judge/reset",
        headers={"Authorization": f"Bearer {token}", **(headers or {})},
    )


def test_a_judge_claim_resets_and_gets_the_clock_state_back(settings):
    client, resetter = make_client(settings, judge=False)

    response = reset(client)

    assert response.status_code == 200
    assert response.json() == {
        "now": "2026-10-17T12:00:00Z",
        "offset_seconds": 0,
        "judge_mode": False,
    }
    assert resetter.calls == ["j1"]


def test_a_reset_writes_the_bulletin_after_the_response(settings):
    JOBS.clear()
    client, _ = make_client(settings)

    assert reset(client).status_code == 200
    assert JOBS == ["bulletin"]


def test_a_refused_reset_writes_no_bulletin(settings):
    JOBS.clear()
    client, _ = make_client(settings)

    assert reset(client, "ops-claim").status_code == 403
    assert JOBS == []


def test_the_judge_header_works_while_judge_mode_is_on(settings):
    client, resetter = make_client(settings, judge=True)

    response = reset(client, "plain", {"X-Bara-Role": "judge"})

    assert response.status_code == 200
    assert response.json()["judge_mode"] is True
    assert resetter.calls == ["u3"]


def test_ops_cannot_reset(settings):
    client, resetter = make_client(settings)

    assert reset(client, "ops-claim").status_code == 403
    assert resetter.calls == []


def test_the_judge_header_is_ignored_with_judge_mode_off(settings):
    client, resetter = make_client(settings, judge=False)

    assert reset(client, "plain", {"X-Bara-Role": "judge"}).status_code == 403
    assert resetter.calls == []


def test_without_a_token_it_is_401(settings):
    client, _ = make_client(settings)

    assert client.post("/api/judge/reset").status_code == 401


def test_the_limit_per_hour_returns_429_with_retry_after(settings):
    client, resetter = make_client(settings, max_resets=2)

    codes = [reset(client).status_code for _ in range(3)]

    assert codes == [200, 200, 429]
    assert len(resetter.calls) == 2
    assert int(reset(client).headers["Retry-After"]) > 0
