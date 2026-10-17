import argparse
import os
import sys
from collections import Counter
from collections.abc import Mapping, Sequence
from datetime import UTC, date, datetime, timedelta
from typing import Protocol

from adapters import fire_tables
from adapters.bigquery import Warehouse
from domain.fire_events import (
    Detection,
    EventRules,
    FireEvent,
    InvalidDetection,
    InvalidSighting,
    build_events,
    detection,
    detection_buffer_m,
    sighting,
)
from ee_lib.config import ReignitionConfig, load_data_config, load_region, read_aoi
from ee_lib.weeks import local_today
from jobs.cli import (
    DATASET,
    JobError,
    configure_logging,
    logger,
    query_report,
    resolve_config_dir,
    resolve_project,
    run_job,
)

ONE_DAY = timedelta(days=1)


class FireSource(Protocol):
    def firms_last_day(self, before: date) -> date: ...

    def fire_detections(
        self, aoi: dict, buffer_m: int, start: date, end: date
    ) -> list[dict]: ...


def event_rules(rules: ReignitionConfig) -> EventRules:
    return EventRules(
        quiet_days=rules.quiet_days,
        label_window_days=rules.label_window_days,
        first_year=rules.split_years.train[0],
        last_year=rules.split_years.test,
    )


def parse_detections(features: Sequence[dict]) -> list[Detection]:
    try:
        return [detection(feature) for feature in features]
    except InvalidDetection as error:
        raise JobError(str(error)) from error


def extract_detections(
    earth: FireSource,
    aoi: dict,
    rules: ReignitionConfig,
    buffer_m: int,
    observed_until: date,
) -> list[Detection]:
    found: list[Detection] = []
    for year in range(rules.history_from_year, observed_until.year + 1):
        end = min(date(year + 1, 1, 1), observed_until + ONE_DAY)
        features = earth.fire_detections(aoi, buffer_m, date(year, 1, 1), end)
        logger.info("FIRMS %d: %d detections", year, len(features))
        found.extend(parse_detections(features))
    return found


def build_region_events(
    region: str,
    rows: Sequence[Mapping[str, object]],
    rules: ReignitionConfig,
    observed_until: date,
) -> list[FireEvent]:
    try:
        sightings = [sighting(row) for row in rows]
    except InvalidSighting as error:
        raise JobError(str(error)) from error
    return build_events(region, sightings, event_rules(rules), observed_until)


def year_counts(events: Sequence[FireEvent]) -> dict[int, dict[str, int]]:
    totals = Counter(event.quiet_date.year for event in events)
    positives = Counter(
        event.quiet_date.year for event in events if event.reignited == 1
    )
    return {
        year: {"events": totals[year], "reignited": positives[year]}
        for year in sorted(totals)
    }


def summarize(events: Sequence[FireEvent]) -> dict[str, object]:
    return {
        "events": len(events),
        "reignited": sum(1 for event in events if event.reignited == 1),
        "unlabeled": sum(1 for event in events if event.reignited is None),
        "years": year_counts(events),
    }


def fire_events(
    *,
    region: str,
    aoi: dict,
    rules: ReignitionConfig,
    grid_cell_m: int,
    today: date,
    earth: FireSource,
    warehouse: Warehouse,
    dry_run: bool,
) -> dict[str, object]:
    observed_until = earth.firms_last_day(today + ONE_DAY) - ONE_DAY
    buffer_m = detection_buffer_m(rules.label_radius_m, grid_cell_m)
    detections = extract_detections(earth, aoi, rules, buffer_m, observed_until)
    if not detections:
        raise JobError(f"no FIRMS detections for {region}; nothing was written")
    summary: dict[str, object] = {
        "region": region,
        "observed_until": observed_until,
        "detections": len(detections),
        "dry_run": dry_run,
    }
    if dry_run:
        estimate = fire_tables.read_sightings(
            warehouse, region, rules.label_radius_m, dry_run=True
        )
        return {**summary, "queries": [query_report("read_sightings", estimate)]}
    queries = [
        query_report(
            "rewrite_detections",
            fire_tables.replace_detections(warehouse, region, detections),
        )
    ]
    read = fire_tables.read_sightings(warehouse, region, rules.label_radius_m)
    queries.append(query_report("read_sightings", read))
    events = build_region_events(region, read.rows, rules, observed_until)
    if not events:
        raise JobError(f"no fire events for {region}; check the FIRMS detections")
    queries.append(
        query_report(
            "rewrite_events", fire_tables.replace_events(warehouse, region, events)
        )
    )
    logger.info("%s: wrote %d fire events", region, len(events))
    return {**summary, **summarize(events), "queries": queries}


def parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m jobs.fire_events",
        description="Load the FIRMS detections of a region into bara.firms_detections, "
        "cluster them into fire events per cell with the reignited label, and "
        "rewrite the region in bara.fire_events.",
    )
    parser.add_argument(
        "--region", required=True, help="region id in config/regions.yaml"
    )
    parser.add_argument(
        "--project", help="Google Cloud project (default: GOOGLE_CLOUD_PROJECT)"
    )
    parser.add_argument(
        "--config-dir",
        help="config directory (default: BARA_CONFIG_DIR or repo config/)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="read the detections and estimate the query; write nothing",
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
        from google.cloud import bigquery

        from adapters import earthengine
        from ee_lib import session

        session.initialize(project)
        return fire_events(
            region=region.id,
            aoi=aoi,
            rules=data.reignition,
            grid_cell_m=data.grid_cell_m,
            today=local_today(datetime.now(UTC), region.zone),
            earth=earthengine.EarthEngineSource(data),
            warehouse=Warehouse(bigquery.Client(project=project), project, DATASET),
            dry_run=args.dry_run,
        )

    return run_job(work)


if __name__ == "__main__":
    configure_logging()
    sys.exit(main())
