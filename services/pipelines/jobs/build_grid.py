import argparse
import os
import sys
from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Protocol

from adapters import tables
from adapters.bigquery import QueryResult, Warehouse
from domain.grid import staged_cells
from ee_lib.config import RegionConfig, load_data_config, load_region, read_aoi
from jobs.cli import (
    DATASET,
    JobError,
    configure_logging,
    logger,
    resolve_config_dir,
    resolve_project,
    run_job,
)


class PeatSource(Protocol):
    def peat_cells(self, region: RegionConfig, aoi: dict) -> list[dict]: ...


def query_report(step: str, result: QueryResult) -> dict[str, object]:
    logger.info(
        "%s: %s bytes %s",
        step,
        result.bytes_billed,
        "estimated" if result.dry_run else "billed",
    )
    return {"step": step, "bytes": result.bytes_billed, "estimate": result.dry_run}


def canals_loaded(warehouse: Warehouse, region: str) -> bool:
    return tables.canals_exist(warehouse) and tables.region_has_canals(
        warehouse, region
    )


def build_grid(
    *,
    region: RegionConfig,
    aoi: dict,
    earth: PeatSource,
    warehouse: Warehouse,
    osm_lines: str,
    dry_run: bool,
) -> dict[str, object]:
    cells = staged_cells(region.id, earth.peat_cells(region, aoi))
    if not cells:
        raise JobError(f"no peat cells in the {region.id} AOI; check {region.aoi}")
    logger.info("%s: %d peat cells", region.id, len(cells))
    queries: list[dict[str, object]] = []
    if not canals_loaded(warehouse, region.id):
        created = tables.create_canals(warehouse, osm_lines, region.id, aoi, dry_run)
        queries.append(query_report("osm_canals", created))
    if not dry_run:
        tables.stage_cells(warehouse, cells)
        queries.append(
            query_report("cells", tables.rewrite_cells(warehouse, region.id))
        )
    counts = Counter(str(cell.peat_class) for cell in cells)
    return {
        "region": region.id,
        "cells": len(cells),
        "peat_class_counts": dict(sorted(counts.items())),
        "dry_run": dry_run,
        "queries": queries,
    }


def parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m jobs.build_grid",
        description="Build the 1 km peat grid for a region and write bara.cells "
        "with the distance to the nearest OSM canal.",
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
        help="compute the grid and estimate the canal query; write nothing",
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
        return build_grid(
            region=region,
            aoi=aoi,
            earth=earthengine.EarthEngineSource(data),
            warehouse=Warehouse(bigquery.Client(project=project), project, DATASET),
            osm_lines=data.datasets.osm_lines,
            dry_run=args.dry_run,
        )

    return run_job(work)


if __name__ == "__main__":
    configure_logging()
    sys.exit(main())
