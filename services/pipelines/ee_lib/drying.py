from datetime import date, timedelta

import ee

from ee_lib.config import DataConfig, RegionConfig
from ee_lib.grid import aoi_geometry
from ee_lib.weeks import DateRange, DryingWindow, same_day_in_year

S1_BAND = "VV"
RAIN_BAND = "precipitation"
SPECKLE_RADIUS_M = 30
CHIRPS_LOOKBACK_DAYS = 120
INPUT_BANDS = (
    "s1_recent_anom_db",
    "s1_previous_anom_db",
    "rain_30d_mm",
    "clim_rain_30d_mm",
)


def iso(day: date) -> str:
    return day.isoformat()


def smooth(image: ee.Image) -> ee.Image:
    return image.focalMedian(SPECKLE_RADIUS_M, "circle", "meters")


def s1_collection(
    data: DataConfig, region: RegionConfig, geometry: ee.Geometry
) -> ee.ImageCollection:
    return (
        ee.ImageCollection(data.datasets.s1)
        .filterBounds(geometry)
        .filter(ee.Filter.eq("instrumentMode", "IW"))
        .filter(ee.Filter.listContains("transmitterReceiverPolarisation", S1_BAND))
        .filter(ee.Filter.eq("orbitProperties_pass", region.s1_pass))
        .filter(ee.Filter.eq("relativeOrbitNumber_start", region.s1_relative_orbit))
        .select(S1_BAND)
    )


def smoothed_median(collection: ee.ImageCollection, span: DateRange) -> ee.Image:
    return collection.filterDate(iso(span.start), iso(span.end)).map(smooth).median()


def wet_baseline(
    collection: ee.ImageCollection, data: DataConfig, year: int
) -> ee.Image:
    months = [
        ee.Filter.calendarRange(month, month, "month")
        for month in data.drying.wet_baseline_months
    ]
    in_year = collection.filterDate(iso(date(year, 1, 1)), iso(date(year + 1, 1, 1)))
    return in_year.filter(ee.Filter.Or(*months)).map(smooth).median()


def rain_sum(data: DataConfig, span: DateRange) -> ee.Image:
    chirps = ee.ImageCollection(data.datasets.chirps).select(RAIN_BAND)
    return chirps.filterDate(iso(span.start), iso(span.end)).sum()


def shifted(span: DateRange, year: int) -> DateRange:
    offset = year - span.end.year
    return DateRange(
        same_day_in_year(span.start, span.start.year + offset),
        same_day_in_year(span.end, year),
    )


def clim_rain(data: DataConfig, span: DateRange) -> ee.Image:
    first, last = data.drying.clim_years
    sums = [rain_sum(data, shifted(span, year)) for year in range(first, last + 1)]
    return ee.ImageCollection.fromImages(sums).mean()


def chirps_last_millis(data: DataConfig, before: date) -> ee.Number:
    lookback = before - timedelta(days=CHIRPS_LOOKBACK_DAYS)
    recent = ee.ImageCollection(data.datasets.chirps).filterDate(
        iso(lookback), iso(before)
    )
    return recent.aggregate_max("system:time_start")


def inputs_image(
    data: DataConfig,
    region: RegionConfig,
    aoi: dict,
    week_start: date,
    window: DryingWindow,
) -> ee.Image:
    s1 = s1_collection(data, region, aoi_geometry(aoi))
    wet = wet_baseline(s1, data, week_start.year)
    return ee.Image.cat(
        smoothed_median(s1, window.s1_recent).subtract(wet),
        smoothed_median(s1, window.s1_previous).subtract(wet),
        rain_sum(data, window.rain),
        clim_rain(data, window.rain),
    ).rename(list(INPUT_BANDS))


def cells_collection(cells_table: str, region: RegionConfig) -> ee.FeatureCollection:
    cells = ee.FeatureCollection.loadBigQueryTable(
        table=cells_table, geometryColumn="geom"
    )
    return cells.filter(ee.Filter.eq("region", region.id)).select(["cell_id"])
