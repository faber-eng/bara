from datetime import date

import ee

from ee_lib import drying, grid, session
from ee_lib.config import DataConfig, RegionConfig
from ee_lib.weeks import DryingWindow

PAGE_SIZE = 1000
MEASURE_SCALE_M = 100
MEASURE_TILE_SCALE = 4


class EarthEngineError(Exception):
    pass


def compute_features(collection: ee.FeatureCollection) -> list[dict]:
    features: list[dict] = []
    token: str | None = None
    while True:
        params: dict[str, object] = {"expression": collection, "pageSize": PAGE_SIZE}
        if token is not None:
            params["pageToken"] = token
        page = ee.data.computeFeatures(params)
        features.extend(page.get("features", []))
        token = page.get("nextPageToken")
        if not token:
            return features


class EarthEngineSource:
    def __init__(self, data: DataConfig):
        self._data = data

    def peat_cells(self, region: RegionConfig, aoi: dict) -> list[dict]:
        return compute_features(grid.peat_cells(aoi, region, self._data))

    def chirps_last_day(self, before: date) -> date:
        last = session.latest_chirps_day(self._data, before)
        if last is None:
            raise EarthEngineError(
                f"no CHIRPS day in the {drying.CHIRPS_LOOKBACK_DAYS} days before {before}"
            )
        return last

    def drying_inputs(
        self,
        region: RegionConfig,
        aoi: dict,
        cells_table: str,
        week_start: date,
        window: DryingWindow,
    ) -> list[dict]:
        image = drying.inputs_image(self._data, region, aoi, week_start, window)
        measured = image.reduceRegions(
            collection=drying.cells_collection(cells_table, region),
            reducer=ee.Reducer.mean(),
            scale=MEASURE_SCALE_M,
            tileScale=MEASURE_TILE_SCALE,
        )
        return [feature["properties"] for feature in compute_features(measured)]
