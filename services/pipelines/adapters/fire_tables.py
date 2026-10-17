from collections.abc import Sequence
from dataclasses import asdict

from google.cloud.bigquery import SchemaField

from adapters.bigquery import QueryResult, TableSpec, Warehouse
from domain.fire_events import Detection, FireEvent

FIRMS_DETECTIONS = TableSpec(
    name="firms_detections",
    schema=(
        SchemaField("region", "STRING", mode="REQUIRED"),
        SchemaField("detect_date", "DATE", mode="REQUIRED"),
        SchemaField("point", "GEOGRAPHY", mode="REQUIRED"),
        SchemaField("t21", "FLOAT64", mode="REQUIRED"),
        SchemaField("confidence", "FLOAT64", mode="REQUIRED"),
    ),
    partition_field=None,
    clustering=("region",),
)

FIRE_EVENTS = TableSpec(
    name="fire_events",
    schema=(
        SchemaField("event_id", "STRING", mode="REQUIRED"),
        SchemaField("cell_id", "STRING", mode="REQUIRED"),
        SchemaField("region", "STRING", mode="REQUIRED"),
        SchemaField("start_date", "DATE", mode="REQUIRED"),
        SchemaField("last_detection_date", "DATE", mode="REQUIRED"),
        SchemaField("quiet_date", "DATE", mode="REQUIRED"),
        SchemaField("detection_days", "INT64", mode="REQUIRED"),
        SchemaField("max_t21", "FLOAT64", mode="REQUIRED"),
        SchemaField("mean_confidence", "FLOAT64", mode="REQUIRED"),
        SchemaField("reignited", "INT64", mode="NULLABLE"),
    ),
    partition_field=None,
    clustering=("region", "cell_id"),
)

SIGHTINGS_SQL = """
SELECT
  cell.cell_id,
  detection.detect_date,
  ST_CONTAINS(cell.geom, detection.point) AS inside,
  detection.t21,
  detection.confidence
FROM cells AS cell
JOIN firms_detections AS detection
  ON ST_DWITHIN(cell.centroid, detection.point, @radius_m)
WHERE cell.region = @region AND detection.region = @region
ORDER BY cell.cell_id, detection.detect_date
"""


def detection_row(region: str, detection: Detection) -> dict[str, object]:
    return {
        "region": region,
        "detect_date": detection.detect_date.isoformat(),
        "point": f"POINT({detection.lon} {detection.lat})",
        "t21": detection.t21,
        "confidence": detection.confidence,
    }


def event_row(event: FireEvent) -> dict[str, object]:
    return {
        **asdict(event),
        "start_date": event.start_date.isoformat(),
        "last_detection_date": event.last_detection_date.isoformat(),
        "quiet_date": event.quiet_date.isoformat(),
    }


def replace_detections(
    warehouse: Warehouse, region: str, detections: Sequence[Detection]
) -> QueryResult:
    return warehouse.rewrite_region(
        FIRMS_DETECTIONS,
        region,
        [detection_row(region, detection) for detection in detections],
    )


def read_sightings(
    warehouse: Warehouse, region: str, radius_m: int, dry_run: bool = False
) -> QueryResult:
    return warehouse.query(
        SIGHTINGS_SQL, {"region": region, "radius_m": radius_m}, dry_run=dry_run
    )


def replace_events(
    warehouse: Warehouse, region: str, events: Sequence[FireEvent]
) -> QueryResult:
    return warehouse.rewrite_region(
        FIRE_EVENTS, region, [event_row(event) for event in events]
    )
