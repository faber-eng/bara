from datetime import date

import pytest
from google.api_core import exceptions as gax

from adapters.earthengine import LayerNotReady, TileSourceError
from adapters.reignition import ReignitionScores


class FakeWarehouse:
    def __init__(self, rows=None, error=None):
        self.rows = rows or []
        self.error = error
        self.queries = []

    def query(self, sql, params):
        self.queries.append((sql, dict(params)))
        if self.error is not None:
            raise self.error
        return self.rows


ROW = {"cell_id": "riau-1-1", "p_reignite": 0.82, "geojson": '{"type":"Polygon"}'}


def test_a_missing_table_is_not_ready():
    scores = ReignitionScores(FakeWarehouse(error=gax.NotFound("no table")))

    with pytest.raises(LayerNotReady, match="reignition_scores"):
        scores.for_region("riau", date(2026, 10, 19))


def test_no_scores_yet_is_not_ready():
    with pytest.raises(LayerNotReady):
        ReignitionScores(FakeWarehouse(rows=[])).for_region("riau", date(2026, 10, 19))


def test_scores_come_back_per_cell_with_the_geometry():
    warehouse = FakeWarehouse(rows=[ROW])

    cells = ReignitionScores(warehouse).for_region("riau", date(2026, 10, 19))

    assert [(c.cell_id, c.p_reignite) for c in cells] == [("riau-1-1", 0.82)]
    assert cells[0].geometry == {"type": "Polygon"}
    assert warehouse.queries[0][1] == {"region": "riau", "until": date(2026, 10, 19)}


def test_any_other_warehouse_failure_is_a_tile_source_error():
    scores = ReignitionScores(FakeWarehouse(error=gax.BadRequest("cap exceeded")))

    with pytest.raises(TileSourceError):
        scores.for_region("riau", date(2026, 10, 19))


def test_the_end_of_the_week_is_exclusive():
    warehouse = FakeWarehouse(rows=[ROW])

    ReignitionScores(warehouse).for_region("riau", date(2026, 10, 19))

    assert "< @until" in warehouse.queries[0][0]
