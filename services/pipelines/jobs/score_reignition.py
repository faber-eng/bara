import argparse
import os
import sys
import uuid
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, date, datetime, timedelta

from pydantic import ValidationError

from adapters import reignition_scores
from adapters.bigquery import Warehouse
from adapters.events import EventPublisher
from domain.reignition_scores import (
    PUBLISH_DAYS,
    SERVED_MODEL,
    EventScore,
    Fire,
    InvalidScore,
    event_score,
    fire_quiet_event,
    fires_to_publish,
    group_fires,
)
from ee_lib.config import DataConfig, load_data_config, load_region
from ee_lib.weeks import local_today
from jobs.cli import (
    DATASET,
    JobError,
    UsageError,
    configure_logging,
    full_flow_region,
    logger,
    query_report,
    resolve_config_dir,
    resolve_project,
    run_job,
)

DEFAULT_DAYS = 60


def resolve_since(
    rebuild_all: bool, days: int, today: date, data: DataConfig, only: date | None
) -> date:
    if rebuild_all:
        return date(data.reignition.split_years.train[0], 1, 1)
    if days < 1:
        raise UsageError(f"--days must be at least 1, got {days}")
    window = today - timedelta(days=days)
    if only is not None and only < window:
        return only
    return window


def parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError(f"not a date: {value!r}") from error


def build_scores(rows: Sequence[Mapping[str, object]]) -> list[EventScore]:
    try:
        return [event_score(row) for row in rows]
    except InvalidScore as error:
        raise JobError(str(error)) from error


def fire_summary(fire: Fire) -> dict[str, object]:
    return {
        "event_id": fire.event_id,
        "quiet_date": fire.quiet_date,
        "cells": [
            {
                "cell_id": cell.cell_id,
                "p_reignite": cell.p_reignite,
                "top_features": [item.feature for item in cell.top_features],
            }
            for cell in fire.cells
        ],
    }


def score_reignition(
    *,
    region_id: str,
    since: date,
    today: date,
    only: date | None,
    example: bool,
    spots: int,
    warehouse: Warehouse,
    publisher: EventPublisher,
    now: datetime,
    new_id: Callable[[], str],
    dry_run: bool,
) -> dict[str, object]:
    explained = reignition_scores.explain_scores(
        warehouse, SERVED_MODEL, region_id, since
    )
    queries = [query_report("explain_predict", explained)]
    scores = build_scores(explained.rows)
    fires = fires_to_publish(
        group_fires(scores, spots), today - timedelta(days=PUBLISH_DAYS), only
    )
    if only is not None and not fires:
        raise JobError(f"no scored fire event in {region_id} went quiet on {only}")
    summary: dict[str, object] = {
        "region": region_id,
        "since": since,
        "model": SERVED_MODEL,
        "scored": len(scores),
        "fires": [fire_summary(fire) for fire in fires],
        "dry_run": dry_run,
    }
    if dry_run:
        return {**summary, "queries": queries}
    written = reignition_scores.replace_scores(
        warehouse, region_id, since, scores, SERVED_MODEL, now
    )
    queries.append(query_report("rewrite_scores", written))
    published = []
    for fire in fires:
        event = fire_quiet_event(fire, new_id(), now, example)
        message_id = publisher.publish(event)
        logger.info("published fire.quiet %s as message %s", fire.event_id, message_id)
        published.append({"event_id": fire.event_id, "message_id": message_id})
    return {**summary, "published": published, "queries": queries}


def parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m jobs.score_reignition",
        description="Score the fire events in bara.reignition_training with "
        f"{SERVED_MODEL} (ML.EXPLAIN_PREDICT), rewrite bara.reignition_scores, and "
        f"publish fire.quiet with the top cells of each fire quiet in the last "
        f"{PUBLISH_DAYS} days.",
    )
    parser.add_argument(
        "--region", required=True, help="region id in config/regions.yaml"
    )
    scope = parser.add_mutually_exclusive_group()
    scope.add_argument(
        "--all", action="store_true", help="score every event from the first train year"
    )
    scope.add_argument(
        "--days",
        type=int,
        default=DEFAULT_DAYS,
        help=f"score events quiet in the last N days (default {DEFAULT_DAYS})",
    )
    parser.add_argument(
        "--quiet-date",
        type=parse_date,
        help="publish only the fire that went quiet on this date (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--example",
        action="store_true",
        help="mark the published events as example data (judge reset removes them)",
    )
    parser.add_argument(
        "--project", help="Google Cloud project (default: GOOGLE_CLOUD_PROJECT)"
    )
    parser.add_argument(
        "--config-dir",
        help="config directory (default: BARA_CONFIG_DIR or repo config/)",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="score and print; write nothing"
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
        region_id = full_flow_region(region)
        today = local_today(datetime.now(UTC), region.zone)
        from google.cloud import bigquery, pubsub_v1

        try:
            return score_reignition(
                region_id=region_id,
                since=resolve_since(args.all, args.days, today, data, args.quiet_date),
                today=today,
                only=args.quiet_date,
                example=args.example,
                spots=data.reignition.recheck_spots_per_fire,
                warehouse=Warehouse(bigquery.Client(project=project), project, DATASET),
                publisher=EventPublisher(pubsub_v1.PublisherClient(), project),
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
