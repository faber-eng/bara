from collections.abc import Mapping, Sequence
from datetime import date, datetime, timedelta

from google.cloud.bigquery import SchemaField

from adapters.bigquery import QueryResult, TableSpec, Warehouse
from domain.eval_report import FOLLOW_WEEKS, TOP_SHARE, WeekCapture

DETECTIONS_MARGIN_DAYS = 2

EVAL_DRYING = TableSpec(
    name="eval_drying",
    schema=(
        SchemaField("evaluated_at", "TIMESTAMP", mode="REQUIRED"),
        SchemaField("region", "STRING", mode="REQUIRED"),
        SchemaField("year", "INT64", mode="REQUIRED"),
        SchemaField("weeks", "INT64", mode="REQUIRED"),
        SchemaField("hotspots", "INT64", mode="REQUIRED"),
        SchemaField("captured", "INT64", mode="REQUIRED"),
        SchemaField("capture_rate", "FLOAT64", mode="NULLABLE"),
        SchemaField("lift", "FLOAT64", mode="NULLABLE"),
        SchemaField("top_share", "FLOAT64", mode="REQUIRED"),
        SchemaField("detections_through", "DATE", mode="REQUIRED"),
    ),
    partition_field=None,
    clustering=("region",),
)

WEEK_CAPTURE_SQL = """
WITH scored AS (
  SELECT week_start, cell_id, rank,
    COUNT(*) OVER (PARTITION BY week_start) AS cells
  FROM cell_weekly_drying
  WHERE region = @region AND EXTRACT(YEAR FROM week_start) = @year
),
hits AS (
  SELECT c.cell_id, f.detect_date
  FROM firms_detections AS f
  JOIN cells AS c ON c.region = f.region AND ST_CONTAINS(c.geom, f.point)
  WHERE f.region = @region
    AND f.detect_date >= DATE(@year, 1, 1)
    AND f.detect_date < DATE_ADD(DATE(@year + 1, 1, 1), INTERVAL @tail_days DAY)
)
SELECT s.week_start, s.cells,
  COUNT(h.cell_id) AS hotspots,
  COUNTIF(
    h.cell_id IS NOT NULL AND s.rank <= CAST(CEIL(@top_share * s.cells) AS INT64)
  ) AS captured
FROM scored AS s
LEFT JOIN hits AS h
  ON h.cell_id = s.cell_id
  AND h.detect_date >= DATE_ADD(s.week_start, INTERVAL @first_day DAY)
  AND h.detect_date < DATE_ADD(s.week_start, INTERVAL @end_day DAY)
GROUP BY s.week_start, s.cells
ORDER BY s.week_start
"""

DETECTIONS_MODIFIED_SQL = """
SELECT DATE(TIMESTAMP_MILLIS(last_modified_time)) AS modified
FROM __TABLES__
WHERE table_id = 'firms_detections'
"""

REIGNITION_EVAL_SQL = """
SELECT evaluated_at, model, split, events, positives, auc,
  precision_top10, recall_top10
FROM eval_reignition
WHERE region = @region
  AND evaluated_at = (SELECT MAX(evaluated_at) FROM eval_reignition WHERE region = @region)
"""


def week_capture(row: Mapping[str, object]) -> WeekCapture:
    return WeekCapture(
        week_start=row["week_start"],
        cells=int(row["cells"]),
        hotspots=int(row["hotspots"]),
        captured=int(row["captured"]),
    )


def read_week_captures(
    warehouse: Warehouse, region: str, year: int
) -> tuple[list[WeekCapture], QueryResult]:
    first, last = FOLLOW_WEEKS
    result = warehouse.query(
        WEEK_CAPTURE_SQL,
        {
            "region": region,
            "year": year,
            "top_share": TOP_SHARE,
            "first_day": first * 7,
            "end_day": (last + 1) * 7,
            "tail_days": (last + 1) * 7,
        },
    )
    return [week_capture(row) for row in result.rows], result


def detections_through(warehouse: Warehouse) -> tuple[date, QueryResult]:
    result = warehouse.query(DETECTIONS_MODIFIED_SQL, {})
    if not result.rows:
        raise LookupError("bara.firms_detections does not exist; run jobs.fire_events")
    modified = result.rows[0]["modified"]
    return modified - timedelta(days=DETECTIONS_MARGIN_DAYS), result


def iso_row(row: Mapping[str, object]) -> dict[str, object]:
    evaluated_at = row["evaluated_at"]
    if isinstance(evaluated_at, datetime):
        return {**row, "evaluated_at": evaluated_at.isoformat()}
    return dict(row)


def read_reignition_eval(
    warehouse: Warehouse, region: str
) -> tuple[list[dict[str, object]], QueryResult]:
    result = warehouse.query(REIGNITION_EVAL_SQL, {"region": region})
    return [iso_row(row) for row in result.rows], result


def append_drying_eval(
    warehouse: Warehouse, rows: Sequence[Mapping[str, object]]
) -> None:
    warehouse.ensure_table(EVAL_DRYING)
    warehouse.load_rows(EVAL_DRYING, rows, write="append")
