from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from fastapi.testclient import TestClient

import main
from adapters.gemini import ModelGateway
from config import JudgeMode
from contracts import ClockSettings
from domain.clock import Clock
from tests.fakes import FakeModels, FakeVerifier, InMemoryClockStore

REAL_NOW = datetime(2026, 10, 17, 12, 0, tzinfo=UTC)


def make_client(settings, offset_seconds=0, judge=None):
    configured = settings
    if judge is not None:
        configured = settings.model_copy(
            update={"judge_mode": JudgeMode(enabled=judge, max_resets_per_hour=20)}
        )
    gateway = ModelGateway(
        configured.models, {"reasoning": FakeModels([]), "fast": FakeModels([])}
    )
    app = main.build_app(configured, gateway, FakeVerifier({}))
    store = InMemoryClockStore(
        ClockSettings(offset_seconds=offset_seconds, updated_by="seed")
    )
    app.state.adapters = SimpleNamespace(clock=Clock(store, lambda: REAL_NOW))
    return TestClient(app)


def test_the_clock_is_public_and_reports_the_simulated_now(settings):
    client = make_client(settings, offset_seconds=48 * 3600)

    response = client.get("/api/clock")

    assert response.status_code == 200
    body = response.json()
    assert body["offset_seconds"] == 48 * 3600
    assert datetime.fromisoformat(body["now"]) == REAL_NOW + timedelta(hours=48)


def test_with_no_offset_now_is_the_real_time(settings):
    body = make_client(settings).get("/api/clock").json()

    assert body["offset_seconds"] == 0
    assert datetime.fromisoformat(body["now"]) == REAL_NOW


def test_judge_mode_follows_the_effective_setting(settings):
    assert (
        make_client(settings, judge=True).get("/api/clock").json()["judge_mode"] is True
    )
    assert (
        make_client(settings, judge=False).get("/api/clock").json()["judge_mode"]
        is False
    )


def test_judge_mode_reflects_the_environment_override(settings, tmp_path, monkeypatch):
    from config import load_settings

    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "example-project")
    monkeypatch.setenv("BARA_JUDGE_MODE", "1")
    loaded = load_settings(config_dir=settings.config_dir)

    assert make_client(loaded).get("/api/clock").json()["judge_mode"] is True


def test_the_reading_takes_one_store_read(settings):
    reads = []

    class CountingStore(InMemoryClockStore):
        def get(self):
            reads.append(1)
            return super().get()

    clock = Clock(
        CountingStore(ClockSettings(offset_seconds=5, updated_by="s")), lambda: REAL_NOW
    )

    reading = clock.reading()

    assert (reading.offset_seconds, reading.now) == (5, REAL_NOW + timedelta(seconds=5))
    assert len(reads) == 1
