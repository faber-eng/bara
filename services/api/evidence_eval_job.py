import argparse
import asyncio
import csv
import json
import sys
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

from google.cloud import bigquery

from adapters.bigquery import DATASET, Warehouse
from adapters.evidence_eval_table import append_evidence_eval
from adapters.gemini import ModelGateway, build_vertex_clients
from casework.evidence_eval import EvidenceEvaluator
from casework.evidence_reader import PROMPT_VERSIONS, EvidenceReader
from config import load_settings
from domain.evidence_eval import (
    LabelRow,
    ScoredItem,
    evidence_row,
    kind_for,
    parse_label_row,
    summarize_set,
)
from logs import configure_logging

REPO = Path(__file__).resolve().parents[2]
EVAL_DIR = REPO / "data/eval"
RESULT_PATH = REPO / "docs/eval/evidence.json"
KINDS = ("photo", "audio")


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python evidence_eval_job.py",
        description="Read every item of data/eval/labels.csv with the live evidence "
        "reader, append the verdicts to bara.eval_evidence and write "
        "docs/eval/evidence.json.",
    )
    parser.add_argument("--eval-dir", type=Path, default=EVAL_DIR)
    parser.add_argument("--out", type=Path, default=RESULT_PATH)
    return parser.parse_args(argv)


def read_labels(eval_dir: Path) -> list[LabelRow]:
    with (eval_dir / "labels.csv").open(newline="") as handle:
        return [parse_label_row(raw) for raw in csv.DictReader(handle)]


def items_of_kind(items: Sequence[ScoredItem], kind: str) -> list[ScoredItem]:
    return [item for item in items if kind_for(item.row.object_path) == kind]


def summarize(
    items: Sequence[ScoredItem], run_at: str, model: str
) -> dict[str, object]:
    sets = [
        summarize_set(kind, PROMPT_VERSIONS[kind], items_of_kind(items, kind))
        for kind in KINDS
        if items_of_kind(items, kind)
    ]
    return {"run_at": run_at, "model": model, "sets": sets}


def main(argv: Sequence[str]) -> int:
    configure_logging()
    args = parse_args(argv)
    settings = load_settings()
    gateway = ModelGateway(settings.models, build_vertex_clients(settings))
    rows = read_labels(args.eval_dir)
    evaluator = EvidenceEvaluator(EvidenceReader(gateway))
    run_at = datetime.now(UTC).isoformat()
    items = asyncio.run(
        evaluator.score_all(
            rows, lambda row: (args.eval_dir / row.object_path).read_bytes()
        )
    )
    route = settings.models.fast
    model = route.fallback if gateway.fallback_used else route.model
    warehouse = Warehouse(
        bigquery.Client(project=settings.project), settings.project, DATASET
    )
    append_evidence_eval(
        warehouse,
        [
            evidence_row(
                item, run_at, model, PROMPT_VERSIONS[kind_for(item.row.object_path)]
            )
            for item in items
        ],
    )
    summary = summarize(items, run_at, model)
    args.out.write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
