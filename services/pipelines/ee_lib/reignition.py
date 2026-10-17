from datetime import date

import ee

from ee_lib import drying
from ee_lib.config import DataConfig, RegionConfig
from ee_lib.grid import PEAT_BAND, aoi_geometry
from ee_lib.peat import PEAT_CLASSES
from ee_lib.weeks import DateRange, EventWindows


def rain_band(data: DataConfig, span: DateRange | None, name: str) -> ee.Image:
    if span is None:
        return drying.masked_image(name)
    return drying.rain_sum(data, span).rename(name).toFloat()


def s1_anomaly(
    data: DataConfig, region: RegionConfig, aoi: dict, windows: EventWindows
) -> ee.Image:
    s1 = drying.s1_collection(data, region, aoi_geometry(aoi))
    wet = drying.wet_baseline(s1, data, windows.s1_baseline_year)
    return drying.smoothed_median(s1, windows.s1).subtract(wet).rename("s1_anom_db")


def event_image(
    data: DataConfig,
    region: RegionConfig,
    aoi: dict,
    quiet_date: date,
    windows: EventWindows,
) -> ee.Image:
    return ee.Image.cat(
        s1_anomaly(data, region, aoi, windows).toFloat(),
        rain_band(data, windows.rain_7d_before, "rain_7d_before_mm"),
        rain_band(data, windows.rain_14d_before, "rain_14d_before_mm"),
        rain_band(data, windows.rain_7d_after, "rain_7d_after_mm"),
    )


def date_measures(
    data: DataConfig,
    region: RegionConfig,
    aoi: dict,
    cells: ee.FeatureCollection,
    quiet_date: date,
    cell_ids: list[str],
    windows: EventWindows,
) -> ee.FeatureCollection:
    image = event_image(data, region, aoi, quiet_date, windows)
    measured = image.reduceRegions(
        collection=cells.filter(ee.Filter.inList("cell_id", cell_ids)),
        reducer=ee.Reducer.mean(),
        scale=drying.MEASURE_SCALE_M,
        tileScale=drying.MEASURE_TILE_SCALE,
    )
    day = quiet_date.isoformat()
    return measured.map(lambda cell: cell.set("quiet_date", day).setGeometry(None))


def peat_fractions(
    data: DataConfig, cells: ee.FeatureCollection
) -> ee.FeatureCollection:
    peat = ee.Image(data.datasets.peat).select(PEAT_BAND)
    is_peat = peat.remap(list(PEAT_CLASSES), [1] * len(PEAT_CLASSES), 0).unmask(0)
    measured = is_peat.reduceRegions(
        collection=cells,
        reducer=ee.Reducer.mean().setOutputs(["peat_fraction"]),
        scale=drying.MEASURE_SCALE_M,
        tileScale=drying.MEASURE_TILE_SCALE,
    )
    return measured.map(lambda cell: cell.setGeometry(None))
