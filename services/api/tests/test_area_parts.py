import asyncio
import threading
from datetime import UTC, datetime, timedelta

import pytest

from adapters.area_regions import load_area_regions
from adapters.earthengine_area import AreaSourceError, scored_cell
from bara_agent.tools.run_area_ranking import MAX_AREA_RUNS, RunAreaRanking
from contracts import AreaRanking, AreaRunState
from domain.area_cache import AreaRankingCache
from domain.area_limit import RUNS_PER_HOUR, decide
from domain.area_rank import AreaMeasure
from tests.area_support import RIAU_SQUARE, FakeAreaSource, make_ranker, square
from tests.fakes import FakeToolContext

HASH = "a" * 64


def ranking():
    return AreaRanking(
        status="no_peat",
        region="riau",
        week="2026-W42",
        polygon_hash=HASH,
        area_km2=10,
        peat_cells=0,
        cells=[],
        tile_url_template=None,
        cached=False,
    )


def test_the_cache_drops_an_entry_after_its_ttl():
    now = [0.0]
    cache = AreaRankingCache(ttl_seconds=10, clock=lambda: now[0])
    cache.put("k", ranking())
    now[0] = 9.9
    assert cache.get("k") is not None
    now[0] = 10.0
    assert cache.get("k") is None


def test_the_cache_evicts_the_least_recently_used_entry():
    cache = AreaRankingCache(max_entries=2)
    cache.put("a", ranking())
    cache.put("b", ranking())
    cache.get("a")
    cache.put("c", ranking())
    assert cache.get("b") is None
    assert cache.get("a") is not None


def test_the_limit_counts_only_runs_inside_the_hour():
    now = datetime(2026, 10, 17, 4, 0, tzinfo=UTC)
    old = [now - timedelta(minutes=61)] * 5
    recent = [now - timedelta(minutes=i) for i in range(RUNS_PER_HOUR - 1)]

    state, wait = decide(AreaRunState(runs=old + recent), now)

    assert wait == 0
    assert len(state.runs) == RUNS_PER_HOUR


def test_the_limit_names_the_wait_until_the_oldest_run_leaves():
    now = datetime(2026, 10, 17, 4, 0, tzinfo=UTC)
    runs = [now - timedelta(minutes=59)] + [now] * (RUNS_PER_HOUR - 1)

    state, wait = decide(AreaRunState(runs=runs), now)

    assert state is None
    assert wait == 60


def test_a_cell_feature_becomes_a_scored_cell_with_the_ring_centre():
    feature = {
        "geometry": {
            "type": "Polygon",
            "coordinates": [[[1, 1], [2, 1], [2, 2], [1, 2], [1, 1]]],
        },
        "properties": {"grid_index": "12,-3", "mean": 71.25, "peat_mode": 1},
    }

    cell = scored_cell("riau", feature)

    assert (cell.cell_id, cell.lon, cell.lat, cell.drying_score) == (
        "riau-12--3",
        1.5,
        1.5,
        71.25,
    )


def test_a_cell_without_a_grid_index_is_a_source_error():
    feature = {
        "geometry": {"type": "Polygon", "coordinates": [[[1, 1], [2, 1], [1, 1]]]},
        "properties": {"mean": 1.0},
    }
    with pytest.raises(AreaSourceError):
        scored_cell("riau", feature)


def test_every_region_with_drying_settings_takes_area_runs(settings):
    regions = load_area_regions(settings.config_dir)

    assert [candidate.region.id for candidate in regions] == ["riau", "congo_cuvette"]
    assert regions[0].box.west == 101.95


def run_tool(tool, geojson, context=None):
    coordinates = geojson.get("coordinates")
    return asyncio.run(tool.function(coordinates, context or FakeToolContext()))


def test_the_tool_returns_the_ranking_and_summarises_it(settings):
    tool = RunAreaRanking(make_ranker(settings))

    result = run_tool(tool, RIAU_SQUARE)

    assert result["status"] == "ranked"
    assert tool.summarize(result) == "3 cells, top riau-1-2 at 80.0"


def test_the_tool_reports_no_peat(settings):
    ranker = make_ranker(settings, FakeAreaSource(AreaMeasure(0, [], None)))
    tool = RunAreaRanking(ranker)

    assert tool.summarize(run_tool(tool, RIAU_SQUARE)) == "no mapped peat"


def test_the_tool_returns_an_error_for_a_bad_polygon(settings):
    result = run_tool(
        RunAreaRanking(make_ranker(settings)), {"coordinates": [[[1, 1]]]}
    )

    assert "area rejected" in str(result["error"])


def test_the_tool_returns_an_error_when_earth_engine_fails(settings):
    source = FakeAreaSource(error=AreaSourceError("ee down"))

    result = run_tool(RunAreaRanking(make_ranker(settings, source)), RIAU_SQUARE)

    assert "area ranking unavailable" in str(result["error"])


def test_the_tool_returns_an_error_when_the_run_times_out(settings):
    gate = threading.Event()
    ranker = make_ranker(settings, FakeAreaSource(delay=gate), timeout_seconds=0.05)
    threading.Timer(0.3, gate.set).start()

    result = run_tool(RunAreaRanking(ranker), RIAU_SQUARE)

    assert "area ranking unavailable" in str(result["error"])


def test_one_agent_run_gets_at_most_two_area_runs(settings):
    source = FakeAreaSource()
    tool = RunAreaRanking(make_ranker(settings, source))
    context = FakeToolContext()

    first = run_tool(tool, square(102.0, 0.5, 0.05), context)
    second = run_tool(tool, square(102.1, 0.5, 0.05), context)
    third = run_tool(tool, square(102.2, 0.5, 0.05), context)

    assert first["status"] == "ranked"
    assert second["status"] == "ranked"
    assert f"at most {MAX_AREA_RUNS} area runs" in str(third["error"])
    assert len(source.calls) == MAX_AREA_RUNS


def test_a_new_agent_run_gets_a_new_area_budget(settings):
    tool = RunAreaRanking(make_ranker(settings))
    spent = FakeToolContext()
    for west in (102.0, 102.1, 102.2):
        run_tool(tool, square(west, 0.5, 0.05), spent)

    assert run_tool(tool, RIAU_SQUARE)["status"] == "ranked"
