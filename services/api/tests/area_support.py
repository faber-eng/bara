from datetime import UTC, datetime

from adapters.area_regions import AreaRegion, aoi_box
from casework.area_ranking import AreaRanker
from domain.area_cache import AreaRankingCache
from domain.area_rank import AreaMeasure, ScoredAreaCell
from ee_lib.config import load_region

NOW = datetime(2026, 10, 17, 4, 0, tzinfo=UTC)
RIAU_BOX = aoi_box([[101.95, 0.35], [102.55, 0.85]])


def square(west, south, side):
    east, north = west + side, south + side
    ring = [[west, south], [east, south], [east, north], [west, north], [west, south]]
    return {"type": "Polygon", "coordinates": [ring]}


RIAU_SQUARE = square(102.0, 0.5, 0.09)
FAR_SQUARE = square(10.0, 40.0, 0.09)


def scored(cell_id, score):
    return ScoredAreaCell(cell_id, 0.5, 102.0, score)


class FakeAreaSource:
    def __init__(self, measure=None, error=None, delay=None):
        self.measure = measure or AreaMeasure(
            3,
            [
                scored("riau-1-1", 40.0),
                scored("riau-1-2", 80.0),
                scored("riau-1-3", 60.0),
            ],
            "https://tiles.example/{z}/{x}/{y}",
        )
        self.error = error
        self.delay = delay
        self.calls = []

    def rank(self, region, polygon, week_start, today):
        self.calls.append((region.id, polygon.digest, week_start, today))
        if self.delay is not None:
            self.delay.wait()
        if self.error is not None:
            raise self.error
        return self.measure


class FakeAreaLimits:
    def __init__(self):
        self.states = {}

    def update(self, uid, apply):
        state, retry_after = apply(self.states.get(uid))
        if state is not None:
            self.states[uid] = state
        return retry_after


def make_ranker(settings, source=None, limits=None, clock=None, **options):
    region = load_region(settings.config_dir, "riau")
    clock = clock or (lambda: NOW)
    return AreaRanker(
        source=source or FakeAreaSource(),
        limits=limits or FakeAreaLimits(),
        regions=[AreaRegion(region, RIAU_BOX)],
        cache=AreaRankingCache(),
        utcnow=clock,
        **options,
    )
