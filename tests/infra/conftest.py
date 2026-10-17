import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
PROJECT = "demo-project"
REGION = "asia-southeast1"
CI_ACCOUNT = f"bara-build@{PROJECT}.iam.gserviceaccount.com"

STUB_SCRIPT = """#!/usr/bin/env bash
printf '%s\\n' "$*" >> "$STUB_LOG"
if [[ "$*" == *get-iam-policy* && -n "${STUB_POLICY:-}" ]]; then
  printf '%s\\n' "$STUB_POLICY"
  exit 0
fi
if [[ -n "${STUB_OK_PATTERN:-}" && "$*" =~ $STUB_OK_PATTERN ]]; then
  exit 0
fi
case "$*" in
  *describe*) exit 1 ;;
esac
exit 0
"""

REPORT_LINE = re.compile(r"^(ok|made|would make)\s+(\S+)\s+(.*)$")


@dataclass(frozen=True)
class Report:
    state: str
    kind: str
    name: str


@dataclass(frozen=True)
class Result:
    code: int
    out: str
    err: str
    calls: list[str]

    def reports(self) -> list[Report]:
        matches = (REPORT_LINE.match(line) for line in self.out.splitlines())
        return [Report(*m.groups()) for m in matches if m]

    def states_of(self, kind: str, name_part: str) -> list[str]:
        return [r.state for r in self.reports() if r.kind == kind and name_part in r.name]


@pytest.fixture
def stub_bin(tmp_path: Path) -> Path:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for tool in ("gcloud", "bq"):
        path = bin_dir / tool
        path.write_text(STUB_SCRIPT)
        path.chmod(0o755)
    return bin_dir


@pytest.fixture
def bare_bin(tmp_path: Path) -> Path:
    bin_dir = tmp_path / "bare"
    bin_dir.mkdir()
    (bin_dir / "dirname").symlink_to(shutil.which("dirname"))
    return bin_dir


@pytest.fixture
def run_script(tmp_path: Path, stub_bin: Path):
    def run(
        script: str,
        *args: str,
        path: Path | None = None,
        ok_pattern: str = "",
        policy: str = "",
    ) -> Result:
        log = tmp_path / "calls.log"
        log.write_text("")
        search_path = f"{stub_bin}:{os.environ['PATH']}" if path is None else str(path)
        env = {
            "PATH": search_path,
            "BARA_ENV": str(tmp_path / "missing.env"),
            "STUB_LOG": str(log),
            "STUB_OK_PATTERN": ok_pattern,
            "STUB_POLICY": policy,
        }
        bash = shutil.which("bash")
        done = subprocess.run(
            [bash, str(REPO / script), *args],
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
        )
        calls = log.read_text().splitlines()
        return Result(done.returncode, done.stdout, done.stderr, calls)

    return run
