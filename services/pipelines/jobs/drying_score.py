import argparse
import os
import sys
from collections.abc import Mapping, Sequence
from datetime import UTC, date, datetime
from typing import Protocol

from adapters import tables
from adapters.bigquery import QueryResult, Warehouse
from domain.drying import DryingRow, join_measurements, score_cells
from ee_lib.config import (
    DryingConfig,
    RegionConfig,
    load_data_config,
    load_region,
    read_aoi,
)
from ee_lib.weeks import (
    DryingWindow,
    FutureWeek,
    InvalidWeek,
    drying_window,
    local_today,
    resolve_week,
    week_label,
    window_end,
)
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

TOP_CELLS = 3


class DryingSource(Protocol):
    def chirps_last_day(self, before: date) -> date: ...

    def drying_inputs(
        self,
        region: RegionConfig,
        aoi: dict,
        cells_table: str,
        week_start: date,
        window: DryingWindow,
    ) -> list[dict]: ...


def utcnow() -> datetime:
    return datetime.now(UTC)


def query_report(step: str, result: QueryResult) -> dict[str, object]:
    logger.info("%s: %s bytes billed", step, result.bytes_billed)
    return {"step": step, "bytes": result.bytes_billed, "estimate": result.dry_run}


def top_cells(rows: Sequence[DryingRow]) -> list[dict[str, object]]:
    return [
        {"cell_id": row.cell_id, "drying_score": row.drying_score, "rank": row.rank}
        for row in rows[:TOP_CELLS]
    ]


def summarize(rows: Sequence[DryingRow], window: DryingWindow) -> dict[str, object]:
    scores = [row.drying_score for row in rows]
    return {
        "cells": len(rows),
        "s1_window": [window.s1_recent.start, window.s1_recent.end],
        "rain_window": [window.rain.start, window.rain.end],
        "s1_null": sum(1 for row in rows if row.s1_anom_db is None),
        "stale_s1": sum(1 for row in rows if row.stale_s1),
        "score_min": min(scores),
        "score_max": max(scores),
        "top": top_cells(rows),
    }


def drying_score(
    *,
    region: RegionConfig,
    aoi: dict,
    week_start: date,
    today: date,
    earth: DryingSource,
    warehouse: Warehouse,
    drying: DryingConfig,
    dry_run: bool,
) -> dict[str, object]:
    read = tables.read_cells(warehouse, region.id)
    queries = [query_report("read_cells", read)]
    if not read.rows:
        raise JobError(
            f"bara.cells has no rows for {region.id}; run jobs.build_grid first"
        )
    window = drying_window(
        week_start,
        today=today,
        chirps_last=earth.chirps_last_day(window_end(week_start, today)),
        s1_days=drying.s1_window_days,
        rain_days=drying.rain_window_days,
    )
    measured = earth.drying_inputs(
        region, aoi, warehouse.table_id(tables.CELLS.name), week_start, window
    )
    rows = score_cells(
        region.id, week_start, join_measurements(read.rows, measured), drying.weights
    )
    logger.info("%s %s: scored %d cells", region.id, week_label(week_start), len(rows))
    if not dry_run:
        deleted = tables.replace_week(warehouse, region.id, week_start, rows)
        queries.append(query_report("delete_week", deleted))
    return {
        "region": region.id,
        "week": week_label(week_start),
        "week_start": week_start,
        **summarize(rows, window),
        "dry_run": dry_run,
        "queries": queries,
    }


def parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m jobs.drying_score",
        description="Score every peat cell of a region for one ISO week and write "
        "bara.cell_weekly_drying.",
    )
    parser.add_argument(
        "--region", required=True, help="region id in config/regions.yaml"
    )
    parser.add_argument(
        "--week",
        help="ISO week like 2026-W42 (default: the current week in the region)",
    )
    parser.add_argument(
        "--project", help="Google Cloud project (default: GOOGLE_CLOUD_PROJECT)"
    )
    parser.add_argument(
        "--config-dir",
        help="config directory (default: BARA_CONFIG_DIR or repo config/)",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="score the week; write nothing"
    )
    return parser.parse_args(argv)


def resolve_job_week(label: str | None, region: RegionConfig) -> date:
    try:
        return resolve_week(label, utcnow(), region.zone)
    except (InvalidWeek, FutureWeek) as error:
        raise UsageError(str(error)) from error


def main(
    argv: Sequence[str] | None = None, environ: Mapping[str, str] = os.environ
) -> int:
    args = parse_args(argv)

    def work() -> dict[str, object]:
        project = resolve_project(args.project, environ)
        config_dir = resolve_config_dir(args.config_dir, environ)
        data = load_data_config(config_dir)
        region = load_region(config_dir, args.region)
        week_start = resolve_job_week(args.week, region)
        aoi = read_aoi(config_dir, region)
        from google.cloud import bigquery

        from adapters import earthengine
        from ee_lib import session

        session.initialize(project)
        return drying_score(
            region=region,
            aoi=aoi,
            week_start=week_start,
            today=local_today(utcnow(), region.zone),
            earth=earthengine.EarthEngineSource(data),
            warehouse=Warehouse(bigquery.Client(project=project), project, DATASET),
            drying=data.drying,
            dry_run=args.dry_run,
        )

    return run_job(work)


if __name__ == "__main__":
    configure_logging()
    sys.exit(main())
