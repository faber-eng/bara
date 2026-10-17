from datetime import timedelta

import pytest

from api_contracts import contracts
from domain.dams import (
    Candidate,
    DamPlan,
    DamShapeError,
    cell_grid_index,
    dam_feature,
    plan_dams,
    spread,
)

LINE = {"type": "LineString", "coordinates": [[102.0, 0.5], [102.001, 0.5]]}


def candidate(x, y, top_rank=None, region="riau"):
    return Candidate(
        cell_id=f"{region}-{x}-{y}",
        osm_id=str(1000 + x * 100 + y),
        lon=102.0 + x / 1000,
        lat=0.4 + y / 1000,
        top_rank=top_rank,
        canal=LINE,
    )


def grid(width, height, top=None):
    top = top or {}
    return [
        candidate(x, y, top.get((x, y))) for x in range(width) for y in range(height)
    ]


def test_cell_grid_index_reads_x_and_y_from_the_cell_id():
    assert cell_grid_index("riau-218-88") == (218, 88)
    assert cell_grid_index("congo_cuvette-3-14") == (3, 14)


def test_cell_grid_index_rejects_a_malformed_cell_id():
    with pytest.raises(DamShapeError):
        cell_grid_index("riau-218")


def test_spread_takes_the_candidate_farthest_from_the_seeds_first():
    pool = [candidate(x, 0) for x in range(1, 10)]

    picked = spread(pool, seeds=[(0, 0)], count=2)

    assert picked[0].cell_id == "riau-9-0"
    assert len(picked) == 2


def test_spread_is_deterministic_and_never_repeats_a_cell():
    pool = grid(6, 6)

    first = spread(pool, seeds=[(0, 0)], count=10)
    second = spread(list(reversed(pool)), seeds=[(0, 0)], count=10)

    assert [c.cell_id for c in first] == [c.cell_id for c in second]
    assert len({c.cell_id for c in first}) == 10


def test_spread_returns_every_candidate_when_asked_for_more_than_exist():
    assert len(spread(grid(2, 2), seeds=[], count=10)) == 4


def plan(count=12, top=None):
    top = top if top is not None else {(1, 1): 2, (4, 4): 1, (7, 7): 5, (8, 8): 9}
    return plan_dams("riau", grid(10, 10, top), count=count)


def test_exactly_three_dams_sit_in_top_cells_with_one_state_each_by_rank():
    dams = plan()

    in_top = sorted(
        (dam for dam in dams if dam.top_rank is not None), key=lambda d: d.top_rank
    )
    assert [(d.cell_id, d.state) for d in in_top] == [
        ("riau-4-4", "broken"),
        ("riau-1-1", "damaged"),
        ("riau-7-7", "intact"),
    ]


def test_plan_has_the_requested_count_on_distinct_cells_with_unique_ids():
    dams = plan(count=12)

    assert len(dams) == 12
    assert len({d.cell_id for d in dams}) == 12
    assert len({d.id for d in dams}) == 12
    assert all(d.id.startswith("dam-riau-") for d in dams)


def test_plan_is_identical_on_every_run():
    assert plan() == plan()


def test_plan_needs_three_top_cells_with_a_canal():
    with pytest.raises(DamShapeError):
        plan(top={(1, 1): 2, (4, 4): 1})


def test_the_rest_of_the_dams_get_a_mix_of_states_and_prior_checks():
    dams = plan_dams("riau", grid(12, 12, {(1, 1): 2, (4, 4): 1, (7, 7): 5}), count=40)

    states = {d.state for d in dams}
    assert {"intact", "damaged", "broken"} <= states
    unchecked = [d for d in dams if d.checked_at is None]
    assert all(d.state == "unknown" for d in unchecked)
    assert all(d.checked_at is not None for d in dams if d.state != "unknown")


def test_dam_feature_validates_as_a_dam_contract_and_is_an_example():
    dam: DamPlan = plan()[0]

    feature = dam_feature(dam)
    properties = feature["properties"]
    model = contracts.Dam.model_validate(
        {
            **properties,
            "point": {
                "lat": feature["geometry"]["coordinates"][1],
                "lon": feature["geometry"]["coordinates"][0],
            },
        }
    )

    assert feature["geometry"]["type"] == "Point"
    assert model.example is True
    assert model.canal_osm_id == dam.osm_id
    assert set(properties) == set(contracts.Dam.model_fields) - {"point"}


def test_prior_check_is_before_the_scenario_start():
    dams = plan(count=12)

    for dam in dams:
        if dam.checked_at is not None:
            assert dam.checked_at.utcoffset() == timedelta(hours=7)
            assert dam.checked_at.isoformat() < "2026-07-20T08:00:00+07:00"
