import asyncio

from fastapi.testclient import TestClient
from google.genai import types

import main
from adapters.gemini import ModelGateway
from tests.fakes import FakeModels, FakeVerifier, api_error, stub_app_builders


def make_client(settings, reasoning_outcomes=()):
    reasoning = FakeModels(list(reasoning_outcomes))
    fast = FakeModels([])
    gateway = ModelGateway(settings.models, {"reasoning": reasoning, "fast": fast})
    return (
        TestClient(main.build_app(settings, gateway, FakeVerifier({}))),
        gateway,
        reasoning,
        fast,
    )


def test_health_returns_models_fallback_flag_and_git_sha(settings):
    client, _, _, _ = make_client(settings)

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "models": {"reasoning": "reasoning-primary", "fast": "fast-primary"},
        "fallback_used": False,
        "git_sha": "abc1234",
    }


def test_health_makes_no_model_call(settings):
    client, _, reasoning, fast = make_client(settings)

    client.get("/api/health")

    assert reasoning.calls == []
    assert fast.calls == []


def test_health_reports_a_fallback_after_one_happened(settings):
    client, gateway, _, _ = make_client(
        settings, [api_error(404), types.GenerateContentResponse()]
    )
    asyncio.run(gateway.generate("reasoning", "ping"))

    assert client.get("/api/health").json()["fallback_used"] is True


def test_create_app_wires_the_repo_config(monkeypatch):
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "example-project")
    monkeypatch.setenv("GIT_SHA", "fe23bb1")
    monkeypatch.delenv("REASONING_MODEL", raising=False)
    monkeypatch.delenv("FAST_MODEL", raising=False)
    monkeypatch.delenv("BARA_CONFIG_DIR", raising=False)
    stub_app_builders(monkeypatch, main, FakeVerifier({}))

    body = TestClient(main.create_app()).get("/api/health").json()

    assert body["models"] == {
        "reasoning": "gemini-3.1-pro-preview",
        "fast": "gemini-3.5-flash",
    }
    assert body["git_sha"] == "fe23bb1"


def test_create_app_puts_the_verifier_and_adapters_on_app_state(monkeypatch):
    verifier = FakeVerifier({})
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "example-project")
    stub_app_builders(monkeypatch, main, verifier)

    app = main.create_app()

    assert app.state.verifier is verifier
    assert app.state.adapters == "adapters"


def test_importing_main_initialises_no_firebase_app():
    import firebase_admin

    assert firebase_admin._apps == {}
