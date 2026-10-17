import asyncio
import threading
from datetime import timedelta

import pytest

from casework.area_ranking import (
    AreaBusy,
    AreaTimeout,
    OutsideRegions,
    RateLimited,
)
from domain.area_polygon import InvalidPolygon, PolygonTooLarge
from domain.area_rank import AreaMeasure
from tests.area_support import (
    FAR_SQUARE,
    NOW,
    RIAU_SQUARE,
    FakeAreaLimits,
    FakeAreaSource,
    make_ranker,
    square,
)


def test_ranks_the_driest_cell_first_with_the_week_and_a_tile_url(settings):
    ranker = make_ranker(settings)

    ranking = ranker.rank("u1", RIAU_SQUARE)

    assert ranking.status == "ranked"
    assert ranking.region == "riau"
    assert ranking.week == "2026-W42"
    assert [cell.cell_id for cell in ranking.cells] == [
        "riau-1-2",
        "riau-1-3",
        "riau-1-1",
    ]
    assert [cell.rank for cell in ranking.cells] == [1, 2, 3]
    assert ranking.tile_url_template == "https://tiles.example/{z}/{x}/{y}"
    assert ranking.cached is False
    assert ranking.area_km2 == pytest.approx(100, rel=0.03)


def test_no_mapped_peat_returns_a_no_peat_result_without_cells_or_tiles(settings):
    source = FakeAreaSource(AreaMeasure(0, [], None))
    ranker = make_ranker(settings, source)

    ranking = ranker.rank("u1", RIAU_SQUARE)

    assert ranking.status == "no_peat"
    assert ranking.cells == []
    assert ranking.tile_url_template is None
    assert ranking.peat_cells == 0


def test_the_same_polygon_is_served_from_cache_and_spends_no_run(settings):
    source = FakeAreaSource()
    limits = FakeAreaLimits()
    ranker = make_ranker(settings, source, limits)

    ranker.rank("u1", RIAU_SQUARE)
    again = ranker.rank("u1", RIAU_SQUARE)

    assert again.cached is True
    assert len(source.calls) == 1
    assert len(limits.states["u1"].runs) == 1


def test_a_cache_hit_by_another_user_spends_no_run(settings):
    limits = FakeAreaLimits()
    ranker = make_ranker(settings, limits=limits)

    ranker.rank("u1", RIAU_SQUARE)
    ranker.rank("u2", RIAU_SQUARE)

    assert "u2" not in limits.states


def test_a_new_week_does_not_reuse_the_cache(settings):
    source = FakeAreaSource()
    now = [NOW]
    ranker = make_ranker(settings, source, clock=lambda: now[0])

    ranker.rank("u1", RIAU_SQUARE)
    now[0] = NOW + timedelta(days=7)
    ranker.rank("u1", RIAU_SQUARE)

    assert len(source.calls) == 2


def test_the_eleventh_run_in_an_hour_is_refused_with_a_retry_time(settings):
    ranker = make_ranker(settings)
    for step in range(10):
        ranker.rank("u1", square(102.0 + step * 0.01, 0.5, 0.05))

    with pytest.raises(RateLimited) as caught:
        ranker.rank("u1", square(102.2, 0.5, 0.05))

    assert 0 < caught.value.retry_after <= 3600


def test_the_limit_is_per_user(settings):
    ranker = make_ranker(settings)
    for step in range(10):
        ranker.rank("u1", square(102.0 + step * 0.01, 0.5, 0.05))

    assert ranker.rank("u2", square(102.2, 0.5, 0.05)).status == "ranked"


def test_a_run_frees_after_an_hour(settings):
    now = [NOW]
    ranker = make_ranker(settings, clock=lambda: now[0])
    for step in range(10):
        ranker.rank("u1", square(102.0 + step * 0.01, 0.5, 0.05))
    now[0] = NOW + timedelta(hours=1, seconds=1)

    assert ranker.rank("u1", square(102.2, 0.5, 0.05)).status == "ranked"


def test_a_polygon_outside_every_region_is_refused(settings):
    with pytest.raises(OutsideRegions):
        make_ranker(settings).rank("u1", FAR_SQUARE)


def test_a_bad_or_oversize_polygon_is_refused_before_a_run_is_spent(settings):
    limits = FakeAreaLimits()
    ranker = make_ranker(settings, limits=limits)

    with pytest.raises(InvalidPolygon):
        ranker.rank("u1", {"type": "Point"})
    with pytest.raises(PolygonTooLarge):
        ranker.rank("u1", square(102.0, 0.0, 0.6))

    assert limits.states == {}


def test_a_source_failure_propagates_and_is_not_cached(settings):
    source = FakeAreaSource(error=RuntimeError("ee down"))
    ranker = make_ranker(settings, source)

    with pytest.raises(RuntimeError):
        ranker.rank("u1", RIAU_SQUARE)
    source.error = None

    assert ranker.rank("u1", RIAU_SQUARE).cached is False


def test_too_many_runs_at_once_are_refused_as_busy(settings):
    gate = threading.Event()
    source = FakeAreaSource(delay=gate)
    ranker = make_ranker(settings, source, max_concurrent=1)
    holder = threading.Thread(target=ranker.rank, args=("u1", RIAU_SQUARE))
    holder.start()
    while not source.calls:
        pass

    with pytest.raises(AreaBusy):
        ranker.rank("u2", square(102.2, 0.5, 0.05))

    gate.set()
    holder.join()


def test_a_run_over_the_deadline_times_out(settings):
    gate = threading.Event()
    ranker = make_ranker(settings, FakeAreaSource(delay=gate), timeout_seconds=0.05)
    threading.Timer(0.3, gate.set).start()

    with pytest.raises(AreaTimeout):
        asyncio.run(ranker.rank_within_deadline("u1", RIAU_SQUARE))


def test_a_busy_refusal_spends_no_run(settings):
    gate = threading.Event()
    source = FakeAreaSource(delay=gate)
    limits = FakeAreaLimits()
    ranker = make_ranker(settings, source, limits, max_concurrent=1)
    holder = threading.Thread(target=ranker.rank, args=("u1", RIAU_SQUARE))
    holder.start()
    while not source.calls:
        pass

    with pytest.raises(AreaBusy):
        ranker.rank("u2", square(102.2, 0.5, 0.05))

    gate.set()
    holder.join()
    assert "u2" not in limits.states
