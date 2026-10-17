import google.auth
import pytest
from google.auth.credentials import AnonymousCredentials

import main
from adapters.factory import build_adapters
from bara_agent.run import AgentService
from config import ConfigError


@pytest.fixture(autouse=True)
def offline_credentials(monkeypatch):
    monkeypatch.setattr(
        google.auth,
        "default",
        lambda *a, **k: (AnonymousCredentials(), "example-project"),
    )


def test_build_adapters_wires_every_adapter_offline(settings):
    adapters = build_adapters(settings)

    assert adapters.scheduler is not None
    assert adapters.clock is not None
    assert adapters.warehouse is not None


def test_without_an_api_url_the_scheduler_is_none(settings):
    adapters = build_adapters(settings.model_copy(update={"api_url": None}))

    assert adapters.scheduler is None


def test_build_agent_service_wires_the_coordinator_offline(settings, monkeypatch):
    monkeypatch.setenv("GOOGLE_GENAI_USE_ENTERPRISE", "True")

    service = main.build_agent_service(settings, build_adapters(settings))

    assert isinstance(service, AgentService)


def test_build_agent_service_without_enterprise_mode_fails_at_boot(
    settings, monkeypatch
):
    monkeypatch.delenv("GOOGLE_GENAI_USE_ENTERPRISE", raising=False)

    with pytest.raises(ConfigError, match="GOOGLE_GENAI_USE_ENTERPRISE"):
        main.build_agent_service(settings, build_adapters(settings))
