import math
from datetime import date

import pytest

from api_contracts import load_api_contracts
from domain.drying import (
    CellInput,
    MissingMeasurement,
    canal_proximity,
    join_measurements,
    peat_weight,
    pick_s1,
    rain_deficit_pct,
    rank_order,
    score_cells,
    zscores,
)
from ee_lib.config import DryingWeights, load_data_config

WEEK = date(2026, 10, 12)
WEIGHTS = DryingWeights(
    s1_anomaly=0.45, rain_deficit=0.30, canal_proximity=0.15, peat_class=0.10
)


def cell(cell_id="riau-1-1", **overrides) -> CellInput:
    fields = {
        "cell_id": cell_id,
        "peat_class": 1,
        "canal_dist_m": 500.0,
        "s1_recent_anom_db": -1.0,
        "s1_previous_anom_db": -0.5,
        "rain_30d_mm": 100.0,
        "clim_rain_30d_mm": 200.0,
    }
    return CellInput(**{**fields, **overrides})


def test_rain_deficit_is_one_minus_the_ratio():
    assert rain_deficit_pct(50.0, 200.0) == 0.75


@pytest.mark.parametrize(
    ("rain", "clim", "expected"),
    [(0.0, 100.0, 1.0), (500.0, 100.0, -1.0), (0.0, 0.0, 0.0), (5.0, 0.0, -1.0)],
)
def test_rain_deficit_clips_and_handles_a_dry_climatology(rain, clim, expected):
    assert rain_deficit_pct(rain, clim) == expected


def test_canal_proximity_decays_per_kilometre():
    assert canal_proximity(0.0) == 1.0
    assert canal_proximity(1000.0) == pytest.approx(math.exp(-1))


def test_peat_weight_per_class():
    assert peat_weight(1) == 1.0
    assert peat_weight(2) == 0.6


@pytest.mark.parametrize("peat_class", [0, 3])
def test_peat_weight_rejects_other_classes(peat_class):
    with pytest.raises(ValueError):
        peat_weight(peat_class)


def test_pick_s1_prefers_the_recent_window():
    assert pick_s1(-1.0, -0.5) == (-1.0, False)


def test_pick_s1_carries_the_previous_window_and_marks_it_stale():
    assert pick_s1(None, -0.5) == (-0.5, True)


def test_pick_s1_with_no_window_is_null_and_stale():
    assert pick_s1(None, None) == (None, True)


def test_zscores_use_non_null_values_and_give_null_zero():
    assert zscores([-2.0, 0.0, None]) == [-1.0, 1.0, 0.0]


def test_zscores_of_a_constant_are_zero():
    assert zscores([3.0, 3.0]) == [0.0, 0.0]


def test_zscores_of_all_null_are_zero():
    assert zscores([None, None]) == [0.0, 0.0]


def test_rank_order_is_ordinal_high_first_ties_by_cell_id():
    ranks = rank_order([("b", 50.0), ("a", 50.0), ("c", 90.0), ("d", 10.0)])

    assert ranks == {"c": 1, "a": 2, "b": 3, "d": 4}


def test_scores_stay_between_0_and_100():
    cells = [
        cell("riau-1-1", s1_recent_anom_db=-6.0, rain_30d_mm=0.0, canal_dist_m=0.0),
        cell("riau-1-2", s1_recent_anom_db=4.0, rain_30d_mm=900.0, peat_class=2),
        cell("riau-1-3", canal_dist_m=12000.0),
    ]

    rows = score_cells("riau", WEEK, cells, WEIGHTS)

    assert all(0 <= row.drying_score <= 100 for row in rows)
    assert sorted(row.rank for row in rows) == [1, 2, 3]


def test_a_more_negative_s1_anomaly_scores_higher():
    rows = score_cells(
        "riau",
        WEEK,
        [
            cell("riau-1-1", s1_recent_anom_db=-3.0),
            cell("riau-1-2", s1_recent_anom_db=1.0),
        ],
        WEIGHTS,
    )
    by_id = {row.cell_id: row for row in rows}

    assert by_id["riau-1-1"].drying_score > by_id["riau-1-2"].drying_score
    assert by_id["riau-1-1"].rank == 1


