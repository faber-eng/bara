import asyncio
import logging
import os
import threading
from types import SimpleNamespace

import pytest
from google.genai import types

from adapters.gemini import (
    ModelGateway,
    ThreadedModels,
    build_http_options,
    build_vertex_clients,
)
from config import load_settings
from tests.fakes import FakeModels, api_error

RESPONSE = types.GenerateContentResponse()


def make_gateway(settings, reasoning_outcomes, fast_outcomes=()):
    reasoning = FakeModels(list(reasoning_outcomes))
    fast = FakeModels(list(fast_outcomes))
    gateway = ModelGateway(settings.models, {"reasoning": reasoning, "fast": fast})
    return gateway, reasoning, fast


def generate(gateway, role="reasoning"):
    return asyncio.run(gateway.generate(role, "ping"))


def test_primary_success_returns_its_response(settings):
    gateway, reasoning, _ = make_gateway(settings, [RESPONSE])

    assert generate(gateway) is RESPONSE
    assert reasoning.calls == ["reasoning-primary"]
    assert gateway.fallback_used is False


@pytest.mark.parametrize("code", [404, 429])
def test_404_or_429_falls_back_once(settings, code):
    gateway, reasoning, _ = make_gateway(settings, [api_error(code), RESPONSE])

    assert generate(gateway) is RESPONSE
    assert reasoning.calls == ["reasoning-primary", "reasoning-backup"]
    assert gateway.fallback_used is True


def test_fallback_logs_a_structured_warning(settings, caplog):
    gateway, _, _ = make_gateway(settings, [api_error(404), RESPONSE])

    with caplog.at_level(logging.WARNING):
        generate(gateway)

    [record] = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert record.fields == {
        "event": "model_fallback",
        "role": "reasoning",
        "primary": "reasoning-primary",
        "fallback": "reasoning-backup",
        "code": 404,
    }


@pytest.mark.parametrize("code", [400, 403, 500])
def test_other_api_errors_propagate_without_fallback(settings, code):
    error = api_error(code)
    gateway, reasoning, _ = make_gateway(settings, [error])

    with pytest.raises(type(error)) as raised:
        generate(gateway)

    assert raised.value.code == code
    assert reasoning.calls == ["reasoning-primary"]
    assert gateway.fallback_used is False


def test_fallback_error_propagates_after_exactly_two_calls(settings):
    gateway, reasoning, _ = make_gateway(settings, [api_error(429), api_error(429)])

    with pytest.raises(Exception) as raised:
        generate(gateway)

    assert raised.value.code == 429
    assert reasoning.calls == ["reasoning-primary", "reasoning-backup"]


def test_non_api_error_propagates_without_fallback(settings):
    gateway, reasoning, _ = make_gateway(settings, [ValueError("bad contents")])

    with pytest.raises(ValueError):
        generate(gateway)

    assert reasoning.calls == ["reasoning-primary"]


def test_fast_role_uses_the_fast_client_and_model(settings):
    gateway, reasoning, fast = make_gateway(settings, [], [RESPONSE])

    assert generate(gateway, "fast") is RESPONSE
    assert fast.calls == ["fast-primary"]
    assert reasoning.calls == []


def test_retry_options_cover_5xx_and_leave_404_and_429_to_the_fallback():
    retry = build_http_options().retry_options

    assert retry.attempts == 3
    assert set(retry.http_status_codes) == {500, 502, 503, 504}


def test_model_calls_time_out_after_60_seconds():
    assert build_http_options().timeout == 60_000


class RecordingSyncModels:
    def __init__(self):
        self.calls = []
        self.threads = []

    def generate_content(self, *, model, contents, config=None):
        self.calls.append((model, contents, config))
        self.threads.append(threading.get_ident())
        return RESPONSE


def test_threaded_models_run_the_sync_client_off_the_event_loop_each_run():
    sync = RecordingSyncModels()
    models = ThreadedModels(SimpleNamespace(models=sync))

    for _ in range(2):
        result = asyncio.run(
            models.generate_content(model="m", contents="ping", config=None)
        )
        assert result is RESPONSE

    assert sync.calls == [("m", "ping", None), ("m", "ping", None)]
    assert threading.get_ident() not in sync.threads


@pytest.mark.live
def test_live_gateway_answers_in_two_event_loops():
    settings = load_settings(os.environ)
    gateway = ModelGateway(settings.models, build_vertex_clients(settings))

    for _ in range(2):
        response = asyncio.run(gateway.generate("fast", "Reply with the word ok."))
        assert response.text is not None
