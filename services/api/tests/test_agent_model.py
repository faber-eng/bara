from pathlib import Path

import pytest

from adapters.gemini import FALLBACK_STATUS_CODES, build_agent_model, build_http_options
from config import ConfigError, load_settings

REPO_CONFIG_DIR = Path(__file__).resolve().parents[3] / "config"
ENTERPRISE = {"GOOGLE_GENAI_USE_ENTERPRISE": "True"}


def test_the_agent_model_is_the_reasoning_route_with_its_fallback(settings):
    model = build_agent_model(settings, ENTERPRISE)

    primary, backup = model.models
    assert (primary.model, backup.model) == ("reasoning-primary", "reasoning-backup")
    assert model.model == "reasoning-primary"
    assert model.retriable_status_codes == FALLBACK_STATUS_CODES == {404, 429}


def test_each_agent_model_calls_vertex_in_the_project_and_route_location(settings):
    model = build_agent_model(settings, ENTERPRISE)

    for gemini in model.models:
        kwargs = gemini.client_kwargs
        assert kwargs["enterprise"] is True
        assert kwargs["project"] == "example-project"
        assert kwargs["location"] == "global"
        assert kwargs["http_options"] == build_http_options()


def test_reasoning_model_override_reaches_the_agent():
    settings = load_settings(
        {"GOOGLE_CLOUD_PROJECT": "p", "REASONING_MODEL": "gemini-3.5-flash"},
        REPO_CONFIG_DIR,
    )

    model = build_agent_model(settings, ENTERPRISE)

    assert model.models[0].model == "gemini-3.5-flash"


@pytest.mark.parametrize("environ", [{}, {"GOOGLE_GENAI_USE_ENTERPRISE": "False"}])
def test_without_enterprise_mode_the_agent_model_is_a_config_error(settings, environ):
    with pytest.raises(ConfigError, match="GOOGLE_GENAI_USE_ENTERPRISE"):
        build_agent_model(settings, environ)
