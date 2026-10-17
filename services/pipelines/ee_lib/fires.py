from datetime import date, timedelta

import ee

from ee_lib.config import DataConfig
from ee_lib.grid import aoi_geometry

FIRMS_BANDS = ("T21", "confidence")
MIN_CONFIDENCE = 30
FIRMS_LOOKBACK_DAYS = 30


def iso(day: date) -> str:
    return day.isoformat()


def day_detections(image: ee.Image, region: ee.Geometry) -> ee.FeatureCollection:
    confident = image.select("confidence").gte(MIN_CONFIDENCE)
    points = (
        image.select(list(FIRMS_BANDS))
        .updateMask(confident)
        .sample(
            region=region,
            projection=image.projection(),
            geometries=True,
            dropNulls=True,
        )
    )
    day = image.date().format("YYYY-MM-dd")
    return points.map(lambda point: point.set("detect_date", day))


def detections(
    data: DataConfig, aoi: dict, buffer_m: int, start: date, end: date
) -> ee.FeatureCollection:
    region = aoi_geometry(aoi).buffer(buffer_m)
    days = (
        ee.ImageCollection(data.datasets.firms)
        .filterDate(iso(start), iso(end))
        .filterBounds(region)
    )
    return days.map(lambda image: day_detections(image, region)).flatten()


def firms_last_millis(data: DataConfig, before: date) -> ee.Number:
    lookback = before - timedelta(days=FIRMS_LOOKBACK_DAYS)
    recent = ee.ImageCollection(data.datasets.firms).filterDate(
        iso(lookback), iso(before)
    )
    return recent.aggregate_max("system:time_start")
