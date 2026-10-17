from datetime import date

from adapters.cells import CENTROID_SQL, WEEKLY_SQL, CellRepository
from contracts import GeoPoint
from tests.fakes import FakeWarehouse, weekly_row


def test_weekly_maps_rows_newest_first_with_the_cell_as_a_parameter():
    rows = [
        weekly_row(week_start=date(2026, 10, 12), drying_score=90.5, rank=1),
        weekly_row(week_start=date(2026, 10, 5), drying_score=80.0, rank=7),
    ]
    warehouse = FakeWarehouse({WEEKLY_SQL: rows})

    weeks = CellRepository(warehouse).weekly("riau-1-1", 8)

    assert warehouse.queries == [(WEEKLY_SQL, {"cell_id": "riau-1-1", "weeks": 8})]
    assert "riau-1-1" not in WEEKLY_SQL
    assert [week.week_start for week in weeks] == [
        date(2026, 10, 12),
        date(2026, 10, 5),
    ]
    latest = weeks[0]
    assert latest.region == "riau"
    assert latest.centroid == GeoPoint(lat=0.5, lon=101.4)
    assert latest.components.canal_dist_m == 140.0
    assert latest.components.peat_class == 1
    assert (latest.drying_score, latest.rank, latest.stale_s1) == (90.5, 1, False)


def test_a_null_radar_value_stays_null():
    warehouse = FakeWarehouse(
        {WEEKLY_SQL: [weekly_row(s1_anom_db=None, stale_s1=True)]}
    )

    [week] = CellRepository(warehouse).weekly("riau-1-1", 8)

    assert week.components.s1_anom_db is None
    assert week.stale_s1 is True


def test_weekly_for_an_unknown_cell_is_empty():
    assert CellRepository(FakeWarehouse()).weekly("nope", 8) == []


def test_centroid_reads_the_cell_location():
    warehouse = FakeWarehouse({CENTROID_SQL: [{"lat": 0.8, "lon": 102.47}]})

    centroid = CellRepository(warehouse).centroid("riau-218-88")

    assert warehouse.queries == [(CENTROID_SQL, {"cell_id": "riau-218-88"})]
    assert centroid == GeoPoint(lat=0.8, lon=102.47)


def test_centroid_of_an_unknown_cell_is_none():
    assert CellRepository(FakeWarehouse()).centroid("nope") is None
