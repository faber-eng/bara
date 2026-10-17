import json

import pytest

from adapters.bigquery import MAX_BYTES_BILLED, Warehouse
from adapters.tables import CANAL_MAX_BYTES_BILLED
from ee_lib.config import load_region, read_aoi
from jobs import build_grid as job
from jobs.cli import JobError
from tests.fakes import FakeEarth, RecordingBigQueryClient

OSM_LINES = "bigquery-public-data.geo_openstreetmap.planet_features_lines"
SQUARE = {
    "type": "Polygon",
    "coordinates": [[[102.0, 0.4], [102.01, 0.4], [102.01, 0.41], [102.0, 0.4]]],
}


def feature(grid_index, mode):
    return {
        "type": "Feature",
        "geometry": SQUARE,
        "properties": {"grid_index": grid_index, "peat_mode": mode},
    }


PEAT_FEATURES = [feature("160,38", 1), feature("161,38", 2), feature("162,38", 0)]


def run(config_dir, *, existing=(), dry_run=False, features=PEAT_FEATURES):
    client = RecordingBigQueryClient(existing=existing)
    region = load_region(config_dir, "riau")
    summary = job.build_grid(
        region=region,
        aoi=read_aoi(config_dir, region),
        earth=FakeEarth(peat_features=features),
        warehouse=Warehouse(client, project="p", dataset="bara"),
        osm_lines=OSM_LINES,
        dry_run=dry_run,
    )
    return summary, client


def test_creates_the_canal_table_once_when_it_is_missing(config_dir):
    _, client = run(config_dir)

    canal_queries = [q for q in client.queries if "CREATE TABLE osm_canals" in q[0]]
    assert len(canal_queries) == 1
    sql, config = canal_queries[0]
    assert f"`{OSM_LINES}`" in sql
    assert "'canal', 'ditch', 'drain'" in sql
    assert config.maximum_bytes_billed == CANAL_MAX_BYTES_BILLED == 110_000_000_000
    params = {p.name: p.value for p in config.query_parameters}
    assert params["region"] == "riau"
    assert params["buffer_m"] == 5000
    assert json.loads(params["aoi"])["type"] == "Polygon"


def test_skips_the_canal_query_when_the_table_exists(config_dir):
    _, client = run(config_dir, existing=["osm_canals"])

    assert not any("CREATE TABLE osm_canals" in sql for sql in client.sql_sent())


def test_stages_only_peat_cells_with_their_geometry(config_dir):
    _, client = run(config_dir, existing=["osm_canals"])

    table_id, rows, config = client.loads[0]
    assert table_id == "p.bara.cells_staging"
    assert config.write_disposition == "WRITE_TRUNCATE"
    assert [(r["cell_id"], r["region"], r["peat_class"]) for r in rows] == [
        ("riau-160-38", "riau", 1),
        ("riau-161-38", "riau", 2),
    ]
    assert json.loads(rows[0]["geom"]) == SQUARE


def test_rewrites_the_region_deleting_before_inserting(config_dir):
    _, client = run(config_dir, existing=["osm_canals"])

    sql, config = client.queries[-1]
    assert sql.index("DELETE FROM cells WHERE region = @region") < sql.index(
        "INSERT INTO cells"
    )
    assert "BEGIN TRANSACTION" in sql and "COMMIT TRANSACTION" in sql
    assert "MIN(ST_DISTANCE(" in sql
    assert "LEFT JOIN" in sql
    assert {p.name: p.value for p in config.query_parameters} == {"region": "riau"}


def test_the_cells_table_exists_before_the_rewrite(config_dir):
    _, client = run(config_dir, existing=["osm_canals"])

    assert client.created[0].table_id == "cells"
    assert client.created[0].clustering_fields == ["region", "cell_id"]
    assert client.calls == ["load", "create", "query"]


def test_every_query_caps_bytes_billed(config_dir):
    _, client = run(config_dir)

    for sql, config in client.queries:
        expected = (
            CANAL_MAX_BYTES_BILLED
            if "CREATE TABLE osm_canals" in sql
            else MAX_BYTES_BILLED
        )
        assert config.maximum_bytes_billed == expected


def test_a_dry_run_estimates_the_canal_query_and_writes_nothing(config_dir):
    summary, client = run(config_dir, dry_run=True)

    assert len(client.queries) == 1
    assert client.queries[0][1].dry_run is True
    assert client.loads == []
    assert client.created == []
    assert summary["dry_run"] is True
    assert summary["queries"] == [
        {"step": "osm_canals", "bytes": 52_428_800, "estimate": True}
    ]


def test_the_summary_counts_cells_by_peat_class_and_reports_bytes(config_dir):
    summary, _ = run(config_dir)

    assert summary["region"] == "riau"
    assert summary["cells"] == 2
    assert summary["peat_class_counts"] == {"1": 1, "2": 1}
    assert [q["step"] for q in summary["queries"]] == ["osm_canals", "cells"]
    assert all(q["estimate"] is False for q in summary["queries"])


def test_no_peat_cells_is_a_job_error_and_writes_nothing(config_dir):
    with pytest.raises(JobError, match="no peat cells"):
        run(config_dir, features=[feature("1,1", 0)])


def test_help_exits_zero(capsys):
    with pytest.raises(SystemExit) as exit_info:
        job.main(["--help"], {})

    assert exit_info.value.code == 0
    assert "--dry-run" in capsys.readouterr().out


def test_no_arguments_is_a_usage_error():
    with pytest.raises(SystemExit) as exit_info:
        job.main([], {})

    assert exit_info.value.code == 2


def test_an_unknown_flag_is_a_usage_error():
    with pytest.raises(SystemExit) as exit_info:
        job.main(["--region", "riau", "--bogus"], {})

    assert exit_info.value.code == 2


def test_an_unknown_region_exits_two(capsys):
    code = job.main(["--region", "atlantis"], {"GOOGLE_CLOUD_PROJECT": "p"})

    assert code == 2
    assert "atlantis" in capsys.readouterr().err


def test_a_missing_project_exits_two(capsys):
    code = job.main(["--region", "riau"], {})

    assert code == 2
    assert "GOOGLE_CLOUD_PROJECT" in capsys.readouterr().err
