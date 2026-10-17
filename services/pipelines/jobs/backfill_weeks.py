import argparse
import os
import sys
import uuid
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, date, datetime, timedelta

from pydantic import ValidationError

from adapters import earthengine
from adapters.bigquery import Warehouse
from adapters.events import EventPublisher
from adapters.rankings_store import RankingsStore
from ee_lib import session
from ee_lib.config import RegionConfig, load_data_config, load_region, read_aoi
from ee_lib.weeks import (
    FutureWeek,
    InvalidWeek,
    local_today,
    resolve_week,
    week_label,
)
from jobs import drying_score, publish_rankings
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

DEFAULT_FIRST_WEEK = "2026-W20"
ONE_WEEK = timedelta(days=7)

Score = Callable[[date], dict[str, object]]
Publish = Callable[[date, bool], dict[str, object]]


def weeks_between(first: date, last: date) -> list[date]:
    if first > last:
        raise UsageError(f"{week_label(first)} is after {week_label(last)}")
    count = (last - first).days // 7 + 1
    return [first + ONE_WEEK * step for step in range(count)]


def backfill(
    weeks: Sequence[date], latest_week: date, score: Score, publish: Publish
) -> list[dict]:
    summaries = []
    for week_start in weeks:
        scored = score(week_start)
        published = publish(week_start, week_start == latest_week)
        logger.info(
            "%s: %s cells scored, %s published",
            week_label(week_start),
            scored.get("cells"),
            published.get("cells"),
        )
        summaries.append(
            {"week": week_label(week_start), "scored": scored, "published": published}
        )
    return summaries


def parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m jobs.backfill_weeks",
        description="Score and snapshot every ISO week in a range, oldest first. "
        "A rerun replaces each week.",
    )
    parser.add_argument("--region", required=True)
    parser.add_argument("--from-week", default=DEFAULT_FIRST_WEEK)
    parser.add_argument(
        "--to-week", help="ISO week (default: the current week in the region)"
    )
    parser.add_argument("--project")
    parser.add_argument("--config-dir")
    parser.add_argument("--data-dir")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


def resolve_range(args: argparse.Namespace, region: RegionConfig) -> list[date]:
    now = datetime.now(UTC)
    try:
        first = resolve_week(args.from_week, now, region.zone)
        last = resolve_week(args.to_week, now, region.zone)
    except (InvalidWeek, FutureWeek) as error:
        raise UsageError(str(error)) from error
    return weeks_between(first, last)


def main(
    argv: Sequence[str] | None = None, environ: Mapping[str, str] = os.environ
) -> int:
    args = parse_args(argv)

    def work() -> dict[str, object]:
        project = resolve_project(args.project, environ)
        config_dir = resolve_config_dir(args.config_dir, environ)
        data = load_data_config(config_dir)
        region = load_region(config_dir, args.region)
        weeks = resolve_range(args, region)
        aoi = read_aoi(config_dir, region)
        from google.cloud import bigquery, firestore, pubsub_v1

        session.initialize(project)
        warehouse = Warehouse(bigquery.Client(project=project), project, DATASET)
        earth = earthengine.EarthEngineSource(data)
        store = RankingsStore(firestore.Client(project=project))
        publisher = EventPublisher(pubsub_v1.PublisherClient(), project)
        data_dir = resolve_data_dir(args.data_dir, environ)

        def score(week_start: date) -> dict[str, object]:
            return drying_score.drying_score(
                region=region,
                aoi=aoi,
                week_start=week_start,
                today=local_today(datetime.now(UTC), region.zone),
                earth=earth,
                warehouse=warehouse,
                drying=data.drying,
                dry_run=args.dry_run,
            )

        def publish(week_start: date, latest: bool) -> dict[str, object]:
            if args.dry_run:
                return {"skipped": "dry_run"}
            return publish_rankings.publish_rankings(
                region=region.id,
                week_start=week_start,
                warehouse=warehouse,
                store=store,
                publisher=publisher,
                data_dir=data_dir,
                now=datetime.now(UTC),
                new_id=lambda: uuid.uuid4().hex,
                dry_run=args.dry_run,
                latest=latest,
                announce=False,
            )

        latest_week = resolve_week(None, datetime.now(UTC), region.zone)
        try:
            summaries = backfill(weeks, latest_week, score, publish)
        except ValidationError as error:
            raise JobError(f"event does not match the contract: {error}") from error
        return {"region": region.id, "weeks": summaries}

    return run_job(work)


if __name__ == "__main__":
    configure_logging()
    sys.exit(main())
