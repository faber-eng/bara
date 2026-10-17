import google.auth
import pytest
from google.auth.credentials import AnonymousCredentials

from adapters.factory import build_adapters


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
