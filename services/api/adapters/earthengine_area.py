import threading
import time
from collections.abc import Callable
from datetime import date
from pathlib import Path

import ee
from google.auth.exceptions import GoogleAuthError

from adapters.earthengine import CANALS_TABLE
from domain.area_polygon import AreaPolygon
from domain.area_rank import TOP_CELLS, AreaMeasure, ScoredAreaCell
from ee_lib import drying, grid, session
from ee_lib.config import RegionConfig, load_data_config
from ee_lib.grid import aoi_geometry
from ee_lib.weeks import DryingWindow, drying_window, window_end

MEAN = "mean"
CHIRPS_DAY_TTL_SECONDS = 3600.0


class AreaSourceError(Exception):
    pass


def grid_index_parts(grid_index: object) -> tuple[str, str]:
    if not isinstance(grid_index, str) or grid_index.count(",") != 1:
        raise AreaSourceError(f"grid index {grid_index!r} is not 'x,y'")
    x, y = grid_index.split(",")
    return x, y


def ring_center(geometry: dict) -> tuple[float, float]:
    ring = geometry["coordinates"][0][:-1]
    lon = sum(position[0] for position in ring) / len(ring)
    lat = sum(position[1] for position in ring) / len(ring)
    return lon, lat


def scored_cell(region: str, feature: dict) -> ScoredAreaCell:
    properties = feature["properties"]
    x, y = grid_index_parts(properties.get("grid_index"))
    lon, lat = ring_center(feature["geometry"])
    return ScoredAreaCell(f"{region}-{x}-{y}", lat, lon, float(properties[MEAN]))


class EarthEngineAreaSource:
    def __init__(
        self,
        project: str,
        config_dir: Path,
        clock: Callable[[], float] = time.monotonic,
    ):
        self._project = project
        self._data = load_data_config(config_dir)
        self._clock = clock
        self._lock = threading.Lock()
        self._initialized = False
        self._chirps_day: tuple[float, date] | None = None

    def rank(
        self,
        region: RegionConfig,
        polygon: AreaPolygon,
        week_start: date,
        today: date,
    ) -> AreaMeasure:
        try:
            self._initialize()
            return self._measure(region, polygon, week_start, today)
        except (ee.EEException, GoogleAuthError, OSError) as error:
            raise AreaSourceError(str(error)) from error

    def _measure(
        self,
        region: RegionConfig,
        polygon: AreaPolygon,
        week_start: date,
        today: date,
    ) -> AreaMeasure:
        window = self._window(week_start, today)
        aoi = polygon.geometry
        score = drying.score_image(
            self._data,
            region,
            aoi,
            week_start,
            window,
            f"{self._project}.{CANALS_TABLE}",
        )
        cells = self._peat_cells(region, aoi)
        scored = score.reduceRegions(
            collection=cells,
            reducer=ee.Reducer.mean(),
            scale=drying.MEASURE_SCALE_M,
            tileScale=drying.MEASURE_TILE_SCALE,
        ).filter(ee.Filter.notNull([MEAN]))
        top = scored.sort(MEAN, False).limit(TOP_CELLS)
        summary = ee.Dictionary(
            {"peat_cells": cells.size(), "top": top.toList(TOP_CELLS)}
        ).getInfo()
        return AreaMeasure(
            peat_cells=int(summary["peat_cells"]),
            cells=[scored_cell(region.id, feature) for feature in summary["top"]],
            tile_url_template=self._tile_url(score, summary["peat_cells"]),
        )

    def _peat_cells(self, region: RegionConfig, aoi: dict) -> ee.FeatureCollection:
        return grid.peat_cells(aoi, region, self._data).filterBounds(aoi_geometry(aoi))

    def _tile_url(self, score: ee.Image, peat_cells: int) -> str | None:
        if peat_cells == 0:
            return None
        return score.getMapId(drying.DRYING_VIS)["tile_fetcher"].url_format

    def _window(self, week_start: date, today: date) -> DryingWindow:
        before = window_end(week_start, today)
        chirps_last = self._latest_chirps_day(before)
        return drying_window(
            week_start,
            today=today,
            chirps_last=chirps_last,
            s1_days=self._data.drying.s1_window_days,
            rain_days=self._data.drying.rain_window_days,
        )

    def _latest_chirps_day(self, before: date) -> date:
        now = self._clock()
        cached = self._chirps_day
        if cached is not None and cached[0] > now:
            return cached[1]
        day = session.latest_chirps_day(self._data, before)
        if day is None:
            raise AreaSourceError(f"no CHIRPS day before {before}")
        self._chirps_day = (now + CHIRPS_DAY_TTL_SECONDS, day)
        return day

    def _initialize(self) -> None:
        with self._lock:
            if self._initialized:
                return
            session.initialize(self._project)
            self._initialized = True
