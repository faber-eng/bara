import json
from pathlib import Path
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import yaml
from pydantic import (
    BaseModel,
    ConfigDict,
    PositiveInt,
    ValidationError,
    field_validator,
    model_validator,
)


class ConfigError(Exception):
    pass


class UnknownRegion(Exception):
    pass


class Config(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Datasets(Config):
    s1: str
    chirps: str
    peat: str
    osm_lines: str
    firms: str
    viirs_snpp: str
    viirs_noaa20: str
    burned_area: str


class DryingWeights(Config):
    s1_anomaly: float
    rain_deficit: float
    canal_proximity: float
    peat_class: float


class DryingConfig(Config):
    wet_baseline_months: tuple[int, ...]
    s1_window_days: PositiveInt
    rain_window_days: PositiveInt
    clim_years: tuple[int, int]
    weights: DryingWeights

    @model_validator(mode="after")
    def check_ranges(self) -> "DryingConfig":
        if self.clim_years[0] > self.clim_years[1]:
            raise ValueError("clim_years must be [first, last] with first <= last")
        if not all(1 <= month <= 12 for month in self.wet_baseline_months):
            raise ValueError("wet_baseline_months must be months 1 to 12")
        return self


class SplitYears(Config):
    train: tuple[int, int]
    valid: int
    test: int

    @model_validator(mode="after")
    def check_order(self) -> "SplitYears":
        if not self.train[0] <= self.train[1] < self.valid < self.test:
            raise ValueError("split_years must be train [first, last] < valid < test")
        return self


class ReignitionConfig(Config):
    model_config = ConfigDict(extra="ignore", frozen=True)

    quiet_days: PositiveInt
    label_window_days: tuple[PositiveInt, PositiveInt]
    label_radius_m: PositiveInt
    recheck_spots_per_fire: PositiveInt
    history_from_year: int
    split_years: SplitYears

    @model_validator(mode="after")
    def check_window(self) -> "ReignitionConfig":
        if self.label_window_days[0] > self.label_window_days[1]:
            raise ValueError("label_window_days must be [first, last]")
        if self.history_from_year > self.split_years.train[0]:
            raise ValueError("history_from_year must not be after the first train year")
        return self


class DataConfig(Config):
    model_config = ConfigDict(extra="ignore", frozen=True)

    grid_cell_m: PositiveInt
    datasets: Datasets
    drying: DryingConfig
    reignition: ReignitionConfig

    @model_validator(mode="after")
    def check_label_radius(self) -> "DataConfig":
        if self.reignition.label_radius_m < self.grid_cell_m:
            raise ValueError("reignition.label_radius_m must be at least grid_cell_m")
        return self


class RegionConfig(Config):
    model_config = ConfigDict(extra="ignore", frozen=True)

    id: str
    name: str
    aoi: str
    timezone: str
    full_flow: bool
    s1_relative_orbit: PositiveInt
    s1_pass: Literal["ASCENDING", "DESCENDING"]
    grid_crs: str

    @field_validator("timezone")
    @classmethod
    def known_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as error:
            raise ValueError(f"unknown timezone {value!r}") from error
        return value

    @property
    def zone(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)


def read_yaml(path: Path) -> object:
    try:
        return yaml.safe_load(path.read_text())
    except OSError as error:
        raise ConfigError(f"cannot read {path}: {error}") from error
    except yaml.YAMLError as error:
        raise ConfigError(f"{path} is not valid YAML: {error}") from error


def load_data_config(config_dir: Path) -> DataConfig:
    path = config_dir / "app.yaml"
    try:
        return DataConfig.model_validate(read_yaml(path))
    except ValidationError as error:
        raise ConfigError(f"{path} does not match the data config: {error}") from error


def load_region(config_dir: Path, region_id: str) -> RegionConfig:
    path = config_dir / "regions.yaml"
    regions = read_yaml(path)
    if not isinstance(regions, dict) or region_id not in regions:
        raise UnknownRegion(f"region {region_id!r} is not in {path}")
    entry = regions[region_id]
    if not isinstance(entry, dict):
        raise ConfigError(f"region {region_id!r} in {path} is not a mapping")
    try:
        return RegionConfig.model_validate({**entry, "id": region_id})
    except ValidationError as error:
        fields = ", ".join(str(issue["loc"][0]) for issue in error.errors())
        raise UnknownRegion(
            f"region {region_id!r} in {path} has no valid drying settings: {fields}"
        ) from error


def read_aoi(config_dir: Path, region: RegionConfig) -> dict:
    path = config_dir.parent / region.aoi
    try:
        document = json.loads(path.read_text())
    except OSError as error:
        raise ConfigError(f"cannot read the AOI {path}: {error}") from error
    except json.JSONDecodeError as error:
        raise ConfigError(f"the AOI {path} is not valid JSON: {error}") from error
    features = document.get("features") if isinstance(document, dict) else None
    if not isinstance(features, list) or len(features) != 1:
        raise ConfigError(
            f"the AOI {path} must be a FeatureCollection with one feature"
        )
    geometry = features[0].get("geometry")
    if not isinstance(geometry, dict) or geometry.get("type") != "Polygon":
        raise ConfigError(f"the AOI {path} feature must be a Polygon")
    return geometry
