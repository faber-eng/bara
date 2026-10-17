import json
from datetime import date
from typing import Protocol

from google.api_core import exceptions as gax

from adapters.bigquery import DATASET
from adapters.earthengine import LayerNotReady
from ee_lib.layers import ScoredCell

SCORES_TABLE = "reignition_scores"
MAX_CELLS = 2000

SCORES_SQL = f"""
SELECT s.cell_id, MAX(s.p_reignite) AS p_reignite,
  ANY_VALUE(ST_ASGEOJSON(c.geom)) AS geojson
FROM {DATASET}.{SCORES_TABLE} AS s
JOIN {DATASET}.cells AS c ON c.cell_id = s.cell_id
WHERE c.region = @region AND DATE(s.quiet_date) <= @until
GROUP BY s.cell_id
ORDER BY p_reignite DESC
LIMIT {MAX_CELLS}
"""


class Queryable(Protocol):
    def query(self, sql: str, params: dict[str, object]) -> list[dict]: ...


class ReignitionScores:
    def __init__(self, warehouse: Queryable):
        self._warehouse = warehouse

    def for_region(self, region: str, until: date) -> list[ScoredCell]:
        try:
            rows = self._warehouse.query(SCORES_SQL, {"region": region, "until": until})
        except gax.NotFound as error:
            raise LayerNotReady(
                f"bara.{SCORES_TABLE} does not exist yet; the reignition scorer has not run"
            ) from error
        if not rows:
            raise LayerNotReady(f"bara.{SCORES_TABLE} has no scores for {region}")
        return [
            ScoredCell(
                cell_id=row["cell_id"],
                p_reignite=row["p_reignite"],
                geometry=json.loads(row["geojson"]),
            )
            for row in rows
        ]
