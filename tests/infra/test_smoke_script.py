import json
import os
import shutil
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from conftest import REPO

SCRIPT = str(REPO / "scripts/smoke_test.sh")
CASE = "case-1"
SECOND = "case-2"


class FakeBara:
    def __init__(
        self,
        advance=200,
        verdict="broken",
        trigger=202,
        cases_ready=True,
        real_case=False,
        sample=200,
        old_verdict=False,
        stale=False,
    ):
        self.stale = stale
        self.triggered = False
        self.real_case = real_case
        self.sample = sample
        self.old_verdict = old_verdict
        self.advance = advance
        self.verdict = verdict
        self.trigger = trigger
        self.cases_ready = cases_ready
        self.calls: list[tuple[str, str, str | None]] = []
        self.advanced = False

    def respond(self, method, path, role, body=b""):
        self.last_body = body
        self.calls.append((method, path, role))
        if path == "/api/health":
            return 200, {"status": "ok", "git_sha": "abc1234"}
        if path == "/api/judge/reset":
            return 200, {"now": "2026-07-20T01:00:00Z", "offset_seconds": 0, "judge_mode": True}
        if path == "/api/judge/trigger":
            self.triggered = True
            return self.trigger, {"event": "drying.ranked", "message_id": "m1"}
        if path.startswith("/api/cases?"):
            return 200, self.case_list()
        if path == f"/api/cases/{CASE}":
            return 200, self.detail()
        if path == f"/api/cases/{SECOND}":
            return 200, self.second_detail()
        if path == "/api/clock":
            return 200, {"now": "2026-07-20T01:00:00Z", "offset_seconds": 0, "judge_mode": True}
        if path == "/api/samples/broken-dam-1/file":
            return self.sample, b"\xff\xd8\xff\xe0jpegbytes"
        if path == "/api/v/vol-ari/uploads":
            return 200, {
                "evidence_id": "e1",
                "upload_url": f"{self.base}/put/e1",
                "headers": {"Content-Type": "image/jpeg"},
            }
        if path == "/put/e1":
            return 200, b""
        if path == "/api/v/vol-ari/evidence/e1/complete":
            return 200, {"id": "e1"}
        if path == "/api/judge/advance":
            self.advanced = self.advance == 200
            self.advance_body = json.loads(self.last_body or b"{}")
            hours = self.advance_body.get("hours", 0)
            return self.advance, {"now": "x", "offset_seconds": hours * 3600, "judge_mode": True}
        return 404, {"detail": "no"}

    def case_list(self):
        status = "escalated" if self.advanced else "assigned"
        if not self.cases_ready:
            return []
        rows = []
        if self.triggered or self.stale:
            rows = [
                {
                    "case": {"id": CASE, "status": "assigned", "example": True},
                    "task_status": "open",
                    "next_deadline_at": None,
                },
                {
                    "case": {"id": SECOND, "status": status, "example": True},
                    "task_status": "open",
                    "next_deadline_at": None,
                },
            ]
        if self.real_case:
            rows.append(
                {
                    "case": {"id": "real-1", "status": "assigned", "example": False},
                    "task_status": "open",
                    "next_deadline_at": None,
                }
            )
        return rows

    def second_detail(self):
        status = "escalated" if self.advanced else "assigned"
        return {
            "case": {"id": SECOND, "status": status},
            "tasks": [
                {
                    "id": "t2",
                    "status": "open",
                    "assignee_id": "vol-dedi",
                    "deadline_at": "2026-07-23T01:00:00Z",
                    "target": {"lat": 0.5, "lon": 102.1},
                }
            ],
            "evidence": [],
            "agent_runs": [],
            "timeline": [],
        }

    def detail(self):
        verdict = {"dam_state": self.verdict} if self.verdict else None
        evidence = [{"id": "e1", "verdict": verdict}]
        if self.old_verdict:
            evidence.insert(0, {"id": "old", "verdict": {"dam_state": "broken"}})
        status = "escalated" if self.advanced else "assigned"
        return {
            "case": {"id": CASE, "status": status},
            "tasks": [
                {"id": "t0", "status": "done", "assignee_id": "someone", "target": {"lat": 1, "lon": 1}},
                {"id": "t1", "status": "open", "assignee_id": "vol-ari", "target": {"lat": 0.5, "lon": 102.1}},
            ],
            "evidence": evidence,
            "agent_runs": [],
            "timeline": [],
        }


