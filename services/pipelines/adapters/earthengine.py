from datetime import UTC, date, datetime

import ee

from ee_lib import drying, fires, grid, reignition, session
from ee_lib.config import DataConfig, RegionConfig
from ee_lib.weeks import DryingWindow, EventWindows

PAGE_SIZE = 1000
MEASURE_SCALE_M = 100
MEASURE_TILE_SCALE = 4
DATES_PER_CALL = 10


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

    def firms_last_day(self, before: date) -> date:
        millis = fires.firms_last_millis(self._data, before).getInfo()
        if millis is None:
            raise EarthEngineError(
                f"no FIRMS day in the {fires.FIRMS_LOOKBACK_DAYS} days before {before}"
            )
        return datetime.fromtimestamp(millis / 1000, UTC).date()

    def fire_detections(
        self, aoi: dict, buffer_m: int, start: date, end: date
    ) -> list[dict]:
        return compute_features(fires.detections(self._data, aoi, buffer_m, start, end))

    def reignition_measures(
        self,
        region: RegionConfig,
        aoi: dict,
        cells_table: str,
        dates: list[tuple[date, list[str], EventWindows]],
    ) -> list[dict]:
        cells = drying.cells_collection(cells_table, region)
        measures: list[dict] = []
        for start in range(0, len(dates), DATES_PER_CALL):
            chunk = [
                reignition.date_measures(
                    self._data, region, aoi, cells, quiet_date, cell_ids, windows
                )
                for quiet_date, cell_ids, windows in dates[
                    start : start + DATES_PER_CALL
                ]
            ]
            features = compute_features(ee.FeatureCollection(chunk).flatten())
            measures.extend(feature["properties"] for feature in features)
        return measures

    def peat_fractions(self, region: RegionConfig, cells_table: str) -> list[dict]:
        cells = drying.cells_collection(cells_table, region)
        features = compute_features(reignition.peat_fractions(self._data, cells))
        return [feature["properties"] for feature in features]
