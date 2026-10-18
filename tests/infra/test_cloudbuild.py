import os
import subprocess
from pathlib import Path

import pytest
import yaml
from conftest import REPO

CONFIG_PATH = REPO / "cloudbuild.yaml"
GUARD = REPO / "ci" / "guard.sh"
STEP_IDS = [
    "stamp",
    "api-gate",
    "pipelines-gate",
    "web-gate",
    "image",
    "image-jobs",
    "deploy-jobs",
    "deploy-api",
    "guard-hosting",
    "deploy-hosting",
    "verify",
]


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
    assert steps["stamp"]["waitFor"] == ["-"]
    assert steps["api-gate"]["waitFor"] == ["-"]
    assert steps["pipelines-gate"]["waitFor"] == ["-"]
    assert steps["web-gate"]["waitFor"] == ["-"]


def test_dependency_graph(steps):
    assert sorted(steps["image"]["waitFor"]) == ["api-gate", "pipelines-gate"]
    assert sorted(steps["deploy-api"]["waitFor"]) == ["image", "stamp", "web-gate"]
    assert steps["guard-hosting"]["waitFor"] == ["deploy-api"]
    assert steps["deploy-hosting"]["waitFor"] == ["guard-hosting"]
    assert steps["verify"]["waitFor"] == ["deploy-hosting"]


def descendants(steps, root: str) -> set[str]:
    found = {root}
    changed = True
    while changed:
        changed = False
        for step_id, step in steps.items():
            if step_id not in found and found & set(step["waitFor"]):
                found.add(step_id)
                changed = True
    return found


def test_jobs_path_hangs_off_the_pipelines_gate_only(steps):
    assert steps["image-jobs"]["waitFor"] == ["pipelines-gate"]
    assert sorted(steps["deploy-jobs"]["waitFor"]) == ["image-jobs", "stamp"]


def test_nothing_waits_for_the_jobs_path(steps):
    jobs_path = {"image-jobs", "deploy-jobs"}
    for step_id, step in steps.items():
        if step_id not in jobs_path:
            assert not jobs_path & set(step["waitFor"]), step_id
    assert descendants(steps, "image-jobs") == jobs_path


def test_a_failing_jobs_path_does_not_fail_the_build(steps):
    assert steps["image-jobs"]["allowFailure"] is True
    assert steps["deploy-jobs"]["allowFailure"] is True
    for step_id in ("deploy-api", "guard-hosting", "deploy-hosting", "verify"):
        assert "allowFailure" not in steps[step_id]


def test_image_jobs_builds_from_the_pipelines_dockerfile_and_pushes_the_sha_tag(steps):
    text = command_text(steps["image-jobs"])
    assert "-f services/pipelines/Dockerfile" in text
    assert "${_REGION}-docker.pkg.dev/$PROJECT_ID/bara/bara-jobs:$SHORT_SHA" in text
    assert "docker push" in text


def test_deploy_jobs_runs_the_weekly_job_as_bara_jobs_on_the_new_image(steps):
    text = command_text(steps["deploy-jobs"])
    assert "gcloud run jobs deploy bara-drying" in text
    assert (
        "--image=${_REGION}-docker.pkg.dev/$PROJECT_ID/bara/bara-jobs:$SHORT_SHA"
        in text
    )
    assert "--service-account=bara-jobs@$PROJECT_ID.iam.gserviceaccount.com" in text
    assert "--args=jobs.weekly_rankings,--region,riau,--region,congo_cuvette" in text
    assert "--max-retries=0" in text
    assert "--allow-unauthenticated" not in text


def test_deploy_jobs_also_runs_the_daily_reignition_job(steps):
    text = command_text(steps["deploy-jobs"])
    reignition = text.index("gcloud run jobs deploy bara-reignition")
    assert "--args=jobs.daily_reignition,--region,riau" in text[reignition:]
    assert (
        "--service-account=bara-jobs@$PROJECT_ID.iam.gserviceaccount.com"
        in text[reignition:]
    )
    guard = "bash ci/guard.sh jobs bara-reignition $_REGION $PROJECT_ID"
    assert text.index(guard) < reignition
    assert text.index("superseded-bara-reignition") < reignition


def test_a_superseded_drying_job_does_not_skip_the_reignition_deploy(steps):
    text = command_text(steps["deploy-jobs"])
    drying_skip = text[: text.index("gcloud run jobs deploy bara-reignition")]
    assert "exit 0" not in drying_skip


def test_every_wait_for_names_a_real_step(steps):
    for step in steps.values():
        for dependency in step["waitFor"]:
            assert dependency == "-" or dependency in steps


def test_api_gate_runs_lint_format_and_tests_frozen(steps):
    text = command_text(steps["api-gate"])
    for part in ("uv sync --frozen", "ruff check", "ruff format --check", "pytest"):
        assert part in text
    assert steps["api-gate"]["dir"] == "services/api"


def test_pipelines_gate_runs_lint_format_and_tests_frozen(steps):
    text = command_text(steps["pipelines-gate"])
    for part in ("uv sync --frozen", "ruff check", "ruff format --check", "pytest"):
        assert part in text
    assert steps["pipelines-gate"]["dir"] == "services/pipelines"


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


