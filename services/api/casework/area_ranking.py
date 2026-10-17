import asyncio
import logging
import threading
from collections.abc import Callable
from datetime import date, datetime
from typing import Protocol

from adapters.area_regions import AreaRegion
from contracts import AreaRanking, AreaRunState
from domain.area_cache import AreaRankingCache
from domain.area_limit import decide
from domain.area_polygon import AreaPolygon, parse_polygon
from domain.area_rank import AreaMeasure, to_area_cells
from ee_lib.config import RegionConfig
from ee_lib.weeks import local_today, resolve_week, week_label

logger = logging.getLogger(__name__)

TIMEOUT_SECONDS = 60.0
MAX_CONCURRENT_RUNS = 4


class AreaSource(Protocol):
    def rank(
        self,
        region: RegionConfig,
        polygon: AreaPolygon,
        week_start: date,
        today: date,
    ) -> AreaMeasure: ...


class AreaLimitStore(Protocol):
    def update(
        self,
        uid: str,
        apply: Callable[[AreaRunState | None], tuple[AreaRunState | None, int]],
    ) -> int: ...


class OutsideRegions(Exception):
    pass


class RateLimited(Exception):
    def __init__(self, retry_after: int):
        super().__init__(f"area ranking limit reached, retry in {retry_after} s")
        self.retry_after = retry_after


class AreaBusy(Exception):
    pass


class AreaTimeout(Exception):
    pass


class AreaRanker:
    def __init__(
        self,
        *,
        source: AreaSource,
        limits: AreaLimitStore,
        regions: list[AreaRegion],
        cache: AreaRankingCache,
        utcnow: Callable[[], datetime],
        timeout_seconds: float = TIMEOUT_SECONDS,
        max_concurrent: int = MAX_CONCURRENT_RUNS,
    ):
        self._source = source
        self._limits = limits
        self._regions = regions
        self._cache = cache
        self._utcnow = utcnow
        self._timeout = timeout_seconds
        self._slots = threading.BoundedSemaphore(max_concurrent)

    async def rank_within_deadline(self, uid: str, raw: object) -> AreaRanking:
        work = asyncio.to_thread(self.rank, uid, raw)
        try:
            return await asyncio.wait_for(work, self._timeout)
        except TimeoutError as error:
            logger.warning("area ranking timed out", extra={"fields": {"uid": uid}})
            raise AreaTimeout() from error

    def rank(self, uid: str, raw: object) -> AreaRanking:
        polygon = parse_polygon(raw)
        region = self._region_for(polygon)
        week_start = resolve_week(None, self._utcnow(), region.zone)
        key = f"{polygon.digest}:{week_label(week_start)}"
        cached = self._cache.get(key)
        if cached is not None:
            return cached.model_copy(update={"cached": True})
        self._admit(uid)
        ranking = self._measure(region, polygon, week_start)
        self._cache.put(key, ranking)
        return ranking

    def _region_for(self, polygon: AreaPolygon) -> RegionConfig:
        for candidate in self._regions:
            if candidate.box.overlaps(polygon.box):
                return candidate.region
        raise OutsideRegions()

    def _admit(self, uid: str) -> None:
        now = self._utcnow()
        retry_after = self._limits.update(uid, lambda state: decide(state, now))
        if retry_after > 0:
            raise RateLimited(retry_after)

    def _measure(
        self, region: RegionConfig, polygon: AreaPolygon, week_start: date
    ) -> AreaRanking:
        if not self._slots.acquire(blocking=False):
            raise AreaBusy()
        try:
            today = local_today(self._utcnow(), region.zone)
            measure = self._source.rank(region, polygon, week_start, today)
        finally:
            self._slots.release()
        return self._ranking(region, polygon, week_start, measure)

    def _ranking(
        self,
        region: RegionConfig,
        polygon: AreaPolygon,
        week_start: date,
        measure: AreaMeasure,
    ) -> AreaRanking:
        has_peat = measure.peat_cells > 0
        return AreaRanking(
            status="ranked" if has_peat else "no_peat",
            region=region.id,
            week=week_label(week_start),
            polygon_hash=polygon.digest,
            area_km2=polygon.area_km2,
            peat_cells=measure.peat_cells,
            cells=to_area_cells(measure.cells) if has_peat else [],
            tile_url_template=measure.tile_url_template if has_peat else None,
            cached=False,
        )
