import importlib.util
import io
import json
import subprocess
import sys
from pathlib import Path

from tests.test_scenario_reset import World

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts" / "seed_scenario.py"


def load_script():
    spec = importlib.util.spec_from_file_location("seed_scenario_script", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


script = load_script()


def run(argv, world=None, environ=None, factory=None):
    world = world or World()
    seen = []

    def default_factory(project, data_dir):
        seen.append((project, data_dir))
        return world.resetter

    out, err = io.StringIO(), io.StringIO()
    code = script.main(
        argv,
        environ={"PROJECT": "example-project"} if environ is None else environ,
        resetter_factory=factory or default_factory,
        out=out,
        err=err,
    )
    return code, out.getvalue(), err.getvalue(), world, seen


def test_a_run_resets_and_prints_what_it_did():
    world = World()
    world.add_example_case()

    code, out, _, _, seen = run(["--data-dir", str(ROOT / "data")], world)

    assert code == 0
    assert "seeded 40 dams" in out
    assert len(world.dams.where()) == 40
    assert seen[0][0] == "example-project"


def test_dry_run_prints_the_plan_and_writes_nothing():
    world = World()
    before = world.state()

    code, out, _, _, _ = run(["--dry-run"], world)

    assert code == 0
    assert "would delete" in out
    assert world.state() == before


def test_json_prints_one_document_on_stdout():
    code, out, err, _, _ = run(["--dry-run", "--json"])

    document = json.loads(out)
    assert code == 0
    assert document["dry_run"] is True
    assert document["seeded"]["dams"] == 40
    assert err == ""


def test_no_arguments_prints_help_and_exits_2():
    code, out, err, _, _ = run([])

    assert code == 2
    assert "--dry-run" in err
    assert out == ""


def test_an_unknown_flag_is_a_usage_error(capsys):
    code, _, _, _, _ = run(["--bogus"])

    assert code == 2


def test_no_project_is_a_usage_error_that_names_the_flag():
    code, _, err, _, _ = run(["--dry-run"], environ={"BARA_ENV": "/nonexistent"})

    assert code == 2
    assert "--project" in err


def test_a_failing_store_exits_1_with_what_to_do():
    def broken(project, data_dir):
        raise RuntimeError("PermissionDenied")

    code, out, err, _, _ = run(["--dry-run"], factory=broken)

    assert code == 1
    assert out == ""
    assert "PermissionDenied" in err
    assert "application-default" in err


def test_a_bad_scenario_file_exits_1(tmp_path):
    from domain.scenario import ScenarioError

    def bad(project, data_dir):
        raise ScenarioError("cannot read scenario")

    code, _, err, _, _ = run(["--dry-run"], factory=bad)

    assert code == 1
    assert "scenario_riau.yaml" in err


def test_the_real_entry_point_shows_help_with_exit_0():
    done = subprocess.run(
        [sys.executable, "-I", str(SCRIPT), "--help"],
        capture_output=True,
        text=True,
        check=False,
        cwd=ROOT,
    )

    assert done.returncode == 0
    assert "--dry-run" in done.stdout
    assert "--json" in done.stdout
