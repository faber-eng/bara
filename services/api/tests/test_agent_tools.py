import asyncio
from datetime import date

import pytest

from adapters.cells import CENTROID_SQL, WEEKLY_SQL, CellRepository
from adapters.firestore_repos import (
    DamRepository,
    RankingRepository,
    VolunteerRepository,
)
from bara_agent.tools.find_people import FindPeople
from bara_agent.tools.get_area_facts import GetAreaFacts
from bara_agent.tools.rank_areas import RankAreas
from contracts import Dam, GeoPoint, RankedCell, Volunteer
from tests.fakes import (
    FakeWarehouse,
    InMemoryCollection,
    make_dam,
    make_ranked_cell,
    make_volunteer,
    weekly_row,
)

THIS_WEEK = date(2026, 10, 12)
LAST_WEEK = date(2026, 10, 5)
CENTER = {"lat": 0.5, "lon": 101.4}


def collection_of(model, items, key):
    collection = InMemoryCollection(model)
    for item in items:
        collection.put(getattr(item, key), item)
    return collection


def rank_areas_tool(*cells):
    collection = collection_of(RankedCell, cells, "cell_id")
    return RankAreas(RankingRepository(lambda region: collection))


class UnreadRankings:
    def top(self, region, limit):
        raise AssertionError("the repository must not be read")


def test_rank_areas_returns_the_top_cells_by_rank():
    cells = [make_ranked_cell(cell_id=f"riau-{n}", rank=n) for n in (3, 1, 2, 4)]

    result = asyncio.run(rank_areas_tool(*cells).rank_areas("riau", 3))

    assert result["region"] == "riau"
    assert result["week"] == "2026-W42"
    assert [c["cell_id"] for c in result["cells"]] == ["riau-1", "riau-2", "riau-3"]
    assert set(result["cells"][0]) == {"cell_id", "drying_score", "rank", "components"}
    assert result["cells"][0]["components"]["canal_dist_m"] == 140.0


def test_rank_areas_keeps_only_the_newest_week():
    stale = make_ranked_cell(cell_id="old", rank=1, week_start=LAST_WEEK)
    fresh = make_ranked_cell(cell_id="new", rank=2, week_start=THIS_WEEK)

    result = asyncio.run(rank_areas_tool(stale, fresh).rank_areas("riau", 10))

    assert [c["cell_id"] for c in result["cells"]] == ["new"]


def test_rank_areas_with_no_ranking_is_empty():
    assert asyncio.run(rank_areas_tool().rank_areas("riau")) == {
        "region": "riau",
        "week": None,
        "cells": [],
    }


@pytest.mark.parametrize("limit", [0, 201])
def test_rank_areas_rejects_a_limit_outside_1_to_200(limit):
    result = asyncio.run(RankAreas(UnreadRankings()).rank_areas("riau", limit))

    assert "limit" in result["error"]


def test_rank_areas_rejects_a_region_that_is_not_an_id():
    result = asyncio.run(RankAreas(UnreadRankings()).rank_areas("riau/cells/x"))

    assert "region" in result["error"]


def test_rank_areas_summary():
    cells = [make_ranked_cell(cell_id="riau-0412", rank=1, drying_score=91.43)]
    tool = rank_areas_tool(*cells)

    assert (
        tool.summarize(asyncio.run(tool.rank_areas("riau")))
        == "1 cell, top riau-0412 at 91.4"
    )
    assert tool.summarize({"region": "riau", "week": None, "cells": []}) == "0 cells"


def area_facts_tool(rows, dams=()):
    warehouse = FakeWarehouse({WEEKLY_SQL: rows})
    dam_repo = DamRepository(collection_of(Dam, dams, "id"))
    return GetAreaFacts(CellRepository(warehouse), dam_repo, 1_000), warehouse


def test_get_area_facts_maps_the_latest_week_and_a_trend_oldest_first():
    rows = [
        weekly_row(week_start=THIS_WEEK, drying_score=90.5, rank=1),
        weekly_row(week_start=LAST_WEEK, drying_score=80.0, rank=6),
    ]
    tool, warehouse = area_facts_tool(rows)

    facts = asyncio.run(tool.get_area_facts("riau-1-1"))

    assert warehouse.queries == [(WEEKLY_SQL, {"cell_id": "riau-1-1", "weeks": 8})]
    assert set(facts) == {
        "cell_id",
        "region",
        "week",
        "centroid",
        "components",
        "drying_score",
        "rank",
        "stale_s1",
        "trend",
        "nearby_dams",
    }
    assert facts["week"] == "2026-W42"
    assert (facts["drying_score"], facts["rank"], facts["stale_s1"]) == (90.5, 1, False)
    assert facts["components"]["rain_deficit_pct"] == 0.31
    assert facts["centroid"] == {"lat": 0.5, "lon": 101.4}
    assert facts["trend"] == [
        {"week": "2026-W41", "drying_score": 80.0},
        {"week": "2026-W42", "drying_score": 90.5},
    ]