def test_web_gate_points_the_stream_client_at_the_cloud_run_url(config, steps):
    assert config["substitutions"]["_STREAM_BASE"].startswith("https://bara-api-")
    text = command_text(steps["web-gate"])
    assert "VITE_STREAM_BASE=%s" in text
    assert '"$_STREAM_BASE" >> .env.production' in text


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


def test_stamp_records_the_build_start_time_in_the_workspace(steps):
    text = command_text(steps["stamp"])
    assert "date +%s%N > /workspace/build-started" in text


@pytest.mark.parametrize(
    ("step_id", "target"),
    [
        ("deploy-jobs", "jobs bara-drying"),
        ("deploy-jobs", "jobs bara-reignition"),
        ("deploy-api", "services bara-api"),
    ],
)
def test_each_deploy_runs_the_guard_before_deploying(steps, step_id, target):
    text = command_text(steps[step_id])
    kind, name = target.split()
    guard = f"bash ci/guard.sh {target} $_REGION $PROJECT_ID"
    deploy = text.index(f"gcloud run {deploy_verb(kind)} {name}")
    assert text.index(guard) < text.index(f"superseded-{name}") < deploy
    assert "build_started=$$(cat /workspace/build-started)" in text[deploy:]


def deploy_verb(kind):
    if kind == "jobs":
        return "jobs deploy"
    return "deploy"


def test_job_deploys_stamp_with_labels_since_jobs_deploy_has_no_update_labels(
    steps,
):
    text = command_text(steps["deploy-jobs"])
    assert text.count("--labels=build_started=") == 2
    assert "--update-labels" not in text


def test_the_api_deploy_keeps_its_other_labels(steps):
    assert "--update-labels=build_started=" in command_text(steps["deploy-api"])


def test_hosting_is_guarded_and_skips_when_the_api_was_superseded(steps):
    guard = command_text(steps["guard-hosting"])
    assert "bash ci/guard.sh services bara-api $_REGION $PROJECT_ID" in guard
    deploy = command_text(steps["deploy-hosting"])
    assert deploy.index("superseded-bara-api") < deploy.index("firebase-tools")
    assert "exit 0" in deploy


def test_verify_accepts_a_superseded_skip_as_success(steps):
    text = command_text(steps["verify"])
    assert text.index("superseded-bara-api") < text.index("for attempt")
    assert "skipped, superseded" in text
    assert text.index("exit 0") < text.index("for attempt")


MISSING_RESOURCE_GCLOUD = """#!/usr/bin/env bash
if [ "$3" = describe ]; then
  echo "ERROR: (gcloud.run.jobs.describe) Cannot find job [$4]." >&2
  exit 1
fi
"""


def run_guard(tmp_path, live_label, started="200", args=None, fake_script=None):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    fake = bin_dir / "gcloud"
    fake.write_text(fake_script or f"#!/usr/bin/env bash\nprintf '%s' '{live_label}'\n")
    fake.chmod(0o755)
    (tmp_path / "build-started").write_text(started + "\n")
    env = {
        **os.environ,
        "PATH": f"{bin_dir}:{os.environ['PATH']}",
        "GUARD_DIR": str(tmp_path),
    }
    command = ["bash", str(GUARD), *(args or ["services", "bara-api", "r", "p"])]
    return subprocess.run(command, env=env, capture_output=True, text=True)


def test_guard_marks_the_deploy_superseded_when_live_started_later(tmp_path):
    result = run_guard(tmp_path, live_label="300")
    assert result.returncode == 0
    assert "SUPERSEDED" in result.stdout
    assert (tmp_path / "superseded-bara-api").exists()


@pytest.mark.parametrize("live_label", ["100", "200", ""])
def test_guard_lets_an_equal_older_or_first_deploy_through(tmp_path, live_label):
    result = run_guard(tmp_path, live_label=live_label)
    assert result.returncode == 0
    assert "SUPERSEDED" not in result.stdout
    assert not (tmp_path / "superseded-bara-api").exists()


def test_guard_lets_the_first_deploy_of_a_job_that_does_not_exist_through(tmp_path):
    result = run_guard(
        tmp_path,
        live_label="",
        args=["jobs", "bara-reignition", "r", "p"],
        fake_script=MISSING_RESOURCE_GCLOUD,
    )
    assert result.returncode == 0
    assert "guard ok" in result.stdout
    assert not (tmp_path / "superseded-bara-reignition").exists()


def test_guard_without_arguments_is_a_usage_error(tmp_path):
    result = run_guard(tmp_path, live_label="", args=["services"])
    assert result.returncode == 2


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
    assert config["substitutions"]["_REGION"] == "asia-southeast1"
    assert config["timeout"] == "1200s"


def test_images_are_pinned_not_latest(steps):
    for step in steps.values():
        assert not step["name"].endswith(":latest")
        assert ":" in step["name"] or step["name"].endswith("/docker")


def test_no_secret_looking_value_is_committed():
    text = Path(CONFIG_PATH).read_text()
    assert "AIza" not in text
