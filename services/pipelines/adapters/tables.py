import json
import re
from collections.abc import Sequence
from dataclasses import asdict
from datetime import date

from google.cloud.bigquery import SchemaField

from adapters.bigquery import QueryResult, TableSpec, Warehouse
from domain.drying import DryingRow
from domain.grid import StagedCell

CANAL_MAX_BYTES_BILLED = 110_000_000_000
CANAL_BUFFER_M = 5000
CANALS = "osm_canals"
PUBLIC_TABLE = re.compile(r"^[a-z0-9-]+\.[A-Za-z0-9_]+\.[A-Za-z0-9_]+$")

CELLS = TableSpec(
    name="cells",
    schema=(
        SchemaField("cell_id", "STRING", mode="REQUIRED"),
        SchemaField("region", "STRING", mode="REQUIRED"),
        SchemaField("geom", "GEOGRAPHY", mode="REQUIRED"),
        SchemaField("centroid", "GEOGRAPHY", mode="REQUIRED"),
        SchemaField("peat_class", "INT64", mode="REQUIRED"),
        SchemaField("canal_dist_m", "FLOAT64", mode="REQUIRED"),
    ),
    partition_field=None,
    clustering=("region", "cell_id"),
)

CELLS_STAGING = TableSpec(
    name="cells_staging",
    schema=(
        SchemaField("cell_id", "STRING", mode="REQUIRED"),
        SchemaField("region", "STRING", mode="REQUIRED"),
        SchemaField("geom", "GEOGRAPHY", mode="REQUIRED"),
        SchemaField("peat_class", "INT64", mode="REQUIRED"),
    ),
    partition_field=None,
    clustering=(),
)

CELL_WEEKLY_DRYING = TableSpec(
    name="cell_weekly_drying",
    schema=(
        SchemaField("cell_id", "STRING", mode="REQUIRED"),
        SchemaField("region", "STRING", mode="REQUIRED"),
        SchemaField("week_start", "DATE", mode="REQUIRED"),
        SchemaField("s1_anom_db", "FLOAT64", mode="NULLABLE"),
        SchemaField("stale_s1", "BOOL", mode="REQUIRED"),
        SchemaField("rain_30d_mm", "FLOAT64", mode="REQUIRED"),
        SchemaField("rain_deficit_pct", "FLOAT64", mode="REQUIRED"),
        SchemaField("canal_dist_m", "FLOAT64", mode="REQUIRED"),
        SchemaField("peat_class", "INT64", mode="REQUIRED"),
        SchemaField("drying_score", "FLOAT64", mode="REQUIRED"),
        SchemaField("rank", "INT64", mode="REQUIRED"),
    ),
    partition_field="week_start",
    clustering=("region", "cell_id"),
)

READ_CELLS_SQL = """
SELECT cell_id, peat_class, canal_dist_m
FROM cells
WHERE region = @region
ORDER BY cell_id
"""

DELETE_WEEK_SQL = """
DELETE FROM cell_weekly_drying WHERE region = @region AND week_start = @week_start
"""

CANALS_SELECT = """
SELECT
  osm_id,
  (SELECT value FROM UNNEST(all_tags) WHERE key = 'waterway' LIMIT 1) AS waterway,
  geometry,
  @region AS region
FROM `{osm_lines}`
WHERE EXISTS (
    SELECT 1 FROM UNNEST(all_tags)
    WHERE key = 'waterway' AND value IN ('canal', 'ditch', 'drain')
  )
  AND ST_DWITHIN(geometry, ST_GEOGFROMGEOJSON(@aoi), @buffer_m)
"""

CANALS_SQL = "CREATE TABLE osm_canals\nCLUSTER BY region\nAS" + CANALS_SELECT

ADD_CANALS_SQL = (
    "INSERT INTO osm_canals (osm_id, waterway, geometry, region)" + CANALS_SELECT
)

