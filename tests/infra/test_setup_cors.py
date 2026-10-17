import json

from conftest import PROJECT

SCRIPT = "infra/setup.sh"
ORIGINS = [
    f"https://{PROJECT}.web.app",
    f"https://{PROJECT}.firebaseapp.com",
    "http://localhost:5173",
]
SIGNED_HEADER = "x-goog-content-length-range"
OLD_CORS = f"[{{'method': ['PUT', 'GET'], 'origin': {ORIGINS}, 'responseHeader': ['Content-Type']}}]"
NEW_CORS = OLD_CORS.replace(
    "['Content-Type']", f"['Content-Type', '{SIGNED_HEADER}']"
)


def cors_states(run_script, cors):
    result = run_script(SCRIPT, "--project", PROJECT, "--dry-run", cors=cors)
    return result.states_of("bucket-cors", "evidence")


def written_cors(run_script, cors):
    result = run_script(SCRIPT, "--project", PROJECT, cors=cors)
    lines = [c for c in result.calls if c.startswith("CORS_FILE ")]
    assert len(lines) == 1
    return json.loads(lines[0].removeprefix("CORS_FILE "))


def test_a_bucket_with_the_old_cors_is_updated(run_script):
    assert cors_states(run_script, OLD_CORS) == ["would make"]


def test_a_bucket_with_the_signed_header_cors_is_left_alone(run_script):
    assert cors_states(run_script, NEW_CORS) == ["ok"]


def test_the_written_cors_allows_put_and_get_with_both_headers(run_script):
    [rule] = written_cors(run_script, OLD_CORS)

    assert rule["method"] == ["PUT", "GET"]
    assert rule["responseHeader"] == ["Content-Type", SIGNED_HEADER]
    assert rule["origin"] == ORIGINS
