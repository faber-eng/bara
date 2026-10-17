from pathlib import Path

import pytest

from config import ConfigError, load_settings

REPO_CONFIG_DIR = Path(__file__).resolve().parents[3] / "config"
BASE_ENV = {"GOOGLE_CLOUD_PROJECT": "example-project"}

VALID_MODELS_YAML = """
reasoning:
  model: r-model
  location: global
  fallback: r-backup
fast:
  model: f-model
  location: global
  fallback: f-backup
"""


def write_models_yaml(directory: Path, text: str) -> Path:
    (directory / "models.yaml").write_text(text)
    return directory


def test_reads_model_ids_from_the_repo_models_yaml():
    settings = load_settings(BASE_ENV, REPO_CONFIG_DIR)

    assert settings.models.reasoning.model == "gemini-3.1-pro-preview"
    assert settings.models.reasoning.fallback == "gemini-2.5-pro"
    assert settings.models.fast.model == "gemini-3.5-flash"
    assert settings.models.fast.fallback == "gemini-2.5-flash"
    assert settings.models.fast.location == "global"


def test_default_config_dir_is_the_repo_config():
    settings = load_settings(BASE_ENV)

    assert settings.models.reasoning.model == "gemini-3.1-pro-preview"


def test_config_dir_comes_from_bara_config_dir(tmp_path):
    write_models_yaml(tmp_path, VALID_MODELS_YAML)

    settings = load_settings({**BASE_ENV, "BARA_CONFIG_DIR": str(tmp_path)})

    assert settings.models.reasoning.model == "r-model"


def test_empty_bara_config_dir_uses_the_repo_config():
    settings = load_settings({**BASE_ENV, "BARA_CONFIG_DIR": ""})

    assert settings.models.reasoning.model == "gemini-3.1-pro-preview"


def test_env_override_replaces_only_the_model_id():
    settings = load_settings(
        {**BASE_ENV, "REASONING_MODEL": "gemini-3.5-flash"}, REPO_CONFIG_DIR
    )

    assert settings.models.reasoning.model == "gemini-3.5-flash"
    assert settings.models.reasoning.fallback == "gemini-2.5-pro"
    assert settings.models.fast.model == "gemini-3.5-flash"


def test_fast_model_override():
    settings = load_settings(
        {**BASE_ENV, "FAST_MODEL": "gemini-2.5-flash"}, REPO_CONFIG_DIR
    )

    assert settings.models.fast.model == "gemini-2.5-flash"


@pytest.mark.parametrize("variable", ["REASONING_MODEL", "FAST_MODEL"])
def test_empty_override_is_an_error_naming_the_variable(variable):
    with pytest.raises(ConfigError, match=variable):
        load_settings({**BASE_ENV, variable: "  "}, REPO_CONFIG_DIR)


@pytest.mark.parametrize("environ", [{}, {"GOOGLE_CLOUD_PROJECT": ""}])
def test_missing_project_is_an_error(environ):
    with pytest.raises(ConfigError, match="GOOGLE_CLOUD_PROJECT"):
        load_settings(environ, REPO_CONFIG_DIR)


@pytest.mark.parametrize("environ", [BASE_ENV, {**BASE_ENV, "GIT_SHA": ""}])
def test_git_sha_defaults_to_unknown(environ):
    assert load_settings(environ, REPO_CONFIG_DIR).git_sha == "unknown"


def test_git_sha_comes_from_the_environment():
    settings = load_settings({**BASE_ENV, "GIT_SHA": "fe23bb1"}, REPO_CONFIG_DIR)

    assert settings.git_sha == "fe23bb1"


def test_missing_models_yaml_is_an_error(tmp_path):
    with pytest.raises(ConfigError, match="models.yaml"):
        load_settings(BASE_ENV, tmp_path)


def test_malformed_yaml_is_an_error(tmp_path):
    write_models_yaml(tmp_path, "reasoning: [unclosed")

    with pytest.raises(ConfigError, match="models.yaml"):
        load_settings(BASE_ENV, tmp_path)


def test_models_yaml_missing_a_field_is_an_error(tmp_path):
    write_models_yaml(tmp_path, VALID_MODELS_YAML.replace("  fallback: f-backup\n", ""))

    with pytest.raises(ConfigError, match="models.yaml"):
        load_settings(BASE_ENV, tmp_path)


def test_models_yaml_that_is_not_a_mapping_is_an_error(tmp_path):
    write_models_yaml(tmp_path, "- just\n- a list\n")

    with pytest.raises(ConfigError, match="models.yaml"):
        load_settings(BASE_ENV, tmp_path)