REGION_CANALS_SQL = "SELECT COUNT(*) AS n FROM osm_canals WHERE region = @region"

REWRITE_CELLS_SQL = """
BEGIN TRANSACTION;
DELETE FROM cells WHERE region = @region;
INSERT INTO cells (cell_id, region, geom, centroid, peat_class, canal_dist_m)
WITH staged AS (
  SELECT cell_id, region, geom, ST_CENTROID(geom) AS centroid, peat_class
  FROM cells_staging
  WHERE region = @region
),
nearest AS (
  SELECT staged.cell_id, MIN(ST_DISTANCE(staged.centroid, canal.geometry)) AS canal_dist_m
  FROM staged
  CROSS JOIN osm_canals AS canal
  WHERE canal.region = @region
  GROUP BY staged.cell_id
)
SELECT staged.cell_id, staged.region, staged.geom, staged.centroid, staged.peat_class,
  COALESCE(nearest.canal_dist_m, @no_canal_m)
FROM staged
LEFT JOIN nearest USING (cell_id);
COMMIT TRANSACTION;
"""


class InvalidPublicTable(Exception):
    pass


def check_public_table(osm_lines: str) -> str:
    if not PUBLIC_TABLE.match(osm_lines):
        raise InvalidPublicTable(f"invalid OSM lines table: {osm_lines!r}")
    return osm_lines


def canals_sql(osm_lines: str) -> str:
    return CANALS_SQL.format(osm_lines=check_public_table(osm_lines))


def add_canals_sql(osm_lines: str) -> str:
    return ADD_CANALS_SQL.format(osm_lines=check_public_table(osm_lines))


def canals_exist(warehouse: Warehouse) -> bool:
    return warehouse.table_exists(CANALS)


def region_has_canals(warehouse: Warehouse, region: str) -> bool:
    result = warehouse.query(REGION_CANALS_SQL, {"region": region})
    return bool(result.rows) and int(result.rows[0]["n"]) > 0


def create_canals(
    warehouse: Warehouse, osm_lines: str, region: str, aoi: dict, dry_run: bool
) -> QueryResult:
    sql = (
        add_canals_sql(osm_lines) if canals_exist(warehouse) else canals_sql(osm_lines)
    )
    return warehouse.query(
        sql,
        {"region": region, "aoi": json.dumps(aoi), "buffer_m": CANAL_BUFFER_M},
        max_bytes_billed=CANAL_MAX_BYTES_BILLED,
        dry_run=dry_run,
    )


def staging_row(cell: StagedCell) -> dict[str, object]:
    return {
        "cell_id": cell.cell_id,
        "region": cell.region,
        "geom": json.dumps(cell.geometry),
        "peat_class": cell.peat_class,
    }


def stage_cells(warehouse: Warehouse, cells: Sequence[StagedCell]) -> None:
    warehouse.load_rows(
        CELLS_STAGING, [staging_row(cell) for cell in cells], write="truncate"
    )


def rewrite_cells(warehouse: Warehouse, region: str) -> QueryResult:
    warehouse.ensure_table(CELLS)
    return warehouse.query(
        REWRITE_CELLS_SQL, {"region": region, "no_canal_m": CANAL_BUFFER_M}
    )


def read_cells(warehouse: Warehouse, region: str) -> QueryResult:
    return warehouse.query(READ_CELLS_SQL, {"region": region})


def drying_row(row: DryingRow) -> dict[str, object]:
    return {**asdict(row), "week_start": row.week_start.isoformat()}


def replace_week(
    warehouse: Warehouse, region: str, week_start: date, rows: Sequence[DryingRow]
) -> QueryResult:
    warehouse.ensure_table(CELL_WEEKLY_DRYING)
    deleted = warehouse.query(
        DELETE_WEEK_SQL, {"region": region, "week_start": week_start}
    )
    warehouse.load_rows(
        CELL_WEEKLY_DRYING, [drying_row(row) for row in rows], write="append"
    )
    return deleted
