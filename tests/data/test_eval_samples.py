import importlib.util
import json
import shutil
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "check_eval_samples.py"

spec = importlib.util.spec_from_file_location("check_eval_samples", SCRIPT)
check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check)


def copy_data(tmp_path):
    shutil.copytree(REPO / "data" / "eval", tmp_path / "data" / "eval")
    shutil.copytree(REPO / "data" / "samples", tmp_path / "data" / "samples")
    return tmp_path


def test_repo_data_passes(capsys):
    assert check.main([]) == 0
    assert "overlap: 0" in capsys.readouterr().out


def test_json_report_counts_files(capsys):
    assert check.main(["--json"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["problems"] == []
    assert report["overlap"] == 0
    assert report["sample_files"] >= 8


def test_same_bytes_in_both_sets_fails(tmp_path, capsys):
    root = copy_data(tmp_path)
    sample = next((root / "data" / "samples" / "photo").glob("*.jpg"))
    shutil.copy(sample, root / "data" / "eval" / "photos" / "broken_dam_01.jpg")
    assert check.main(["--root", str(root), "--json"]) == check.EXIT_FAIL
    report = json.loads(capsys.readouterr().out)
    assert report["overlap"] == 1


def test_same_source_page_in_both_sets_fails(tmp_path, capsys):
    root = copy_data(tmp_path)
    credits = root / "data" / "samples" / "CREDITS.md"
    labels = root / "data" / "eval" / "labels.csv"
    first_eval_source = check.read_labels(labels)[0]["source_url"]
    first_row = check.read_credits(credits)[0]
    credits.write_text(credits.read_text().replace(first_row["source"], f"<{first_eval_source}>"))
    assert check.main(["--root", str(root), "--json"]) == check.EXIT_FAIL
    assert json.loads(capsys.readouterr().out)["overlap"] == 1


def test_sample_without_credit_row_fails(tmp_path, capsys):
    root = copy_data(tmp_path)
    (root / "data" / "samples" / "photo" / "extra.jpg").write_bytes(b"extra")
    assert check.main(["--root", str(root), "--json"]) == check.EXIT_FAIL
    assert any("extra.jpg" in problem for problem in json.loads(capsys.readouterr().out)["problems"])


def test_eval_file_without_label_fails(tmp_path, capsys):
    root = copy_data(tmp_path)
    (root / "data" / "eval" / "photos" / "extra.jpg").write_bytes(b"extra")
    assert check.main(["--root", str(root), "--json"]) == check.EXIT_FAIL


def test_missing_data_dir_exits_one(tmp_path, capsys):
    assert check.main(["--root", str(tmp_path), "--json"]) == check.EXIT_FAIL
    assert "error" in json.loads(capsys.readouterr().out)
