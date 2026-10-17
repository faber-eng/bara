import importlib.util
import json
import subprocess
import sys

from conftest import REPO

SCRIPT = REPO / "scripts/build_eval.py"


def load_build_eval():
    spec = importlib.util.spec_from_file_location("build_eval", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_committed_eval_outputs_match_the_result_files():
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--check"], capture_output=True, text=True
    )

    assert result.returncode == 0, result.stderr


def test_the_web_copy_is_the_merged_file():
    merged = (REPO / "docs/eval.json").read_text()

    assert (REPO / "apps/web/src/eval/eval.json").read_text() == merged


def test_a_missing_part_is_left_out_and_reported_as_not_run(tmp_path):
    build_eval = load_build_eval()
    agent = {"run_at": "2026-10-18T05:00:00Z", "model": "m", "cases": 8,
             "passed": 6, "pass_rate": 0.75,
             "results": [{"case": "a", "passed": True}]}
    (tmp_path / "agent.json").write_text(json.dumps(agent))

    merged = build_eval.merge(tmp_path)
    report = build_eval.render(merged)

    assert merged["generated_at"] == "2026-10-18T05:00:00Z"
    assert "drying" not in merged
    assert merged["latency"] == []
    assert "## Drying score: capture rate and lift\n\nNot run yet." in report
    assert "6 of 8 cases passed (75.0%)" in report


def test_every_number_in_the_summary_comes_from_the_merged_file():
    build_eval = load_build_eval()
    merged = json.loads((REPO / "docs/eval.json").read_text())

    rows = build_eval.summary_rows(merged)

    lifts = [row for row in rows if row[0].startswith("Drying lift")]
    assert [row[1] for row in lifts] == [
        build_eval.times(year["lift"]) for year in merged["drying"]["years"]
    ]
