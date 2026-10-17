#!/usr/bin/env python3
import argparse
import csv
import hashlib
import json
import re
import sys
from pathlib import Path

DEFAULT_ROOT = Path(__file__).resolve().parents[1]
MEDIA_SUFFIXES = {".jpg", ".jpeg", ".png", ".ogg", ".webm", ".flac", ".mp3", ".geojson"}
EXIT_FAIL = 1
URL_IN_ROW = re.compile(r"<(https?://[^>]+)>")


def media_files(directory):
    return sorted(p for p in directory.rglob("*") if p.is_file() and p.suffix.lower() in MEDIA_SUFFIXES)


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_labels(labels_path):
    with labels_path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def read_credits(credits_path):
    rows = []
    for line in credits_path.read_text().splitlines():
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) == 5 and cells[0] not in ("file", "---"):
            rows.append(dict(zip(("file", "label", "author", "licence", "source"), cells)))
    return rows


def eval_problems(eval_dir, labels):
    listed = {row["object_path"] for row in labels}
    on_disk = {p.relative_to(eval_dir).as_posix() for p in media_files(eval_dir)}
    problems = [f"labels.csv lists {path} but the file is missing" for path in sorted(listed - on_disk)]
    problems += [f"{path} has no row in labels.csv" for path in sorted(on_disk - listed)]
    problems += [f"labels.csv row {row['object_path']} has no licence" for row in labels if not row["licence"]]
    return problems


def samples_problems(samples_dir, credits):
    listed = [row["file"] for row in credits]
    on_disk = {p.relative_to(samples_dir).as_posix() for p in media_files(samples_dir)}
    problems = [f"{path} appears {listed.count(path)} times in CREDITS.md" for path in sorted(set(listed)) if listed.count(path) != 1]
    problems += [f"CREDITS.md lists {path} but the file is missing" for path in sorted(set(listed) - on_disk)]
    problems += [f"{path} has no row in CREDITS.md" for path in sorted(on_disk - set(listed))]
    names = [Path(path).name for path in listed]
    problems += [f"file name {name} is not unique" for name in sorted(set(names)) if names.count(name) > 1]
    return problems


def overlap_problems(eval_dir, samples_dir, labels, credits):
    eval_hashes = {sha256(p): p.relative_to(eval_dir).as_posix() for p in media_files(eval_dir)}
    problems = []
    for path in media_files(samples_dir):
        twin = eval_hashes.get(sha256(path))
        if twin:
            problems.append(f"{path.relative_to(samples_dir).as_posix()} has the same bytes as eval/{twin}")
    eval_sources = {row["source_url"] for row in labels if row["source_url"].startswith("http")}
    for row in credits:
        match = URL_IN_ROW.search(row["source"])
        if match and match.group(1) in eval_sources:
            problems.append(f"{row['file']} has the same source page as an eval file: {match.group(1)}")
    return problems


def run_checks(root):
    eval_dir = root / "data" / "eval"
    samples_dir = root / "data" / "samples"
    labels = read_labels(eval_dir / "labels.csv")
    credits = read_credits(samples_dir / "CREDITS.md")
    overlaps = overlap_problems(eval_dir, samples_dir, labels, credits)
    problems = eval_problems(eval_dir, labels) + samples_problems(samples_dir, credits) + overlaps
    return {"eval_files": len(labels), "sample_files": len(credits), "overlap": len(overlaps), "problems": problems}


def parse_args(argv):
    parser = argparse.ArgumentParser(description="Check that data/eval and data/samples are labelled, credited and do not overlap.")
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT, help="repo root (default: this repo)")
    parser.add_argument("--json", action="store_true", help="print one JSON document on stdout")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        report = run_checks(args.root)
    except FileNotFoundError as error:
        message = f"missing {error.filename}; run from the repo root or pass --root"
        print(json.dumps({"error": message}) if args.json else message, file=sys.stderr if not args.json else sys.stdout)
        return EXIT_FAIL
    if args.json:
        print(json.dumps(report))
    else:
        for problem in report["problems"]:
            print(problem, file=sys.stderr)
        print(f"eval files: {report['eval_files']}, sample files: {report['sample_files']}, overlap: {report['overlap']}")
    return EXIT_FAIL if report["problems"] else 0


if __name__ == "__main__":
    sys.exit(main())
