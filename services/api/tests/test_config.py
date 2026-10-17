from pathlib import Path

import pytest

from config import ConfigError, load_settings, region_timezones

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


VALID_APP_YAML = """
grid_cell_m: 1000
languages: { default: id }
tasks:
  default_deadline_hours: { dam_check: 72, dam_repair: 168, patrol_recheck: 24 }
  human_review_confidence: 0.7
  location_tolerance_m: 300
judge_mode: { enabled: false, max_resets_per_hour: 5 }
agent: { max_llm_calls: 12, max_cases_per_trigger: 3 }
reignition: { recheck_spots_per_fire: 3, recheck_after_hours: 48 }
"""


def write_models_yaml(directory: Path, text: str) -> Path:
    (directory / "models.yaml").write_text(text)
    (directory / "app.yaml").write_text(VALID_APP_YAML)
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


def test_judge_mode_comes_from_the_repo_app_yaml():
    settings = load_settings(BASE_ENV, REPO_CONFIG_DIR)

    assert settings.judge_mode.enabled is True
    assert settings.judge_mode.max_resets_per_hour == 20


@pytest.mark.parametrize(("value", "enabled"), [("0", False), ("1", True)])
def test_bara_judge_mode_overrides_the_yaml(tmp_path, value, enabled):
    write_models_yaml(tmp_path, VALID_MODELS_YAML)

    settings = load_settings(
        {**BASE_ENV, "BARA_JUDGE_MODE": value}, config_dir=tmp_path
    )

    assert settings.judge_mode.enabled is enabled


@pytest.mark.parametrize("value", ["", "true", "2", "yes"])
def test_bara_judge_mode_must_be_0_or_1(tmp_path, value):
    write_models_yaml(tmp_path, VALID_MODELS_YAML)

    with pytest.raises(ConfigError, match="BARA_JUDGE_MODE"):
        load_settings({**BASE_ENV, "BARA_JUDGE_MODE": value}, config_dir=tmp_path)


def test_missing_app_yaml_is_an_error(tmp_path):
    write_models_yaml(tmp_path, VALID_MODELS_YAML)
    (tmp_path / "app.yaml").unlink()

    with pytest.raises(ConfigError, match="app.yaml"):
        load_settings(BASE_ENV, config_dir=tmp_path)


def test_app_yaml_without_judge_mode_is_an_error(tmp_path):
    write_models_yaml(tmp_path, VALID_MODELS_YAML)
    (tmp_path / "app.yaml").write_text(
        VALID_APP_YAML.replace(
            "judge_mode: { enabled: false, max_resets_per_hour: 5 }\n", ""
        )
    )

    with pytest.raises(ConfigError, match="app.yaml"):
        load_settings(BASE_ENV, config_dir=tmp_path)


def test_region_defaults_and_api_url_is_optional():
    settings = load_settings(BASE_ENV, REPO_CONFIG_DIR)

    assert settings.region == "asia-southeast1"
    assert settings.api_url is None


def test_region_and_api_url_come_from_the_environment():
    settings = load_settings(
        {**BASE_ENV, "REGION": "asia-southeast2", "BARA_API_URL": "https://api.test"},
        REPO_CONFIG_DIR,
    )

    assert settings.region == "asia-southeast2"
    assert settings.api_url == "https://api.test"


def test_resource_names_derive_from_the_project():
    settings = load_settings(BASE_ENV, REPO_CONFIG_DIR)

    assert settings.evidence_bucket == "example-project-bara-evidence"
    assert (
        settings.tasks_invoker_email
        == "bara-tasks-invoker@example-project.iam.gserviceaccount.com"
    )


def test_samples_dir_defaults_to_the_repo_data_samples():
    settings = load_settings(BASE_ENV, REPO_CONFIG_DIR)

    assert settings.samples_dir == REPO_CONFIG_DIR.parent / "data" / "samples"


def test_samples_dir_comes_from_the_environment(tmp_path):
    env = {**BASE_ENV, "BARA_SAMPLES_DIR": str(tmp_path)}

    assert load_settings(env, REPO_CONFIG_DIR).samples_dir == tmp_path


def test_the_full_flow_region_is_riau():
    from config import full_flow_region

    assert full_flow_region(REPO_CONFIG_DIR) == "riau"


def test_no_full_flow_region_is_a_config_error(tmp_path):
    from config import full_flow_region

    (tmp_path / "regions.yaml").write_text("a:\n  full_flow: false\n")

    with pytest.raises(ConfigError):
        full_flow_region(tmp_path)


