import argparse
import os
import sys
from collections import Counter
from collections.abc import Mapping, Sequence
from datetime import UTC, date, datetime, timedelta
from typing import Protocol

from adapters import reignition_tables, tables
from adapters.bigquery import QueryResult, Warehouse
from domain.reignition_features import (
    MissingMeasurement,
    TrainingRow,
    cells_by_date,
    event_windows,
    training_rows,
)
from ee_lib.config import (
    DataConfig,
    RegionConfig,
    load_data_config,
    load_region,
    read_aoi,
)
from ee_lib.weeks import EventWindows, local_today
from jobs.cli import (
    DATASET,
    JobError,
    UsageError,
    configure_logging,
    logger,
    resolve_config_dir,
    resolve_project,
    run_job,
)

ONE_DAY = timedelta(days=1)
DEFAULT_DAYS = 60
NULLABLE_FIELDS = (
    "s1_anom_db",
    "rain_7d_before_mm",
    "rain_14d_before_mm",
    "rain_7d_after_mm",
)


class FeatureSource(Protocol):
    def chirps_last_day(self, before: date) -> date: ...

    def reignition_measures(
        self,
        region: RegionConfig,
        aoi: dict,
        cells_table: str,
        dates: list[tuple[date, list[str], EventWindows]],
    ) -> list[dict]: ...

    def peat_fractions(self, region: RegionConfig, cells_table: str) -> list[dict]: ...


def query_report(step: str, result: QueryResult) -> dict[str, object]:
    logger.info("%s: %s bytes billed", step, result.bytes_billed)
    return {"step": step, "bytes": result.bytes_billed, "estimate": result.dry_run}


def resolve_since(rebuild_all: bool, days: int, today: date, data: DataConfig) -> date:
    if rebuild_all:
        return date(data.reignition.split_years.train[0], 1, 1)
    if days < 1:
        raise UsageError(f"--days must be at least 1, got {days}")
    return today - timedelta(days=days)


def peat_by_cell(measured: Sequence[Mapping[str, object]]) -> dict[str, float]:
    fractions: dict[str, float] = {}
    for cell in measured:
        value = cell.get("peat_fraction")
        if value is not None:
            fractions[str(cell["cell_id"])] = float(value)
    return fractions


def split_counts(rows: Sequence[TrainingRow]) -> dict[str, dict[str, int]]:
    totals = Counter(row.split for row in rows)
    positives = Counter(row.split for row in rows if row.reignited == 1)
    unlabeled = Counter(row.split for row in rows if row.reignited is None)
    return {
        split: {
            "rows": totals[split],
            "reignited": positives[split],
            "unlabeled": unlabeled[split],
        }
        for split in sorted(totals)
    }


def null_counts(rows: Sequence[TrainingRow]) -> dict[str, int]:
    return {
        field: sum(1 for row in rows if getattr(row, field) is None)
        for field in NULLABLE_FIELDS
    }


def reignition_features(
    *,
    region: RegionConfig,
    aoi: dict,
    data: DataConfig,
    since: date,
    today: date,
    earth: FeatureSource,
    warehouse: Warehouse,
    dry_run: bool,
) -> dict[str, object]:
    read = reignition_tables.read_events(
        warehouse, region.id, since, data.reignition.history_from_year
    )
    queries = [query_report("read_events", read)]
    summary: dict[str, object] = {"region": region.id, "since": since}
    if not read.rows:
        logger.info("%s: no fire events since %s", region.id, since)
        return {**summary, "rows": 0, "dry_run": dry_run, "queries": queries}
    chirps_last = earth.chirps_last_day(today + ONE_DAY)
    cells_table = warehouse.table_id(tables.CELLS.name)
    dates = [
        (
            quiet_date,
            cell_ids,
            event_windows(quiet_date, data.drying.s1_window_days, chirps_last),
        )
        for quiet_date, cell_ids in sorted(cells_by_date(read.rows).items())
    ]
    logger.info("%s: measuring %d quiet dates", region.id, len(dates))
    measures = earth.reignition_measures(region, aoi, cells_table, dates)
    fractions = peat_by_cell(earth.peat_fractions(region, cells_table))
    try:
        rows = training_rows(
            read.rows, measures, fractions, data.reignition.split_years
        )
    except MissingMeasurement as error:
        raise JobError(str(error)) from error
    if not dry_run:
        written = reignition_tables.replace_training(warehouse, region.id, since, rows)
        queries.append(query_report("rewrite_training", written))
    return {
        **summary,
        "chirps_last": chirps_last,
        "rows": len(rows),
        "splits": split_counts(rows),
        "nulls": null_counts(rows),
        "dry_run": dry_run,
        "queries": queries,
    }


def parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m jobs.reignition_features",
        description="Compute the re-ignition features of each fire event at its "
        "quiet_date and rewrite those events in bara.reignition_training.",
    )
    parser.add_argument(
        "--region", required=True, help="region id in config/regions.yaml"
    )
    scope = parser.add_mutually_exclusive_group()
    scope.add_argument(
        "--all",
        action="store_true",
        help="rebuild every event from the first train year",
    )
    scope.add_argument(
        "--days",
        type=int,
        default=DEFAULT_DAYS,
        help=f"rebuild events quiet in the last N days (default {DEFAULT_DAYS})",
    )
    parser.add_argument(
        "--project", help="Google Cloud project (default: GOOGLE_CLOUD_PROJECT)"
    )
    parser.add_argument(
        "--config-dir",
        help="config directory (default: BARA_CONFIG_DIR or repo config/)",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="compute the features; write nothing"
    )
    return parser.parse_args(argv)


def main(
    argv: Sequence[str] | None = None, environ: Mapping[str, str] = os.environ
) -> int:
    args = parse_args(argv)

    def work() -> dict[str, object]:
        project = resolve_project(args.project, environ)
        config_dir = resolve_config_dir(args.config_dir, environ)
        data = load_data_config(config_dir)
        region = load_region(config_dir, args.region)
        aoi = read_aoi(config_dir, region)
        today = local_today(datetime.now(UTC), region.zone)
        from google.cloud import bigquery

        from adapters import earthengine
        from ee_lib import session

        session.initialize(project)
        return reignition_features(
            region=region,
            aoi=aoi,
            data=data,
            since=resolve_since(args.all, args.days, today, data),
            today=today,
            earth=earthengine.EarthEngineSource(data),
            warehouse=Warehouse(bigquery.Client(project=project), project, DATASET),
            dry_run=args.dry_run,
        )

    return run_job(work)


if __name__ == "__main__":
    configure_logging()
    sys.exit(main())
