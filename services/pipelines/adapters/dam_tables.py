import json

from adapters.bigquery import Warehouse
from domain.dams import Candidate

CANDIDATES_SQL = """
WITH top AS (
  SELECT cell_id, rank FROM cell_weekly_drying
  WHERE region = @region AND week_start = @week_start AND rank <= @top_n
),
pairs AS (
  SELECT c.cell_id, c.geom, c.centroid, k.osm_id,
    ST_INTERSECTION(k.geometry, c.geom) AS piece
  FROM cells AS c
  JOIN osm_canals AS k ON k.region = c.region AND ST_INTERSECTS(k.geometry, c.geom)
  WHERE c.region = @region
),
lines AS (
  SELECT *, ST_CLOSESTPOINT(piece, centroid) AS pt,
    ROW_NUMBER() OVER (
      PARTITION BY cell_id ORDER BY ST_DISTANCE(piece, centroid), osm_id
    ) AS pick
  FROM pairs
  WHERE ST_DIMENSION(piece) = 1
)
SELECT lines.cell_id, CAST(lines.osm_id AS STRING) AS osm_id,
  ST_X(pt) AS lon, ST_Y(pt) AS lat, top.rank AS top_rank,
  ST_ASGEOJSON(ST_INTERSECTION(piece, ST_BUFFER(pt, @snippet_m))) AS canal
FROM lines
LEFT JOIN top USING (cell_id)
WHERE pick = 1
  AND ST_WITHIN(pt, ST_GEOGFROMGEOJSON(@aoi))
  AND ST_DISTANCE(pt, ST_BOUNDARY(geom)) >= @edge_m
ORDER BY lines.cell_id
"""

TOP_CELLS_SQL = """
SELECT d.cell_id, d.rank, d.drying_score, ST_ASGEOJSON(c.geom) AS geometry
FROM cell_weekly_drying AS d
JOIN cells AS c USING (region, cell_id)
WHERE d.region = @region AND d.week_start = @week_start AND d.rank <= @top_n
ORDER BY d.rank
"""

SNIPPET_M = 300
EDGE_M = 100


def candidate(row: dict) -> Candidate:
    return Candidate(
        cell_id=row["cell_id"],
        osm_id=row["osm_id"],
        lon=round(row["lon"], 6),
        lat=round(row["lat"], 6),
        top_rank=row["top_rank"],
        canal=json.loads(row["canal"]),
    )


def read_candidates(
    warehouse: Warehouse, region: str, aoi: dict, week_start, top_n: int
) -> list[Candidate]:
    result = warehouse.query(
        CANDIDATES_SQL,
        {
            "region": region,
            "aoi": json.dumps(aoi),
            "week_start": week_start,
            "top_n": top_n,
            "snippet_m": SNIPPET_M,
            "edge_m": EDGE_M,
        },
    )
    return [candidate(row) for row in result.rows]


def read_top_cells(warehouse: Warehouse, region: str, week_start, top_n: int):
    result = warehouse.query(
        TOP_CELLS_SQL, {"region": region, "week_start": week_start, "top_n": top_n}
    )
    return [
        {
            "cell_id": row["cell_id"],
            "rank": row["rank"],
            "drying_score": row["drying_score"],
            "geometry": json.loads(row["geometry"]),
        }
        for row in result.rows
    ]
