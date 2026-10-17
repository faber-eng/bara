from datetime import date
from pathlib import Path
from typing import Protocol

import ee
from google.auth.exceptions import GoogleAuthError

from ee_lib import drying, session
from ee_lib.config import RegionConfig, load_data_config, read_aoi
from ee_lib.weeks import drying_window, window_end

CANALS_TABLE = "bara.osm_canals"


class TileSourceError(Exception):
    pass


class DryingTileSource(Protocol):
    def drying_url_template(
        self, region: RegionConfig, week_start: date, today: date
    ) -> str: ...


class EarthEngineTiles:
    def __init__(self, project: str, config_dir: Path):
        self._project = project
        self._config_dir = config_dir
        self._data = load_data_config(config_dir)
        self._initialized = False

    def drying_url_template(
        self, region: RegionConfig, week_start: date, today: date
    ) -> str:
        aoi = read_aoi(self._config_dir, region)
        try:
            return self._map_url(region, aoi, week_start, today)
        except (ee.EEException, GoogleAuthError, OSError) as error:
            raise TileSourceError(str(error)) from error

    def _map_url(
        self, region: RegionConfig, aoi: dict, week_start: date, today: date
    ) -> str:
        self._initialize()
        before = window_end(week_start, today)
        chirps_last = session.latest_chirps_day(self._data, before)
        if chirps_last is None:
            raise TileSourceError(f"no CHIRPS day before {before}")
        window = drying_window(
            week_start,
            today=today,
            chirps_last=chirps_last,
            s1_days=self._data.drying.s1_window_days,
            rain_days=self._data.drying.rain_window_days,
        )
        image = drying.score_image(
            self._data,
            region,
            aoi,
            week_start,
            window,
            f"{self._project}.{CANALS_TABLE}",
        )
        return image.getMapId(drying.DRYING_VIS)["tile_fetcher"].url_format

    def _initialize(self) -> None:
        if self._initialized:
            return
        session.initialize(self._project)
        self._initialized = True
