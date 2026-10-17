import argparse
import os
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path

from adapters import eval_tables
from adapters.bigquery import Warehouse
from domain.eval_report import reignition_summary
from ee_lib.config import load_region
from jobs.cli import (
    DATASET,
    JobError,
    configure_logging,
    query_report,
    resolve_config_dir,
    resolve_project,
    run_job,
    write_json_atomic,
)
from jobs.eval_drying import RESULT_DIR


def eval_reignition(
    *, region_id: str, warehouse: Warehouse, out_dir: Path
) -> dict[str, object]:
    rows, result = eval_tables.read_reignition_eval(warehouse, region_id)
    try:
        report = reignition_summary(region_id, rows)
    except ValueError as error:
        raise JobError(f"{error}; run jobs.train_reignition first") from error
    write_json_atomic(out_dir / "reignition.json", report)
    return {**report, "queries": [query_report("read_eval_reignition", result)]}


def parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m jobs.eval_reignition",
        description="Copy the newest test-split rows of bara.eval_reignition "
        "(model, served model, detection_days baseline) to docs/eval/reignition.json.",
    )
    parser.add_argument(
        "--region", required=True, help="region id in config/regions.yaml"
    )
    parser.add_argument(
        "--project", help="Google Cloud project (default: GOOGLE_CLOUD_PROJECT)"
    )
    parser.add_argument("--config-dir", help="config directory (default: repo config/)")
    parser.add_argument("--out-dir", type=Path, default=RESULT_DIR)
    return parser.parse_args(argv)


def main(
    argv: Sequence[str] | None = None, environ: Mapping[str, str] = os.environ
) -> int:
    args = parse_args(argv)

    def work() -> dict[str, object]:
        project = resolve_project(args.project, environ)
        region = load_region(resolve_config_dir(args.config_dir, environ), args.region)
        from google.cloud import bigquery

        return eval_reignition(
            region_id=region.id,
            warehouse=Warehouse(bigquery.Client(project=project), project, DATASET),
            out_dir=args.out_dir,
        )

    return run_job(work)


if __name__ == "__main__":
    configure_logging()
    sys.exit(main())
