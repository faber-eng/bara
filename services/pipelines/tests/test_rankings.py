import json
from datetime import UTC, date, datetime

import pytest

from domain.rankings import (
    DamLocation,
    MalformedDamFile,
    RankingRowError,
    cell_document,
    dam_cells_param,
    dam_document,
    dam_risk,
    parse_dams,
    rank_dams,
    ranked_cell,
    ranking_event,
)

WEEK = date(2026, 10, 12)


def cell_row(rank, **overrides):
    row = {
        "cell_id": f"riau-{rank}-1",
        "region": "riau",
        "week_start": WEEK,
        "s1_anom_db": -2.5,
        "stale_s1": False,
        "rain_30d_mm": 40.0,
        "rain_deficit_pct": 0.5,
        "canal_dist_m": 120.0,
        "peat_class": 1,
        "drying_score": 96.0 - rank,
        "rank": rank,
        "lat": 0.6,
        "lon": 102.1,
        "prev_rank": None,
    }
    return {**row, **overrides}


def dam_feature(number, state="intact", checked="2026-07-01T09:00:00+07:00"):
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [102.1, 0.6]},
        "properties": {
            "id": f"dam-riau-{number:03d}",
            "canal_osm_id": "839312020",
            "region": "riau",
            "last_state": state,
            "last_checked_at": checked,
            "example": True,
        },
    }


def location(number, state="intact"):
    return parse_dams({"features": [dam_feature(number, state)]})[0]


def test_ranked_cell_carries_every_component_and_a_date_week():
    cell = ranked_cell(cell_row(3))

    assert cell.week_start == WEEK
    assert cell.rank == 3
    assert cell.components.s1_anom_db == -2.5
    assert cell.components.peat_class == 1
    assert cell.centroid.lat == 0.6
    assert cell.explanation is None
    assert cell.rank_change is None


def test_rank_change_is_previous_rank_minus_current_rank():
    assert ranked_cell(cell_row(3, prev_rank=5)).rank_change == 2
    assert ranked_cell(cell_row(3, prev_rank=1)).rank_change == -2


def test_rank_change_zero_is_kept_not_dropped():
    assert ranked_cell(cell_row(4, prev_rank=4)).rank_change == 0


def test_null_s1_and_stale_flag_pass_through():
    cell = ranked_cell(cell_row(1, s1_anom_db=None, stale_s1=True))

    assert cell.components.s1_anom_db is None
    assert cell.stale_s1 is True


def test_cell_document_stores_the_week_as_an_iso_date_string():
    document = cell_document(ranked_cell(cell_row(1)))

    assert document["week_start"] == "2026-10-12"
    assert document["centroid"] == {"lat": 0.6, "lon": 102.1}
    assert document["explanation"] is None


def test_a_cell_row_outside_the_contract_fails_loudly():
    with pytest.raises(RankingRowError):
        ranked_cell(cell_row(1, drying_score=140.0))


def test_dam_risk_adds_the_state_bonus_to_the_cell_score():
    assert (
        dam_risk(80.0, "broken") > dam_risk(80.0, "damaged") > dam_risk(80.0, "intact")
    )
    assert dam_risk(80.0, "intact") == 80.0


def test_broken_dam_in_a_middling_cell_outranks_an_intact_dam_in_a_top_cell():
    dams = [location(1, "intact"), location(2, "broken")]
    scores = {"dam-riau-001": ("riau-1-1", 95.0), "dam-riau-002": ("riau-2-1", 85.0)}

    ranked = rank_dams(dams, scores, limit=50)

    assert [d.dam_id for d in ranked] == ["dam-riau-002", "dam-riau-001"]
    assert [d.rank for d in ranked] == [1, 2]
    assert ranked[0].drying_score == 85.0


def test_rank_dams_caps_at_the_limit_and_breaks_ties_by_id():
    dams = [location(n) for n in range(1, 8)]
    scores = {d.id: ("riau-1-1", 70.0) for d in dams}

    ranked = rank_dams(dams, scores, limit=5)

    assert [d.dam_id for d in ranked] == [f"dam-riau-00{n}" for n in range(1, 6)]


def test_a_dam_without_a_scored_cell_is_left_out():
    dams = [location(1), location(2)]

    ranked = rank_dams(dams, {"dam-riau-001": ("riau-1-1", 70.0)}, limit=50)

    assert [d.dam_id for d in ranked] == ["dam-riau-001"]


def test_dam_document_keeps_the_example_flag_and_the_checked_time():
    ranked = rank_dams([location(1)], {"dam-riau-001": ("riau-1-1", 70.0)}, limit=5)[0]

    document = dam_document(ranked)

    assert document["example"] is True
    assert document["last_checked_at"] == datetime.fromisoformat(
        "2026-07-01T09:00:00+07:00"
    )


def test_parse_dams_reads_points_and_validates_the_dam_contract():
    dams = parse_dams({"features": [dam_feature(1, "broken")]})

    assert dams == [
        DamLocation(
            id="dam-riau-001",
            region="riau",
            lon=102.1,
            lat=0.6,
            state="broken",
            checked_at=datetime.fromisoformat("2026-07-01T09:00:00+07:00"),
            example=True,
        )
    ]


def test_parse_dams_rejects_a_dam_the_contract_forbids():
    feature = dam_feature(1)
    feature["properties"]["cell_id"] = "riau-1-1"

    with pytest.raises(MalformedDamFile):
        parse_dams({"features": [feature]})


def test_parse_dams_rejects_a_duplicate_id():
    with pytest.raises(MalformedDamFile):
        parse_dams({"features": [dam_feature(1), dam_feature(1)]})


def test_dam_cells_param_is_json_of_id_and_point():
    param = json.loads(dam_cells_param([location(1)]))

    assert param == [{"id": "dam-riau-001", "lon": 102.1, "lat": 0.6}]


def test_event_is_real_data_and_lists_the_first_cells_and_dams():
    cells = [ranked_cell(cell_row(n)) for n in range(1, 13)]
    dams = rank_dams(
        [location(n) for n in range(1, 13)],
        {f"dam-riau-{n:03d}": ("riau-1-1", 70.0 + n) for n in range(1, 13)},
        limit=50,
    )

    event = ranking_event(
        "riau", WEEK, cells, dams, "evt-1", datetime(2026, 10, 17, tzinfo=UTC)
    )

    assert event.type == "drying.ranked"
    assert event.example is False
    assert event.region == "riau"
    assert event.payload.week == "2026-W42"
    assert len(event.payload.top_cells) == 10
    assert event.payload.top_cells[0].rank == 1
    assert next(d.dam_id for d in event.payload.top_dams) == "dam-riau-012"
    assert len(event.payload.top_dams) == 10
