from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

import ee

from ee_lib.config import DataConfig
from ee_lib.drying import RISK_PALETTE, iso
from ee_lib.grid import PEAT_BAND, aoi_geometry

BURN_BAND = "BurnDate"
PEAT_PALETTE = ("8fb996", "2f5d3a")
BURN_PALETTE = ("4a2c1a",)
PEAT_VIS = {"min": 1, "max": 2, "palette": list(PEAT_PALETTE)}
BURN_VIS = {"min": 0, "max": 1, "palette": list(BURN_PALETTE)}
REIGNITION_VIS = {"min": 0, "max": 1, "palette": list(RISK_PALETTE)}
P_REIGNITE = "p_reignite"


@dataclass(frozen=True)
class ScoredCell:
    cell_id: str
    p_reignite: float
    geometry: dict


def peat_image(data: DataConfig, aoi: dict) -> ee.Image:
    peat = ee.Image(data.datasets.peat).select(PEAT_BAND)
    return peat.updateMask(peat.gt(0)).clip(aoi_geometry(aoi))


def burn_scars_image(data: DataConfig, aoi: dict, week_end: date) -> ee.Image:
    first_day = date(week_end.year, 1, 1)
    burned = (
        ee.ImageCollection(data.datasets.burned_area)
        .filterDate(iso(first_day), iso(week_end))
        .select(BURN_BAND)
        .max()
    )
    return burned.gt(0).selfMask().clip(aoi_geometry(aoi))


def reignition_image(cells: Sequence[ScoredCell]) -> ee.Image:
    features = [
        ee.Feature(
            ee.Geometry(cell.geometry, None, False), {P_REIGNITE: cell.p_reignite}
        )
        for cell in cells
    ]
    return ee.FeatureCollection(features).reduceToImage([P_REIGNITE], ee.Reducer.max())
