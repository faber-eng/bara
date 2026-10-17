from pathlib import Path

import yaml

from domain.area_polygon import BoundingBox
from ee_lib.config import (
    ConfigError,
    RegionConfig,
    UnknownRegion,
    load_region,
    read_aoi,
)


class AreaRegion:
    def __init__(self, region: RegionConfig, box: BoundingBox):
        self.region = region
        self.box = box


def aoi_box(ring: list[list[float]]) -> BoundingBox:
    lons = [position[0] for position in ring]
    lats = [position[1] for position in ring]
    return BoundingBox(min(lons), min(lats), max(lons), max(lats))


def region_ids(config_dir: Path) -> list[str]:
    document = yaml.safe_load((config_dir / "regions.yaml").read_text())
    if not isinstance(document, dict):
        raise ConfigError("regions.yaml must be a mapping")
    return list(document)


def load_area_regions(config_dir: Path) -> list[AreaRegion]:
    regions: list[AreaRegion] = []
    for region_id in region_ids(config_dir):
        try:
            region = load_region(config_dir, region_id)
        except UnknownRegion:
            continue
        ring = read_aoi(config_dir, region)["coordinates"][0]
        regions.append(AreaRegion(region, aoi_box(ring)))
    return regions
