from pathlib import Path

import pytest
import yaml
from conftest import REPO

CONFIG_PATH = REPO / "cloudbuild.yaml"
STEP_IDS = ["api-gate", "web-gate", "image", "deploy-api", "deploy-hosting", "verify"]


@pytest.fixture(scope="module")
def config() -> dict:
    return yaml.safe_load(CONFIG_PATH.read_text())


@pytest.fixture(scope="module")
def steps(config) -> dict[str, dict]:
    return {step["id"]: step for step in config["steps"]}


def command_text(step: dict) -> str:
    return " ".join([step.get("entrypoint", ""), *map(str, step.get("args", []))])


def test_steps_exist_in_order(config):
    assert [step["id"] for step in config["steps"]] == STEP_IDS


def test_gates_start_in_parallel(steps):
    assert steps["api-gate"]["waitFor"] == ["-"]
    assert steps["web-gate"]["waitFor"] == ["-"]


def test_dependency_graph(steps):
    assert steps["image"]["waitFor"] == ["api-gate"]
    assert sorted(steps["deploy-api"]["waitFor"]) == ["image", "web-gate"]
    assert steps["deploy-hosting"]["waitFor"] == ["deploy-api"]
    assert steps["verify"]["waitFor"] == ["deploy-hosting"]


def test_every_wait_for_names_a_real_step(steps):
    for step in steps.values():
        for dependency in step["waitFor"]:
            assert dependency == "-" or dependency in steps


def test_api_gate_runs_lint_format_and_tests_frozen(steps):
    text = command_text(steps["api-gate"])
    for part in ("uv sync --frozen", "ruff check", "ruff format --check", "pytest"):
        assert part in text
    assert steps["api-gate"]["dir"] == "services/api"


def test_web_gate_runs_every_check_then_builds(steps):
    text = command_text(steps["web-gate"])
    commands = [
        "bun install --frozen-lockfile",
        "bun run check",
        "bun run typecheck",
        "bun run test",
        "bun run build",
    ]
    positions = [text.index(command) for command in commands]
    assert positions == sorted(positions)
    assert steps["web-gate"]["dir"] == "apps/web"


def test_web_gate_writes_env_production_from_the_two_secrets(steps):
    step = steps["web-gate"]
    assert sorted(step["secretEnv"]) == ["FIREBASE_WEB_CONFIG", "MAPS_KEY"]
    text = command_text(step)
    assert ".env.production" in text
    assert "$$MAPS_KEY" in text
    assert "$$FIREBASE_WEB_CONFIG" in text
    assert "echo" not in text


def test_available_secrets_map_both_secrets(config):
    secrets = config["availableSecrets"]["secretManager"]
    mapped = {item["env"]: item["versionName"] for item in secrets}
    assert mapped == {
        "MAPS_KEY": "projects/$PROJECT_ID/secrets/maps-key/versions/latest",
        "FIREBASE_WEB_CONFIG": "projects/$PROJECT_ID/secrets/firebase-web-config/versions/latest",
    }


def test_image_is_built_with_the_git_sha_and_pushed_by_a_step(steps, config):
    text = command_text(steps["image"])
    assert "--build-arg GIT_SHA=$SHORT_SHA" in text
    assert "-f services/api/Dockerfile" in text
    assert "${_REGION}-docker.pkg.dev/$PROJECT_ID/bara/bara-api:$SHORT_SHA" in text
    assert "docker push" in text or "push" in steps["image"]["args"]
    assert "images" not in config


def test_deploy_api_changes_only_the_image(steps):
    text = command_text(steps["deploy-api"])
    assert "gcloud run deploy bara-api" in text
    assert "--image" in text
    assert "--region $_REGION" in text or "--region=$_REGION" in text
    for flag in (
        "--min",
        "--max",
        "--memory",
        "--service-account",
        "--allow-unauthenticated",
    ):
        assert flag not in text


def test_deploy_hosting_pins_firebase_tools_and_uses_no_token(steps):
    text = command_text(steps["deploy-hosting"])
    assert "firebase-tools@" in text
    assert "latest" not in text
    assert "deploy --only hosting" in text
    assert "--project $PROJECT_ID" in text
    assert "--non-interactive" in text
    assert "--token" not in text
    assert steps["deploy-hosting"]["dir"] == "apps/web"


def test_verify_checks_the_deployed_git_sha_through_hosting(steps):
    text = command_text(steps["verify"])
    assert "https://$PROJECT_ID.web.app/api/health" in text
    assert "git_sha" in text
    assert "$SHORT_SHA" in text
    assert "--max-time" in text
    assert text.rstrip().endswith("exit 1")


def test_logging_is_cloud_logging_only_and_machine_is_default(config):
    assert config["options"]["logging"] == "CLOUD_LOGGING_ONLY"
    assert "machineType" not in config["options"]


def test_region_substitution_and_timeout(config):
    assert config["substitutions"] == {"_REGION": "asia-southeast1"}
    assert config["timeout"] == "1200s"


def test_images_are_pinned_not_latest(steps):
    for step in steps.values():
        assert not step["name"].endswith(":latest")
        assert ":" in step["name"] or step["name"].endswith("/docker")


def test_no_secret_looking_value_is_committed():
    text = Path(CONFIG_PATH).read_text()
    assert "AIza" not in text
