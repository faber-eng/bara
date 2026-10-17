from collections.abc import Sequence
from dataclasses import asdict
from datetime import date

from google.cloud.bigquery import SchemaField

from adapters.bigquery import QueryResult, Since, TableSpec, Warehouse
from domain.reignition_features import TrainingRow

REIGNITION_TRAINING = TableSpec(
    name="reignition_training",
    schema=(
        SchemaField("event_id", "STRING", mode="REQUIRED"),
        SchemaField("cell_id", "STRING", mode="REQUIRED"),
        SchemaField("region", "STRING", mode="REQUIRED"),
        SchemaField("quiet_date", "DATE", mode="REQUIRED"),
        SchemaField("split", "STRING", mode="REQUIRED"),
        SchemaField("reignited", "INT64", mode="NULLABLE"),
        SchemaField("peat_class", "INT64", mode="REQUIRED"),
        SchemaField("peat_fraction", "FLOAT64", mode="REQUIRED"),
        SchemaField("canal_dist_m", "FLOAT64", mode="REQUIRED"),
        SchemaField("s1_anom_db", "FLOAT64", mode="NULLABLE"),
        SchemaField("rain_7d_before_mm", "FLOAT64", mode="NULLABLE"),
        SchemaField("rain_14d_before_mm", "FLOAT64", mode="NULLABLE"),
        SchemaField("rain_7d_after_mm", "FLOAT64", mode="NULLABLE"),
        SchemaField("detection_days", "INT64", mode="REQUIRED"),
        SchemaField("max_t21", "FLOAT64", mode="REQUIRED"),
        SchemaField("mean_confidence", "FLOAT64", mode="REQUIRED"),
        SchemaField("month", "INT64", mode="REQUIRED"),
        SchemaField("prior_years_burned", "INT64", mode="REQUIRED"),
    ),
    partition_field=None,
    clustering=("region", "split"),
)

EVENTS_SQL = """
WITH cell_years AS (
  SELECT cell.cell_id, EXTRACT(YEAR FROM detection.detect_date) AS year
  FROM cells AS cell
  JOIN firms_detections AS detection ON ST_CONTAINS(cell.geom, detection.point)
  WHERE cell.region = @region AND detection.region = @region
  GROUP BY cell.cell_id, year
)
SELECT
  event.event_id,
  event.cell_id,
  event.region,
  event.quiet_date,
  event.reignited,
  event.detection_days,
  event.max_t21,
  event.mean_confidence,
  cell.peat_class,
  cell.canal_dist_m,
  ARRAY_AGG(DISTINCT cell_years.year IGNORE NULLS) AS burned_years
FROM fire_events AS event
JOIN cells AS cell ON cell.cell_id = event.cell_id
LEFT JOIN cell_years ON cell_years.cell_id = event.cell_id
WHERE event.region = @region AND event.quiet_date >= @since
GROUP BY
  event.event_id, event.cell_id, event.region, event.quiet_date, event.reignited,
  event.detection_days, event.max_t21, event.mean_confidence, cell.peat_class,
  cell.canal_dist_m
ORDER BY event.quiet_date, event.cell_id
"""


def read_events(warehouse: Warehouse, region: str, since: date) -> QueryResult:
    return warehouse.query(EVENTS_SQL, {"region": region, "since": since})


def training_row(row: TrainingRow) -> dict[str, object]:
    return {**asdict(row), "quiet_date": row.quiet_date.isoformat()}


def replace_training(
    warehouse: Warehouse, region: str, since: date, rows: Sequence[TrainingRow]
) -> QueryResult:
    return warehouse.rewrite_region(
        REIGNITION_TRAINING,
        region,
        [training_row(row) for row in rows],
        Since("quiet_date", since),
    )
