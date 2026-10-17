import ee

from ee_lib.config import DataConfig, RegionConfig
from ee_lib.peat import PEAT_CLASSES

PEAT_BAND = "b1"
LONLAT = "EPSG:4326"
TRANSFORM_MAX_ERROR_M = 1


def aoi_geometry(aoi: dict) -> ee.Geometry:
    return ee.Geometry(aoi, None, False)


def to_cell_feature(feature: ee.Feature) -> ee.Feature:
    return ee.Feature(
        feature.geometry().transform(LONLAT, TRANSFORM_MAX_ERROR_M),
        {"grid_index": feature.get("system:index"), "peat_mode": feature.get("mode")},
    )


def peat_cells(
    aoi: dict, region: RegionConfig, data: DataConfig
) -> ee.FeatureCollection:
    grid = aoi_geometry(aoi).coveringGrid(
        ee.Projection(region.grid_crs), data.grid_cell_m
    )
    peat = ee.Image(data.datasets.peat).select(PEAT_BAND)
    modes = peat.reduceRegions(
        collection=grid, reducer=ee.Reducer.mode(), scale=data.grid_cell_m
    )
    return modes.filter(ee.Filter.inList("mode", list(PEAT_CLASSES))).map(
        to_cell_feature
    )
