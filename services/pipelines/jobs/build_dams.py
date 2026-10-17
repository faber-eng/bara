import argparse
import os
import sys
from collections.abc import Mapping, Sequence
from datetime import UTC, date, datetime
from pathlib import Path

from adapters import dam_tables
from adapters.bigquery import Warehouse
from domain.dams import (
    DamPlan,
    DamShapeError,
    dam_feature,
    plan_dams,
    reference_features,
)
from ee_lib.config import RegionConfig, load_region, read_aoi
from ee_lib.weeks import FutureWeek, InvalidWeek, resolve_week, week_label
from jobs.cli import (
    DATASET,
    JobError,
    UsageError,
    configure_logging,
    logger,
    resolve_config_dir,
    resolve_data_dir,
    resolve_project,
    run_job,
    write_json_atomic,
)

TOP_CELLS = 10
DAM_COUNT = 40
DAM_COUNT_RANGE = range(30, 61)


def collection(features: list[dict]) -> dict:
    return {"type": "FeatureCollection", "features": features}


def top_cell_dams(dams: Sequence[DamPlan]) -> list[dict[str, object]]:
    in_top = sorted(
        (dam for dam in dams if dam.top_rank is not None),
        key=lambda dam: dam.top_rank or 0,
    )
    return [
        {
            "id": dam.id,
            "cell_id": dam.cell_id,
            "rank": dam.top_rank,
            "state": dam.state,
            "canal_osm_id": dam.osm_id,
        }
        for dam in in_top
    ]


def state_counts(dams: Sequence[DamPlan]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for dam in dams:
        counts[dam.state] = counts.get(dam.state, 0) + 1
    return dict(sorted(counts.items()))


def build_dams(
    *,
    region: str,
    aoi: dict,
    week_start: date,
    warehouse: Warehouse,
    count: int,
    out_dir: Path,
    dry_run: bool,
) -> dict[str, object]:
    candidates = dam_tables.read_candidates(
        warehouse, region, aoi, week_start, TOP_CELLS
    )
    if not candidates:
        raise JobError(f"no canal cells for {region}; run jobs.build_grid first")
    try:
        dams = plan_dams(region, candidates, count)
    except DamShapeError as error:
        raise JobError(str(error)) from error
    week = week_label(week_start)
    top_cells = [
        {**cell, "week": week}
        for cell in dam_tables.read_top_cells(warehouse, region, week_start, TOP_CELLS)
    ]
    sample = out_dir / f"dams_{region}_sample.geojson"
    reference = out_dir / f"dams_{region}_reference.geojson"
    if not dry_run:
        write_json_atomic(sample, collection([dam_feature(dam) for dam in dams]))
        write_json_atomic(reference, collection(reference_features(dams, top_cells)))
        logger.info("wrote %s and %s", sample, reference)
    return {
        "region": region,
        "week": week,
        "dams": len(dams),
        "states": state_counts(dams),
        "top_cell_dams": top_cell_dams(dams),
        "files": [str(sample), str(reference)],
        "dry_run": dry_run,
    }


def parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m jobs.build_dams",
        description="Generate the example dams on OSM canals and the reference "
        "file the tests check them against.",
    )
    parser.add_argument(
        "--region", required=True, help="region id in config/regions.yaml"
    )
    parser.add_argument(
        "--week", help="ISO week whose top 10 cells hold 3 dams (default: current)"
    )
    parser.add_argument("--count", type=int, default=DAM_COUNT, help="dams to place")
    parser.add_argument(
        "--project", help="Google Cloud project (default: GOOGLE_CLOUD_PROJECT)"
    )
    parser.add_argument(
        "--config-dir",
        help="config directory (default: BARA_CONFIG_DIR or repo config/)",
    )
    parser.add_argument(
        "--data-dir", help="output directory (default: BARA_DATA_DIR or repo data/)"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="plan the dams; write nothing"
    )
    return parser.parse_args(argv)


def resolve_job_week(label: str | None, region: RegionConfig) -> date:
    try:
        return resolve_week(label, datetime.now(UTC), region.zone)
    except (InvalidWeek, FutureWeek) as error:
        raise UsageError(str(error)) from error


def main(
    argv: Sequence[str] | None = None, environ: Mapping[str, str] = os.environ
) -> int:
    args = parse_args(argv)

    def work() -> dict[str, object]:
        if args.count not in DAM_COUNT_RANGE:
            raise UsageError("--count must be 30 to 60")
        project = resolve_project(args.project, environ)
        config_dir = resolve_config_dir(args.config_dir, environ)
        region = load_region(config_dir, args.region)
        week_start = resolve_job_week(args.week, region)
        from google.cloud import bigquery

        return build_dams(
            region=region.id,
            aoi=read_aoi(config_dir, region),
            week_start=week_start,
            warehouse=Warehouse(bigquery.Client(project=project), project, DATASET),
            count=args.count,
            out_dir=resolve_data_dir(args.data_dir, environ),
            dry_run=args.dry_run,
        )

    return run_job(work)


if __name__ == "__main__":
    configure_logging()
    sys.exit(main())
