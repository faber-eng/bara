from collections.abc import Mapping
from datetime import date
from typing import NamedTuple, Protocol

from pydantic import BaseModel, ConfigDict

from adapters.bigquery import DATASET
from contracts import GeoPoint, RankingComponents

WEEKLY_SQL = f"""
SELECT d.cell_id, d.region, d.week_start, d.s1_anom_db, d.stale_s1,
       d.rain_30d_mm, d.rain_deficit_pct, d.canal_dist_m, d.peat_class,
       d.drying_score, d.rank,
       ST_Y(c.centroid) AS lat, ST_X(c.centroid) AS lon
FROM {DATASET}.cell_weekly_drying AS d
JOIN {DATASET}.cells AS c ON c.cell_id = d.cell_id
WHERE d.cell_id = @cell_id
ORDER BY d.week_start DESC
LIMIT @weeks
"""

CENTROID_SQL = f"""
SELECT ST_Y(centroid) AS lat, ST_X(centroid) AS lon
FROM {DATASET}.cells
WHERE cell_id = @cell_id
"""

ALL_CELLS_LIMIT = 10_000

ALL_CELLS_SQL = f"""
SELECT d.cell_id, d.week_start, d.drying_score, d.rank,
       ST_Y(c.centroid) AS lat, ST_X(c.centroid) AS lon
FROM {DATASET}.cell_weekly_drying AS d
JOIN {DATASET}.cells AS c ON c.cell_id = d.cell_id
WHERE d.region = @region
  AND d.week_start = (
    SELECT MAX(week_start) FROM {DATASET}.cell_weekly_drying WHERE region = @region
  )
ORDER BY d.rank
LIMIT @limit
"""


class Queryable(Protocol):
    def query(self, sql: str, params: Mapping[str, object]) -> list[dict]: ...


class CellPoint(NamedTuple):
    cell_id: str
    week_start: date
    lat: float
    lon: float
    drying_score: float
    rank: int


class CellWeek(BaseModel):
    model_config = ConfigDict(frozen=True)

    cell_id: str
    region: str
    week_start: date
    centroid: GeoPoint
    components: RankingComponents
    drying_score: float
    rank: int
    stale_s1: bool


def to_cell_week(row: Mapping[str, object]) -> CellWeek:
    return CellWeek.model_validate(
        {
            "cell_id": row["cell_id"],
            "region": row["region"],
            "week_start": row["week_start"],
            "centroid": {"lat": row["lat"], "lon": row["lon"]},
            "components": {
                "s1_anom_db": row["s1_anom_db"],
                "rain_30d_mm": row["rain_30d_mm"],
                "rain_deficit_pct": row["rain_deficit_pct"],
                "canal_dist_m": row["canal_dist_m"],
                "peat_class": row["peat_class"],
            },
            "drying_score": row["drying_score"],
            "rank": row["rank"],
            "stale_s1": row["stale_s1"],
        }
    )


class CellRepository:
    def __init__(self, warehouse: Queryable):
        self._warehouse = warehouse

    def weekly(self, cell_id: str, weeks: int) -> list[CellWeek]:
        rows = self._warehouse.query(WEEKLY_SQL, {"cell_id": cell_id, "weeks": weeks})
        return [to_cell_week(row) for row in rows]

    def centroid(self, cell_id: str) -> GeoPoint | None:
        rows = self._warehouse.query(CENTROID_SQL, {"cell_id": cell_id})
        if not rows:
            return None
        return GeoPoint(lat=rows[0]["lat"], lon=rows[0]["lon"])

    def all_cells(self, region: str) -> list[CellPoint]:
        rows = self._warehouse.query(
            ALL_CELLS_SQL, {"region": region, "limit": ALL_CELLS_LIMIT}
        )
        return [
            CellPoint(
                cell_id=row["cell_id"],
                week_start=row["week_start"],
                lat=row["lat"],
                lon=row["lon"],
                drying_score=row["drying_score"],
                rank=row["rank"],
            )
            for row in rows
        ]
