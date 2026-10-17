from pathlib import Path

import pytest

from ee_lib.config import (
    ConfigError,
    UnknownRegion,
    load_data_config,
    load_region,
    read_aoi,
)

DATA_YAML = """
grid_cell_m: 1000
datasets:
  s1: S1
  chirps: CHIRPS
  peat: PEAT
  osm_lines: p.d.t
drying:
  wet_baseline_months: [1, 2, 3]
  s1_window_days: 12
  rain_window_days: 30
  clim_years: [2000, 2025]
  weights: {weights}
judge_mode: {{ enabled: true, max_resets_per_hour: 20 }}
"""

FULL_WEIGHTS = (
    "{ s1_anomaly: 0.45, rain_deficit: 0.30, canal_proximity: 0.15, peat_class: 0.10 }"
)


def write(directory: Path, name: str, text: str) -> Path:
    (directory / name).write_text(text)
    return directory


def test_reads_datasets_and_drying_from_the_repo_config(config_dir):
    data = load_data_config(config_dir)

    assert data.grid_cell_m == 1000
    assert data.datasets.s1 == "COPERNICUS/S1_GRD"
    assert data.datasets.chirps == "UCSB-CHG/CHIRPS/DAILY"
    assert (
        data.datasets.peat == "projects/sat-io/open-datasets/GLOBAL-PEATLAND-DATABASE"
    )
    assert data.datasets.osm_lines == (
        "bigquery-public-data.geo_openstreetmap.planet_features_lines"
    )
    assert data.drying.clim_years == (2000, 2025)
    assert data.drying.weights.s1_anomaly == 0.45
    assert data.drying.weights.peat_class == 0.10


def test_a_missing_weight_is_a_config_error(tmp_path):
    weights = "{ s1_anomaly: 0.45, rain_deficit: 0.30, canal_proximity: 0.15 }"
    write(tmp_path, "app.yaml", DATA_YAML.format(weights=weights))

    with pytest.raises(ConfigError, match="peat_class"):
        load_data_config(tmp_path)


def test_an_unknown_weight_is_a_config_error(tmp_path):
    weights = FULL_WEIGHTS.replace("peat_class", "peat_klass")
    write(tmp_path, "app.yaml", DATA_YAML.format(weights=weights))

    with pytest.raises(ConfigError):
        load_data_config(tmp_path)


def test_a_reversed_climatology_range_is_a_config_error(tmp_path):
    text = DATA_YAML.format(weights=FULL_WEIGHTS).replace(
        "[2000, 2025]", "[2025, 2000]"
    )
    write(tmp_path, "app.yaml", text)

    with pytest.raises(ConfigError, match="clim_years"):
        load_data_config(tmp_path)


def test_unreadable_yaml_is_a_config_error(tmp_path):
    write(tmp_path, "app.yaml", "drying: [unclosed")

    with pytest.raises(ConfigError):
        load_data_config(tmp_path)


def test_loads_the_riau_region(config_dir):
    region = load_region(config_dir, "riau")

    assert region.id == "riau"
    assert region.timezone == "Asia/Jakarta"
    assert region.s1_relative_orbit == 91
    assert region.s1_pass == "DESCENDING"
    assert region.grid_crs == "EPSG:32648"


def test_an_unknown_region_raises(config_dir):
    with pytest.raises(UnknownRegion, match="atlantis"):
        load_region(config_dir, "atlantis")


def test_a_region_without_drying_settings_raises_unknown_region(config_dir):
    with pytest.raises(UnknownRegion, match="congo_cuvette"):
        load_region(config_dir, "congo_cuvette")


def test_an_invalid_timezone_raises(tmp_path):
    write(
        tmp_path,
        "regions.yaml",
        """
riau:
  name: Riau
  aoi: data/aoi/riau_focus.geojson
  timezone: Mars/Olympus
  s1_relative_orbit: 91
  s1_pass: DESCENDING
  grid_crs: EPSG:32648
""",
    )

    with pytest.raises(UnknownRegion, match="timezone"):
        load_region(tmp_path, "riau")


def test_reads_the_riau_aoi_polygon(config_dir):
    region = load_region(config_dir, "riau")

    aoi = read_aoi(config_dir, region)

    assert aoi["type"] == "Polygon"
    assert aoi["coordinates"][0][0] == [101.95, 0.35]


def test_an_aoi_with_two_features_is_a_config_error(tmp_path, config_dir):
    (tmp_path / "config").mkdir()
    (tmp_path / "aoi.geojson").write_text(
        '{"type": "FeatureCollection", "features": [{}, {}]}'
    )
    region = load_region(config_dir, "riau").model_copy(update={"aoi": "aoi.geojson"})

    with pytest.raises(ConfigError, match="one feature"):
        read_aoi(tmp_path / "config", region)


def test_a_missing_aoi_file_is_a_config_error(tmp_path, config_dir):
    region = load_region(config_dir, "riau").model_copy(
        update={"aoi": "missing.geojson"}
    )

    with pytest.raises(ConfigError, match="missing.geojson"):
        read_aoi(tmp_path, region)
