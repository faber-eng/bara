import importlib.util
import io
import subprocess
import sys
from pathlib import Path

import pytest

from adapters.identity import IdentityUnavailable
from tests.fakes import FakeClaimsAdmin

SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "grant_role.py"
ENV = {"PROJECT": "example-project"}


def load_script():
    spec = importlib.util.spec_from_file_location("grant_role_script", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


script = load_script()


def run(argv, admin=None, environ=None):
    admin = admin or FakeClaimsAdmin(
        {"u1": {"role": "volunteer", "locale": "id"}}, {"a@b.test": "u1"}
    )
    out, err = io.StringIO(), io.StringIO()
    projects = []

    def factory(project):
        projects.append(project)
        return admin

    code = script.main(
        argv,
        environ=ENV if environ is None else environ,
        admin_factory=factory,
        out=out,
        err=err,
    )
    return code, out.getvalue(), err.getvalue(), admin, projects


@pytest.mark.parametrize("role", ["ops", "brigade"])
def test_a_grant_merges_the_role_prints_uid_and_role_and_exits_0(role):
    code, out, _, admin, _ = run(["a@b.test", role])

    assert code == 0
    assert out == f"u1 {role}\n"
    assert admin.claims_by_uid["u1"] == {"role": role, "locale": "id"}


@pytest.mark.parametrize("role", ["volunteer", "judge", "root"])
def test_a_role_outside_ops_and_brigade_is_a_usage_error(role):
    code, out, _, admin, _ = run(["a@b.test", role])

    assert code == 2
    assert out == ""
    assert admin.writes == []


def test_no_arguments_is_a_usage_error():
    code, out, err, _, _ = run([])

    assert code == 2
    assert out == ""
    assert "usage" in err.lower()


def test_a_wrong_flag_is_a_usage_error():
    code, _, _, admin, _ = run(["a@b.test", "ops", "--nope"])

    assert code == 2
    assert admin.writes == []


def test_help_exits_0_and_lists_the_flags():
    code, out, _, _, _ = run(["--help"])

    assert code == 0
    for flag in ("--project", "--dry-run"):
        assert flag in out


def test_an_unknown_email_exits_3_and_says_to_sign_in_once():
    code, out, err, _, _ = run(["who@b.test", "ops"])

    assert code == 3
    assert out == ""
    assert "sign in with Google once first" in err


def test_a_firebase_error_exits_4():
    admin = FakeClaimsAdmin(uid_by_email={"a@b.test": "u1"})
    admin.fail_with = IdentityUnavailable("permission denied")

    code, out, err, _, _ = run(["a@b.test", "ops"], admin=admin)

    assert code == 4
    assert out == ""
    assert "permission denied" in err


def test_any_other_failure_exits_1():
    admin = FakeClaimsAdmin(uid_by_email={"a@b.test": "u1"})
    admin.fail_with = RuntimeError("boom")

    code, _, err, _, _ = run(["a@b.test", "ops"], admin=admin)

    assert code == 1
    assert "boom" in err


def test_dry_run_prints_the_same_line_and_writes_nothing():
    code, out, _, admin, _ = run(["a@b.test", "ops", "--dry-run"])

    assert code == 0
    assert out == "u1 ops\n"
    assert admin.writes == []


def test_a_missing_project_exits_2_and_names_the_flag(tmp_path):
    code, out, err, _, _ = run(
        ["a@b.test", "ops"], environ={"BARA_ENV": str(tmp_path / "none.env")}
    )

    assert code == 2
    assert out == ""
    assert "--project" in err


def test_the_project_flag_beats_the_environment():
    _, _, _, _, projects = run(["a@b.test", "ops", "--project", "flag-project"])

    assert projects == ["flag-project"]


def test_the_project_falls_back_to_the_environment():
    _, _, _, _, projects = run(["a@b.test", "ops"])

    assert projects == ["example-project"]


def test_the_project_falls_back_to_the_secrets_file(tmp_path):
    env_file = tmp_path / "bara.env"
    env_file.write_text('OTHER=1\nPROJECT="file-project"\n')

    _, _, _, _, projects = run(["a@b.test", "ops"], environ={"BARA_ENV": str(env_file)})

    assert projects == ["file-project"]


def test_the_real_entry_point_prints_help_and_exits_0():
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--help"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "--dry-run" in result.stdout


def test_the_real_entry_point_with_no_arguments_exits_2():
    result = subprocess.run(
        [sys.executable, str(SCRIPT)], check=False, capture_output=True, text=True
    )

    assert result.returncode == 2
    assert result.stdout == ""