def test_get_area_facts_keeps_a_null_radar_value_with_stale_s1():
    tool, _ = area_facts_tool([weekly_row(s1_anom_db=None, stale_s1=True)])

    facts = asyncio.run(tool.get_area_facts("riau-1-1"))

    assert facts["components"]["s1_anom_db"] is None
    assert facts["stale_s1"] is True


def test_get_area_facts_for_an_unknown_cell_is_an_error():
    tool, _ = area_facts_tool([])

    assert "riau-9-9" in asyncio.run(tool.get_area_facts("riau-9-9"))["error"]


def test_get_area_facts_lists_only_dams_within_the_radius_in_the_cell_region():
    near = make_dam(id="near", point=GeoPoint(lat=0.5, lon=101.405))
    far = make_dam(id="far", point=GeoPoint(lat=0.5, lon=101.42))
    elsewhere = make_dam(
        id="elsewhere", region="congo_cuvette", point=GeoPoint(lat=0.5, lon=101.401)
    )
    tool, _ = area_facts_tool([weekly_row()], [near, far, elsewhere])

    facts = asyncio.run(tool.get_area_facts("riau-1-1"))

    assert [d["dam_id"] for d in facts["nearby_dams"]] == ["near"]
    assert facts["nearby_dams"][0]["last_state"] == "intact"


def test_get_area_facts_summary():
    near = make_dam(id="near", point=GeoPoint(lat=0.5, lon=101.405))
    tool, _ = area_facts_tool([weekly_row(drying_score=96.84, rank=1)], [near])

    summary = tool.summarize(asyncio.run(tool.get_area_facts("riau-1-1")))

    assert summary == "riau-1-1: score 96.8, rank 1, 1 dam within 1000 m"


def find_people_tool(people, located=True):
    rows = [CENTER] if located else []
    warehouse = FakeWarehouse({CENTROID_SQL: rows})
    repo = VolunteerRepository(collection_of(Volunteer, people, "id"))
    return FindPeople(CellRepository(warehouse), repo), warehouse


def at(lon: float) -> GeoPoint:
    return GeoPoint(lat=0.5, lon=lon)


def test_find_people_returns_nearest_available_people_of_the_role():
    people = [
        make_volunteer(id="far", home=at(101.45)),
        make_volunteer(id="near", home=at(101.41)),
        make_volunteer(id="busy", home=at(101.4), available=False),
        make_volunteer(id="patrol", home=at(101.4), role="patrol"),
    ]
    tool, warehouse = find_people_tool(people)

    result = asyncio.run(tool.find_people("riau-1-1", "volunteer"))

    assert warehouse.queries == [(CENTROID_SQL, {"cell_id": "riau-1-1"})]
    assert result["cell_id"] == "riau-1-1"
    assert result["role"] == "volunteer"
    assert [p["id"] for p in result["people"]] == ["near", "far"]


def test_find_people_never_returns_home_or_contact_details():
    tool, _ = find_people_tool([make_volunteer(id="v1", home=at(101.41))])

    [person] = asyncio.run(tool.find_people("riau-1-1", "volunteer"))["people"]

    assert set(person) == {"id", "name", "role", "language", "distance_m", "example"}
    assert isinstance(person["distance_m"], int)


def test_find_people_keeps_real_and_example_people_together():
    people = [
        make_volunteer(id="sample", home=at(101.41), example=True),
        make_volunteer(id="real", home=at(101.42), example=False),
    ]
    tool, _ = find_people_tool(people)

    result = asyncio.run(tool.find_people("riau-1-1", "volunteer"))

    assert [(p["id"], p["example"]) for p in result["people"]] == [
        ("sample", True),
        ("real", False),
    ]


def test_find_people_caps_at_k():
    people = [make_volunteer(id=f"v{n}", home=at(101.4 + n / 100)) for n in range(5)]
    tool, _ = find_people_tool(people)

    assert len(asyncio.run(tool.find_people("riau-1-1", "volunteer", 2))["people"]) == 2


@pytest.mark.parametrize("k", [0, 11])
def test_find_people_rejects_k_outside_1_to_10(k):
    tool, warehouse = find_people_tool([])

    assert "k" in asyncio.run(tool.find_people("riau-1-1", "volunteer", k))["error"]
    assert warehouse.queries == []


def test_find_people_rejects_an_unknown_role():
    tool, warehouse = find_people_tool([])

    assert "role" in asyncio.run(tool.find_people("riau-1-1", "firefighter"))["error"]
    assert warehouse.queries == []


def test_find_people_for_an_unknown_cell_is_an_error():
    tool, _ = find_people_tool([make_volunteer()], located=False)

    assert "riau-9-9" in asyncio.run(tool.find_people("riau-9-9", "volunteer"))["error"]


def test_find_people_summary():
    people = [make_volunteer(id="v1", home=at(101.41))]
    tool, _ = find_people_tool(people)

    summary = tool.summarize(asyncio.run(tool.find_people("riau-1-1", "volunteer")))

    assert summary == "1 person, nearest v1 at 1112 m"
    assert tool.summarize({"cell_id": "c", "role": "volunteer", "people": []}) == (
        "0 people"
    )
