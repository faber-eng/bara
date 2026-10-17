import google.auth
import pytest
from google.auth.credentials import AnonymousCredentials

import main
from adapters.factory import build_adapters
from adapters.gemini import ModelGateway
from bara_agent.run import AgentService
from config import ConfigError
from tests.fakes import FakeModels


def offline_gateway(settings) -> ModelGateway:
    return ModelGateway(
        settings.models, {"reasoning": FakeModels([]), "fast": FakeModels([])}
    )


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
    assert adapters.uploads is not None
    assert adapters.messages is not None
    assert adapters.verdicts is not None


def test_without_an_api_url_the_scheduler_is_none(settings):
    adapters = build_adapters(settings.model_copy(update={"api_url": None}))

    assert adapters.scheduler is None


def test_build_agent_service_wires_the_coordinator_offline(settings, monkeypatch):
    monkeypatch.setenv("GOOGLE_GENAI_USE_ENTERPRISE", "True")

    adapters = build_adapters(settings)
    gateway = offline_gateway(settings)

    service = main.build_agent_service(
        settings,
        adapters,
        gateway,
        main.build_checker(settings, adapters, gateway),
        main.build_escalator(adapters, gateway),
    )

    assert isinstance(service, AgentService)


def test_build_agent_service_without_enterprise_mode_fails_at_boot(
    settings, monkeypatch
):
    monkeypatch.delenv("GOOGLE_GENAI_USE_ENTERPRISE", raising=False)

    adapters = build_adapters(settings)
    gateway = offline_gateway(settings)

    with pytest.raises(ConfigError, match="GOOGLE_GENAI_USE_ENTERPRISE"):
        main.build_agent_service(
            settings,
            adapters,
            gateway,
            main.build_checker(settings, adapters, gateway),
            main.build_escalator(adapters, gateway),
        )


def test_build_dispatcher_handles_every_pushed_topic_and_trigger_wires_offline(
    settings, monkeypatch
):
    monkeypatch.setenv("GOOGLE_GENAI_USE_ENTERPRISE", "True")
    adapters = build_adapters(settings)
    gateway = offline_gateway(settings)
    checker = main.build_checker(settings, adapters, gateway)
    escalator = main.build_escalator(adapters, gateway)
    agent = main.build_agent_service(settings, adapters, gateway, checker, escalator)

    assigner = main.build_assigner(settings, adapters, gateway)
    precomputer = main.build_explanation_precomputer(settings, adapters, gateway)
    queries = main.build_public_queries(settings, adapters)
    bulletin = main.build_bulletin_writer(settings, adapters, gateway, queries)
    dispatcher = main.build_dispatcher(
        settings, adapters, agent, checker, assigner, escalator, precomputer, bulletin
    )
    trigger = main.build_trigger(settings, adapters)

    assert set(dispatcher._handlers) == {
        "drying.ranked",
        "evidence.received",
        "task.overdue",
        "fire.quiet",
    }
    assert trigger is not None


def test_build_deadlines_wires_offline(settings):
    adapters = build_adapters(settings)

    assert main.build_deadlines(adapters) is not None