def test_two_full_flow_regions_are_a_config_error(tmp_path):
    from config import full_flow_region

    (tmp_path / "regions.yaml").write_text(
        "a:\n  full_flow: true\nb:\n  full_flow: true\n"
    )

    with pytest.raises(ConfigError):
        full_flow_region(tmp_path)


def test_agent_bounds_and_grid_size_come_from_the_repo_app_yaml():
    settings = load_settings(BASE_ENV, REPO_CONFIG_DIR)

    assert settings.agent.max_llm_calls == 12
    assert settings.agent.max_cases_per_trigger == 3
    assert settings.grid_cell_m == 1000


@pytest.mark.parametrize(
    "line",
    ["agent: { max_llm_calls: 12, max_cases_per_trigger: 3 }\n", "grid_cell_m: 1000\n"],
)
def test_app_yaml_without_agent_bounds_or_grid_size_is_an_error(tmp_path, line):
    write_models_yaml(tmp_path, VALID_MODELS_YAML)
    (tmp_path / "app.yaml").write_text(VALID_APP_YAML.replace(line, ""))

    with pytest.raises(ConfigError, match="app.yaml"):
        load_settings(BASE_ENV, config_dir=tmp_path)


def test_max_llm_calls_must_be_positive(tmp_path):
    write_models_yaml(tmp_path, VALID_MODELS_YAML)
    (tmp_path / "app.yaml").write_text(
        VALID_APP_YAML.replace("max_llm_calls: 12", "max_llm_calls: 0")
    )

    with pytest.raises(ConfigError, match="app.yaml"):
        load_settings(BASE_ENV, config_dir=tmp_path)


def test_scenario_dir_defaults_to_repo_data_and_follows_the_variable():
    from pathlib import Path

    from config import resolve_scenario_dir

    assert resolve_scenario_dir({}).name == "data"
    assert resolve_scenario_dir({"BARA_SCENARIO_DIR": "/app/scenario"}) == Path(
        "/app/scenario"
    )


def test_task_settings_come_from_the_repo_app_yaml():
    settings = load_settings(BASE_ENV, REPO_CONFIG_DIR)

    assert settings.tasks.default_deadline_hours == {
        "dam_check": 72,
        "dam_repair": 168,
        "patrol_recheck": 24,
    }
    assert settings.tasks.human_review_confidence == 0.7
    assert settings.tasks.location_tolerance_m == 300
    assert settings.default_language == "id"


def test_a_task_type_without_a_default_deadline_is_an_error(tmp_path):
    write_models_yaml(tmp_path, VALID_MODELS_YAML)
    (tmp_path / "app.yaml").write_text(
        VALID_APP_YAML.replace(", patrol_recheck: 24", "")
    )

    with pytest.raises(ConfigError, match="app.yaml"):
        load_settings(BASE_ENV, config_dir=tmp_path)


def test_a_zero_default_deadline_is_an_error(tmp_path):
    write_models_yaml(tmp_path, VALID_MODELS_YAML)
    (tmp_path / "app.yaml").write_text(
        VALID_APP_YAML.replace("dam_check: 72", "dam_check: 0")
    )

    with pytest.raises(ConfigError, match="app.yaml"):
        load_settings(BASE_ENV, config_dir=tmp_path)


def test_region_timezones_come_from_regions_yaml():
    assert region_timezones(REPO_CONFIG_DIR) == {
        "riau": "Asia/Jakarta",
        "congo_cuvette": "Africa/Brazzaville",
    }


def test_a_region_without_a_timezone_is_a_config_error(tmp_path):
    (tmp_path / "regions.yaml").write_text("riau: { name: Riau }\n")

    with pytest.raises(ConfigError, match="timezone"):
        region_timezones(tmp_path)


def test_an_unknown_timezone_is_a_config_error(tmp_path):
    (tmp_path / "regions.yaml").write_text("riau: { timezone: Mars/Base }\n")

    with pytest.raises(ConfigError, match="timezone"):
        region_timezones(tmp_path)


def test_a_default_deadline_past_the_cloud_tasks_limit_is_an_error(tmp_path):
    write_models_yaml(tmp_path, VALID_MODELS_YAML)
    (tmp_path / "app.yaml").write_text(
        VALID_APP_YAML.replace("dam_repair: 168", "dam_repair: 721")
    )

    with pytest.raises(ConfigError, match="app.yaml"):
        load_settings(BASE_ENV, config_dir=tmp_path)


def test_the_repo_config_gives_three_rechecks_after_48_hours():
    settings = load_settings(BASE_ENV, REPO_CONFIG_DIR)

    assert settings.reignition.recheck_spots_per_fire == 3
    assert settings.reignition.recheck_after_hours == 48
