import re
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml
from conftest import PROJECT, REGION, REPO

THIS_SHA = "bbbbbbb"
NEWER_SHA = "ccccccc"
OLDER_SHA = "aaaaaaa"
UNRELATED_SHA = "ddddddd"

CURL_STUB = """#!/usr/bin/env bash
if [[ -z "${STUB_LIVE:-}" ]]; then exit 22; fi
printf '{"status":"ok","git_sha":"%s"}' "$STUB_LIVE"
"""
GCLOUD_STUB = """#!/usr/bin/env bash
printf '%s\\n' "$*" >> "$STUB_LOG"
printf '%s' "$STUB_IMAGES"
"""
SLEEP_STUB = "#!/usr/bin/env bash\nexit 0\n"


@pytest.fixture(scope="module")
def script() -> str:
    config = yaml.safe_load((REPO / "cloudbuild.yaml").read_text())
    step = next(s for s in config["steps"] if s["id"] == "verify")
    text = step["args"][-1]
    return (
        text.replace("$$", "\0")
        .replace("${_REGION}", REGION)
        .replace("$PROJECT_ID", PROJECT)
        .replace("$SHORT_SHA", THIS_SHA)
        .replace("\0", "$")
    )


@pytest.fixture
def stub_bin(tmp_path: Path) -> Path:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for name, body in (
        ("curl", CURL_STUB),
        ("gcloud", GCLOUD_STUB),
        ("sleep", SLEEP_STUB),
    ):
        path = bin_dir / name
        path.write_text(body)
        path.chmod(0o755)
    return bin_dir


@pytest.fixture
def run_verify(script, stub_bin, tmp_path):
    def run(live: str, images: dict[str, int]):
        log = tmp_path / "gcloud.log"
        log.write_text("")
        env = {
            "PATH": f"{stub_bin}:/usr/bin:/bin",
            "STUB_LIVE": live,
            "STUB_IMAGES": "".join(f"{t},{s}.5\n" for t, s in images.items()),
            "STUB_LOG": str(log),
        }
        done = subprocess.run(
            [shutil.which("bash"), "-c", script],
            check=False,
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
        )
        return done.returncode, done.stderr, log.read_text().splitlines()

    return run


def test_passes_when_the_live_sha_is_this_build(run_verify):
    code, _, gcloud_calls = run_verify(THIS_SHA, {})

    assert code == 0
    assert gcloud_calls == []


def test_passes_when_the_live_sha_was_pushed_after_this_build(run_verify):
    code, _, _ = run_verify(NEWER_SHA, {THIS_SHA: 1000, NEWER_SHA: 1200})

    assert code == 0


def test_fails_when_the_live_sha_was_pushed_before_this_build(run_verify):
    code, err, _ = run_verify(OLDER_SHA, {THIS_SHA: 1000, OLDER_SHA: 800})

    assert code == 1
    assert THIS_SHA in err


def test_fails_when_the_live_sha_has_no_image_in_the_repository(run_verify):
    code, _, _ = run_verify(UNRELATED_SHA, {THIS_SHA: 1000})

    assert code == 1


def test_fails_when_this_builds_own_image_is_missing(run_verify):
    code, _, _ = run_verify(NEWER_SHA, {NEWER_SHA: 1200})

    assert code == 1


def test_fails_when_both_images_share_one_push_time(run_verify):
    code, _, _ = run_verify(NEWER_SHA, {THIS_SHA: 1000, NEWER_SHA: 1000})

    assert code == 1


def test_fails_when_the_health_route_cannot_be_read(run_verify):
    code, _, gcloud_calls = run_verify("", {THIS_SHA: 1000})

    assert code == 1
    assert gcloud_calls == []


def test_lists_the_bara_api_images_with_their_tags_in_the_build_project(
    run_verify,
):
    _, _, gcloud_calls = run_verify(NEWER_SHA, {THIS_SHA: 1000, NEWER_SHA: 1200})

    assert gcloud_calls
    assert f"{REGION}-docker.pkg.dev/{PROJECT}/bara/bara-api" in gcloud_calls[0]
    assert "--include-tags" in gcloud_calls[0]
    assert f"--project={PROJECT}" in gcloud_calls[0]


def test_only_cloud_build_substitutions_are_left_unescaped():
    config = yaml.safe_load((REPO / "cloudbuild.yaml").read_text())
    step = next(s for s in config["steps"] if s["id"] == "verify")
    unescaped = step["args"][-1].replace("$$", "")

    assert re.findall(r"\$(?!PROJECT_ID|SHORT_SHA|\{_REGION\})", unescaped) == []
