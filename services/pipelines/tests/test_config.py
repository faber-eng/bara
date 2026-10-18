from pathlib import Path

import pytest

from ee_lib.config import (
    ConfigError,
    UnknownRegion,
    load_data_config,
    load_region,
    load_region_ids,
    read_aoi,
)

DATA_YAML = """
grid_cell_m: 1000
datasets:
  s1: S1
  chirps: CHIRPS
  peat: PEAT
  osm_lines: p.d.t
  firms: FIRMS
  viirs_snpp: SNPP
  viirs_noaa20: NOAA20
  burned_area: BURNED
drying:
  wet_baseline_months: [1, 2, 3]
  s1_window_days: 12
  rain_window_days: 30
  clim_years: [2000, 2025]
  weights: {weights}
reignition:
  quiet_days: 3
  label_window_days: [3, 30]
  label_radius_m: 1000
  recheck_spots_per_fire: 3
  recheck_after_hours: 48
  history_from_year: 2001
  split_years: {{ train: [2015, 2024], valid: 2025, test: 2026 }}
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


def test_reads_the_fire_datasets_and_reignition_rules(config_dir):
    data = load_data_config(config_dir)

    assert data.datasets.firms == "FIRMS"
    assert data.datasets.viirs_snpp == "NASA/LANCE/SNPP_VIIRS/C2"
    assert data.datasets.viirs_noaa20 == "NASA/LANCE/NOAA20_VIIRS/C2"
    assert data.datasets.burned_area == "MODIS/061/MCD64A1"
    rules = data.reignition
    assert rules.quiet_days == 3
    assert rules.label_window_days == (3, 30)
    assert rules.label_radius_m == 1000
    assert rules.history_from_year == 2001
    assert rules.split_years.train == (2015, 2024)
    assert rules.split_years.valid == 2025
    assert rules.split_years.test == 2026


def test_a_valid_year_inside_the_train_years_is_a_config_error(tmp_path):
    text = DATA_YAML.format(weights=FULL_WEIGHTS).replace("valid: 2025", "valid: 2020")
    write(tmp_path, "app.yaml", text)

    with pytest.raises(ConfigError, match="split_years"):
        load_data_config(tmp_path)


def test_a_reversed_label_window_is_a_config_error(tmp_path):
    text = DATA_YAML.format(weights=FULL_WEIGHTS).replace("[3, 30]", "[30, 3]")
    write(tmp_path, "app.yaml", text)

    with pytest.raises(ConfigError, match="label_window_days"):
        load_data_config(tmp_path)


def test_a_label_radius_below_the_cell_size_is_a_config_error(tmp_path):
    text = DATA_YAML.format(weights=FULL_WEIGHTS).replace(
        "label_radius_m: 1000", "label_radius_m: 500"
    )
    write(tmp_path, "app.yaml", text)

    with pytest.raises(ConfigError, match="label_radius_m"):
        load_data_config(tmp_path)


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
    assert region.full_flow is True
    assert region.s1_relative_orbit == 91
    assert region.s1_pass == "DESCENDING"
    assert region.grid_crs == "EPSG:32648"


def test_lists_every_configured_region_in_file_order(config_dir):
    assert load_region_ids(config_dir) == ["riau", "congo_cuvette"]


def test_an_unknown_region_raises(config_dir):
    with pytest.raises(UnknownRegion, match="atlantis"):
        load_region(config_dir, "atlantis")


def test_the_congo_region_is_ranking_only_on_the_109_descending_orbit(config_dir):
    region = load_region(config_dir, "congo_cuvette")

    assert region.full_flow is False
    assert region.s1_relative_orbit == 109
    assert region.s1_pass == "DESCENDING"
    assert region.grid_crs == "EPSG:32633"
    assert region.timezone == "Africa/Brazzaville"


def test_a_region_without_drying_settings_raises_unknown_region(tmp_path):
    write(
        tmp_path,
        "regions.yaml",
        "nowhere:\n  name: Nowhere\n  aoi: a.geojson\n  timezone: UTC\n"
        "  full_flow: false\n",
    )

    with pytest.raises(UnknownRegion, match="nowhere"):
        load_region(tmp_path, "nowhere")


def test_the_congo_aoi_is_a_polygon_inside_the_cuvette(config_dir):
    region = load_region(config_dir, "congo_cuvette")

    aoi = read_aoi(config_dir, region)

    assert aoi["type"] == "Polygon"
    assert aoi["coordinates"][0][0] == [17.5, 0.0]


def test_an_invalid_timezone_raises(tmp_path):
    write(
        tmp_path,
        "regions.yaml",
        """
riau:
  name: Riau
  aoi: data/aoi/riau_focus.geojson
  timezone: Mars/Olympus
  full_flow: true
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