@pytest.fixture
def serve():
    servers = []

    def start(fake: FakeBara) -> str:
        class Handler(BaseHTTPRequestHandler):
            def handle_any(self):
                length = int(self.headers.get("content-length", 0))
                request_body = self.rfile.read(length)
                status, body = fake.respond(
                    self.command, self.path, self.headers.get("X-Bara-Role"), request_body
                )
                payload = body if isinstance(body, bytes) else json.dumps(body).encode()
                self.send_response(status)
                self.send_header("content-length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            do_GET = do_POST = do_PUT = handle_any

            def log_message(self, *args):
                pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        fake.base = f"http://127.0.0.1:{server.server_port}"
        threading.Thread(target=server.serve_forever, daemon=True).start()
        servers.append(server)
        return fake.base

    yield start
    for server in servers:
        server.shutdown()


def run(*args, token="fake-token"):
    env = {
        "PATH": os.environ["PATH"],
        "BARA_ENV": "/nonexistent",
        "BARA_SMOKE_TOKEN": token,
        "BARA_SMOKE_CASE_WAIT": "2",
        "BARA_SMOKE_VERDICT_WAIT": "2",
        "BARA_SMOKE_OUTCOME_WAIT": "2",
        "BARA_SMOKE_POLL": "1",
    }
    return subprocess.run(
        [shutil.which("bash"), SCRIPT, *args],
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
        check=False,
    )


def test_no_arguments_prints_help_and_exits_2():
    done = run()

    assert done.returncode == 2
    assert "--yes" in done.stderr


def test_help_lists_the_flags_and_exits_0():
    done = run("--help")

    assert done.returncode == 0
    for flag in ("--yes", "--dry-run", "--url"):
        assert flag in done.stdout


def test_an_unknown_flag_exits_2():
    assert run("--bogus").returncode == 2


def test_a_flag_without_a_value_exits_2():
    assert run("--url").returncode == 2


def test_dry_run_prints_the_plan_and_calls_nothing(serve):
    fake = FakeBara()
    base = serve(fake)

    done = run("--dry-run", "--url", base)

    assert done.returncode == 0
    assert "/api/judge/reset" in done.stdout
    assert fake.calls == []


def test_without_a_project_or_url_it_exits_3():
    assert run("--yes").returncode == 3


def test_every_step_passes_against_a_working_site(serve):
    fake = FakeBara()
    base = serve(fake)

    done = run("--yes", "--url", base)

    assert done.returncode == 0, done.stderr
    assert done.stdout.count("ok ") == 10
    assert "smoke test passed" in done.stdout
    roles = {path: role for _, path, role in fake.calls}
    assert roles["/api/judge/reset"] == "judge"
    assert roles["/api/v/vol-ari/uploads"] == "volunteer"


def test_the_clock_is_advanced_past_the_deadline_of_the_second_case(serve):
    fake = FakeBara()
    base = serve(fake)

    done = run("--yes", "--url", base)

    assert done.returncode == 0, done.stderr
    assert fake.advance_body == {"hours": 73}
    assert f"{SECOND} is escalated after +73h" in done.stdout


def test_a_missing_advance_route_fails_the_run(serve):
    base = serve(FakeBara(advance=404))

    done = run("--yes", "--url", base)

    assert done.returncode == 1
    assert "advance" in done.stderr


def test_a_wrong_verdict_fails_loudly(serve):
    base = serve(FakeBara(verdict="intact"))

    done = run("--yes", "--url", base)

    assert done.returncode == 1
    assert "FAIL" in done.stdout
    assert "intact" in done.stderr


def test_a_rejected_trigger_fails_with_the_status(serve):
    base = serve(FakeBara(trigger=403))

    done = run("--yes", "--url", base)

    assert done.returncode == 1
    assert "HTTP 202, got 403" in done.stderr


def test_an_unreachable_site_fails(serve):
    done = run("--yes", "--url", "http://127.0.0.1:1")

    assert done.returncode == 1


def test_a_real_assigned_case_is_never_used(serve):
    fake = FakeBara(real_case=True)
    base = serve(fake)

    done = run("--yes", "--url", base)

    assert done.returncode == 0, done.stderr
    assert CASE in done.stdout
    assert not any("real-1" in path for _, path, _ in fake.calls if "/uploads" in path)


def test_a_case_that_exists_before_the_trigger_is_not_used(serve):
    base = serve(FakeBara(stale=True))

    done = run("--yes", "--url", base)

    assert done.returncode == 1
    assert "fewer than 2 assigned" in done.stderr


def test_a_sample_that_is_not_served_fails_at_the_download(serve):
    base = serve(FakeBara(sample=404))

    done = run("--yes", "--url", base)

    assert done.returncode == 1
    assert "download sample" in done.stderr


def test_an_older_verdict_on_other_evidence_does_not_count(serve):
    base = serve(FakeBara(verdict=None, old_verdict=True))

    done = run("--yes", "--url", base)

    assert done.returncode == 1
    assert "verdict" in done.stderr
