from adapters.bigquery import Warehouse

TOP_CELLS_SQL = """
SELECT d.cell_id, d.region, d.week_start, d.s1_anom_db, d.stale_s1,
  d.rain_30d_mm, d.rain_deficit_pct, d.canal_dist_m, d.peat_class,
  d.drying_score, d.rank, ST_Y(c.centroid) AS lat, ST_X(c.centroid) AS lon,
  p.rank AS prev_rank
FROM cell_weekly_drying AS d
JOIN cells AS c ON c.region = d.region AND c.cell_id = d.cell_id
LEFT JOIN cell_weekly_drying AS p
  ON p.region = d.region AND p.cell_id = d.cell_id
  AND p.week_start = DATE_SUB(@week_start, INTERVAL 7 DAY)
WHERE d.region = @region AND d.week_start = @week_start AND d.rank <= @limit
ORDER BY d.rank
"""

DAM_CELLS_SQL = """
WITH dams AS (
  SELECT JSON_VALUE(item, '$.id') AS dam_id,
    CAST(JSON_VALUE(item, '$.lon') AS FLOAT64) AS lon,
    CAST(JSON_VALUE(item, '$.lat') AS FLOAT64) AS lat
  FROM UNNEST(JSON_QUERY_ARRAY(@dams)) AS item
)
SELECT dams.dam_id, c.cell_id, d.drying_score
FROM dams
JOIN cells AS c
  ON c.region = @region AND ST_CONTAINS(c.geom, ST_GEOGPOINT(dams.lon, dams.lat))
JOIN cell_weekly_drying AS d
  ON d.region = c.region AND d.cell_id = c.cell_id AND d.week_start = @week_start
"""


def read_top_cells(warehouse: Warehouse, region: str, week_start, limit: int):
    return warehouse.query(
        TOP_CELLS_SQL, {"region": region, "week_start": week_start, "limit": limit}
    ).rows


def read_dam_cells(
    warehouse: Warehouse, region: str, week_start, dams_json: str
) -> dict[str, tuple[str, float]]:
    rows = warehouse.query(
        DAM_CELLS_SQL, {"region": region, "week_start": week_start, "dams": dams_json}
    ).rows
    return {row["dam_id"]: (row["cell_id"], row["drying_score"]) for row in rows}