def test_score_matches_the_formula_with_the_repo_weights(config_dir):
    weights = load_data_config(config_dir).drying.weights
    cells = [
        cell("riau-1-1", s1_recent_anom_db=-2.0, rain_30d_mm=0.0, canal_dist_m=0.0),
        cell("riau-1-2", s1_recent_anom_db=0.0, rain_30d_mm=200.0, canal_dist_m=1000.0),
    ]

    rows = score_cells("riau", WEEK, cells, weights)

    first_sum = 0.45 * 1 + 0.30 * 1 + 0.15 * 1 + 0.10 * 0
    assert rows[0].drying_score == pytest.approx(100 / (1 + math.exp(-first_sum)))
    assert rows[1].drying_score == pytest.approx(100 / (1 + math.exp(first_sum)))


def test_identical_cells_all_score_50():
    rows = score_cells("riau", WEEK, [cell("riau-1-1"), cell("riau-1-2")], WEIGHTS)

    assert [row.drying_score for row in rows] == [50.0, 50.0]
    assert [row.rank for row in rows] == [1, 2]


def test_a_single_cell_scores_50_and_ranks_first():
    rows = score_cells("riau", WEEK, [cell()], WEIGHTS)

    assert rows[0].drying_score == 50.0
    assert rows[0].rank == 1


def test_no_cells_give_no_rows():
    assert score_cells("riau", WEEK, [], WEIGHTS) == []


def test_a_null_s1_cell_gets_zero_s1_z_and_is_stale():
    cells = [
        cell("riau-1-1", s1_recent_anom_db=-2.0),
        cell("riau-1-2", s1_recent_anom_db=0.0),
        cell("riau-1-3", s1_recent_anom_db=None, s1_previous_anom_db=None),
    ]

    rows = {row.cell_id: row for row in score_cells("riau", WEEK, cells, WEIGHTS)}

    assert rows["riau-1-3"].s1_anom_db is None
    assert rows["riau-1-3"].stale_s1 is True
    assert rows["riau-1-3"].drying_score == 50.0
    assert rows["riau-1-1"].stale_s1 is False


def test_rows_carry_the_components():
    row = score_cells("riau", WEEK, [cell(canal_dist_m=250.0, peat_class=2)], WEIGHTS)[
        0
    ]

    assert row.region == "riau"
    assert row.week_start == WEEK
    assert row.s1_anom_db == -1.0
    assert row.rain_30d_mm == 100.0
    assert row.rain_deficit_pct == 0.5
    assert row.canal_dist_m == 250.0
    assert row.peat_class == 2


def test_rows_validate_against_the_ranking_contracts():
    contracts = load_api_contracts()
    cells = [cell("riau-1-1"), cell("riau-1-2", s1_recent_anom_db=None)]

    for row in score_cells("riau", WEEK, cells, WEIGHTS):
        components = contracts.RankingComponents(
            s1_anom_db=row.s1_anom_db,
            rain_30d_mm=row.rain_30d_mm,
            rain_deficit_pct=row.rain_deficit_pct,
            canal_dist_m=row.canal_dist_m,
            peat_class=row.peat_class,
        )
        contracts.RankedCell(
            cell_id=row.cell_id,
            region=row.region,
            week_start=row.week_start,
            centroid=contracts.GeoPoint(lat=0.5, lon=102.2),
            components=components,
            drying_score=row.drying_score,
            rank=row.rank,
            rank_change=None,
            stale_s1=row.stale_s1,
            explanation=None,
        )


def test_join_pairs_cells_with_their_measurements():
    cells = [{"cell_id": "riau-1-1", "peat_class": 1, "canal_dist_m": 10.0}]
    measured = [
        {
            "cell_id": "riau-1-1",
            "s1_recent_anom_db": -1.5,
            "rain_30d_mm": 80.0,
            "clim_rain_30d_mm": 160.0,
        }
    ]

    joined = join_measurements(cells, measured)

    assert joined == [
        CellInput(
            cell_id="riau-1-1",
            peat_class=1,
            canal_dist_m=10.0,
            s1_recent_anom_db=-1.5,
            s1_previous_anom_db=None,
            rain_30d_mm=80.0,
            clim_rain_30d_mm=160.0,
        )
    ]


def test_join_raises_when_a_cell_has_no_measurement():
    cells = [{"cell_id": "riau-1-1", "peat_class": 1, "canal_dist_m": 10.0}]

    with pytest.raises(MissingMeasurement, match="riau-1-1"):
        join_measurements(cells, [])


def test_join_raises_when_rain_is_missing():
    cells = [{"cell_id": "riau-1-1", "peat_class": 1, "canal_dist_m": 10.0}]
    measured = [{"cell_id": "riau-1-1", "rain_30d_mm": None, "clim_rain_30d_mm": 1.0}]

    with pytest.raises(MissingMeasurement, match="rain_30d_mm"):
        join_measurements(cells, measured)
