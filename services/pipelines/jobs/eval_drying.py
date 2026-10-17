import argparse
import os
import sys
from collections.abc import Mapping, Sequence
from datetime import UTC, date, datetime
from pathlib import Path

from adapters import eval_tables
from adapters.bigquery import Warehouse
from domain.eval_report import FOLLOW_WEEKS, TOP_SHARE, complete_weeks, year_summary
from ee_lib.config import load_region
from jobs.cli import (
    DATASET,
    configure_logging,
    query_report,
    resolve_config_dir,
    resolve_project,
    run_job,
    write_json_atomic,
)

YEARS = (2019, 2023, 2026)
RESULT_DIR = Path(__file__).resolve().parents[3] / "docs/eval"


def evaluate_year(
    warehouse: Warehouse,
    region_id: str,
    year: int,
    through: date,
    queries: list[dict[str, object]],
) -> dict[str, object]:
    weeks, result = eval_tables.read_week_captures(warehouse, region_id, year)
    queries.append(query_report(f"week_captures_{year}", result))
    return year_summary(year, complete_weeks(weeks, through))


def eval_drying(
    *,
    region_id: str,
    years: Sequence[int],
    warehouse: Warehouse,
    evaluated_at: datetime,
    out_dir: Path,
) -> dict[str, object]:
    queries: list[dict[str, object]] = []
    through, result = eval_tables.detections_through(warehouse)
    queries.append(query_report("detections_through", result))
    summaries = [
        evaluate_year(warehouse, region_id, year, through, queries) for year in years
    ]
    eval_tables.append_drying_eval(
        warehouse,
        [
            {
                "evaluated_at": evaluated_at.isoformat(),
                "region": region_id,
                "top_share": TOP_SHARE,
                "detections_through": through.isoformat(),
                **summary,
            }
            for summary in summaries
        ],
    )
    report = {
        "run_at": evaluated_at.isoformat(),
        "region": region_id,
        "top_share": TOP_SHARE,
        "follow_weeks": list(FOLLOW_WEEKS),
        "detections_through": through.isoformat(),
        "years": summaries,
    }
    write_json_atomic(out_dir / "drying.json", report)
    return {**report, "queries": queries}


def parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m jobs.eval_drying",
        description="Capture rate and lift of the top 10%% of cells by drying_score "
        "against FIRMS hotspots 1 to 4 weeks later; appends bara.eval_drying and "
        "writes docs/eval/drying.json.",
    )
    parser.add_argument(
        "--region", required=True, help="region id in config/regions.yaml"
    )
    parser.add_argument("--year", type=int, action="append", help=f"default: {YEARS}")
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

        return eval_drying(
            region_id=region.id,
            years=tuple(args.year or YEARS),
            warehouse=Warehouse(bigquery.Client(project=project), project, DATASET),
            evaluated_at=datetime.now(UTC),
            out_dir=args.out_dir,
        )

    return run_job(work)


if __name__ == "__main__":
    configure_logging()
    sys.exit(main())
