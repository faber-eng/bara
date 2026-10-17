import argparse
import json
import os
import sys
import uuid
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, date, datetime
from pathlib import Path

from pydantic import ValidationError

from adapters import ranking_tables
from adapters.bigquery import Warehouse
from adapters.events import EventPublisher
from adapters.rankings_store import RankingsStore
from domain.rankings import (
    RankingRowError,
    cell_document,
    dam_cells_param,
    dam_document,
    parse_dams,
    rank_dams,
    ranked_cell,
    ranking_event,
)
from ee_lib.config import RegionConfig, load_region
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
)

TOP_CELLS = 200
TOP_DAMS = 50


def read_dams(path: Path) -> list:
    if not path.exists():
        logger.info("no dams file at %s; publishing cells only", path)
        return []
    try:
        return parse_dams(json.loads(path.read_text()))
    except (json.JSONDecodeError, KeyError, ValueError) as error:
        raise JobError(f"cannot read the dams in {path}: {error}") from error


def build_cells(rows: Sequence[Mapping[str, object]]) -> list:
    try:
        return [ranked_cell(row) for row in rows]
    except RankingRowError as error:
        raise JobError(str(error)) from error


def build_dams(warehouse: Warehouse, region: str, week_start: date, dams: list):
    if not dams:
        return []
    scored = ranking_tables.read_dam_cells(
        warehouse, region, week_start, dam_cells_param(dams)
    )
    return rank_dams(dams, scored, TOP_DAMS)


def publish_rankings(
    *,
    region: str,
    week_start: date,
    warehouse: Warehouse,
    store: RankingsStore,
    publisher: EventPublisher,
    data_dir: Path,
    now: datetime,
    new_id: Callable[[], str],
    dry_run: bool,
) -> dict[str, object]:
    rows = ranking_tables.read_top_cells(warehouse, region, week_start, TOP_CELLS)
    if not rows:
        raise JobError(
            f"no scores for {region} {week_label(week_start)}; "
            "run jobs.drying_score first"
        )
    cells = build_cells(rows)
    in_file = read_dams(data_dir / f"dams_{region}_sample.geojson")
    dams = build_dams(warehouse, region, week_start, in_file)
    summary: dict[str, object] = {
        "region": region,
        "week": week_label(week_start),
        "cells": len(cells),
        "dams": len(dams),
        "dams_in_file": len(in_file),
        "dry_run": dry_run,
    }
    event = ranking_event(region, week_start, cells, dams, new_id(), now)
    if dry_run:
        return summary
    replaced_cells = store.replace(
        region, "cells", {cell.cell_id: cell_document(cell) for cell in cells}
    )
    replaced_dams = store.replace(
        region, "dams", {dam.dam_id: dam_document(dam) for dam in dams}
    )
    message_id = publisher.publish(event)
    logger.info("published %s as message %s", event.type, message_id)
    return {
        **summary,
        "deleted": {"cells": replaced_cells.deleted, "dams": replaced_dams.deleted},
        "message_id": message_id,
        "event_id": event.id,
    }


def parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m jobs.publish_rankings",
        description="Copy the top 200 cells and top 50 dams of a week to Firestore "
        "rankings/{region}, then publish drying.ranked.",
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
        "--data-dir",
        help="directory with dams_{region}_sample.geojson "
        "(default: BARA_DATA_DIR or repo data/)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="read and validate the ranking; write and publish nothing",
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
        project = resolve_project(args.project, environ)
        config_dir = resolve_config_dir(args.config_dir, environ)
        region = load_region(config_dir, args.region)
        week_start = resolve_job_week(args.week, region)
        from google.cloud import bigquery, firestore, pubsub_v1

        try:
            return publish_rankings(
                region=region.id,
                week_start=week_start,
                warehouse=Warehouse(bigquery.Client(project=project), project, DATASET),
                store=RankingsStore(firestore.Client(project=project)),
                publisher=EventPublisher(pubsub_v1.PublisherClient(), project),
                data_dir=resolve_data_dir(args.data_dir, environ),
                now=datetime.now(UTC),
                new_id=lambda: uuid.uuid4().hex,
                dry_run=args.dry_run,
            )
        except ValidationError as error:
            raise JobError(f"event does not match the contract: {error}") from error

    return run_job(work)


if __name__ == "__main__":
    configure_logging()
    sys.exit(main())
