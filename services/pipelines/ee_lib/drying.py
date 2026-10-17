from datetime import date, timedelta

import ee

from ee_lib.canals import CANAL_DECAY_M, CANAL_SEARCH_M
from ee_lib.config import DataConfig, RegionConfig
from ee_lib.grid import PEAT_BAND, aoi_geometry
from ee_lib.peat import PEAT_WEIGHTS
from ee_lib.weeks import DateRange, DryingWindow, same_day_in_year

S1_BAND = "VV"
RAIN_BAND = "precipitation"
SPECKLE_RADIUS_M = 30
CHIRPS_LOOKBACK_DAYS = 120
RISK_PALETTE = ("fceace", "f6cf9f", "e9a066", "c4612a", "8a3a12")
DRYING_VIS = {"min": 0, "max": 100, "palette": list(RISK_PALETTE)}
STATS_TILE_SCALE = 4
STATS_MAX_PIXELS = 1_000_000_000
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


def masked_band() -> ee.ImageCollection:
    empty = ee.Image(0).selfMask().rename(S1_BAND).toFloat()
    return ee.ImageCollection([empty])


def smoothed_median(collection: ee.ImageCollection, span: DateRange) -> ee.Image:
    passes = collection.filterDate(iso(span.start), iso(span.end)).map(smooth)
    return passes.merge(masked_band()).median()


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


def rain_deficit_image(rain: ee.Image, clim: ee.Image) -> ee.Image:
    ratio_deficit = ee.Image(1).subtract(rain.divide(clim)).unmask(0)
    dry_climatology = rain.gt(0).multiply(-1)
    return ratio_deficit.where(clim.eq(0), dry_climatology).clamp(-1, 1)


def canal_proximity_image(canals_table: str, region: RegionConfig) -> ee.Image:
    canals = ee.FeatureCollection.loadBigQueryTable(
        table=canals_table, geometryColumn="geometry"
    ).filter(ee.Filter.eq("region", region.id))
    distance = canals.distance(CANAL_SEARCH_M).unmask(CANAL_SEARCH_M)
    return distance.divide(-CANAL_DECAY_M).exp()


def peat_weight_image(data: DataConfig) -> ee.Image:
    peat = ee.Image(data.datasets.peat).select(PEAT_BAND)
    return peat.remap(list(PEAT_WEIGHTS), list(PEAT_WEIGHTS.values()))


def zscore(image: ee.Image, stats: ee.Dictionary, band: str) -> ee.Image:
    mean = ee.Number(stats.get(f"{band}_mean"))
    spread = ee.Number(stats.get(f"{band}_stdDev"))
    standardized = image.select(band).subtract(mean).divide(spread)
    flat = ee.Image.constant(0)
    return ee.Image(ee.Algorithms.If(spread.gt(0), standardized, flat)).unmask(0)


def component_image(
    data: DataConfig,
    region: RegionConfig,
    aoi: dict,
    week_start: date,
    window: DryingWindow,
    canals_table: str,
) -> ee.Image:
    inputs = inputs_image(data, region, aoi, week_start, window)
    s1 = inputs.select("s1_recent_anom_db").unmask(inputs.select("s1_previous_anom_db"))
    rain = inputs.select("rain_30d_mm")
    clim = inputs.select("clim_rain_30d_mm")
    peat_weight = peat_weight_image(data)
    return (
        ee.Image.cat(
            s1,
            rain_deficit_image(rain, clim),
            canal_proximity_image(canals_table, region),
            peat_weight,
        )
        .rename(["s1", "rain_deficit", "canal_proximity", "peat_weight"])
        .updateMask(peat_weight.mask())
    )


def score_image(
    data: DataConfig,
    region: RegionConfig,
    aoi: dict,
    week_start: date,
    window: DryingWindow,
    canals_table: str,
) -> ee.Image:
    geometry = aoi_geometry(aoi)
    components = component_image(data, region, aoi, week_start, window, canals_table)
    stats = components.reduceRegion(
        reducer=ee.Reducer.mean().combine(ee.Reducer.stdDev(), sharedInputs=True),
        geometry=geometry,
        scale=data.grid_cell_m,
        bestEffort=True,
        maxPixels=STATS_MAX_PIXELS,
        tileScale=STATS_TILE_SCALE,
    )
    weights = data.drying.weights
    total = (
        zscore(components, stats, "s1")
        .multiply(-weights.s1_anomaly)
        .add(zscore(components, stats, "rain_deficit").multiply(weights.rain_deficit))
        .add(
            zscore(components, stats, "canal_proximity").multiply(
                weights.canal_proximity
            )
        )
        .add(zscore(components, stats, "peat_weight").multiply(weights.peat_class))
    )
    score = total.multiply(-1).exp().add(1).pow(-1).multiply(100)
    return (
        score.rename("drying_score")
        .updateMask(components.select("peat_weight").mask())
        .clip(geometry)
    )
