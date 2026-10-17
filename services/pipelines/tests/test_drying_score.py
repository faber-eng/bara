from datetime import UTC, date, datetime

import pytest

from adapters.bigquery import MAX_BYTES_BILLED, Warehouse
from ee_lib.config import load_data_config, load_region, read_aoi
from ee_lib.weeks import DateRange
from jobs import drying_score as job
from jobs.cli import JobError
from tests.fakes import FakeEarth, RecordingBigQueryClient

WEEK = date(2026, 10, 12)
TODAY = date(2026, 10, 17)
CELLS = [
    {"cell_id": "riau-1-1", "peat_class": 1, "canal_dist_m": 0.0},
    {"cell_id": "riau-1-2", "peat_class": 2, "canal_dist_m": 1500.0},
    {"cell_id": "riau-1-3", "peat_class": 1, "canal_dist_m": 300.0},
]
MEASURED = [
    {
        "cell_id": "riau-1-1",
        "s1_recent_anom_db": -3.0,
        "s1_previous_anom_db": -2.0,
        "rain_30d_mm": 20.0,
        "clim_rain_30d_mm": 200.0,
    },
    {
        "cell_id": "riau-1-2",
        "s1_recent_anom_db": 0.5,
        "s1_previous_anom_db": 0.0,
        "rain_30d_mm": 250.0,
        "clim_rain_30d_mm": 200.0,
    },
    {
        "cell_id": "riau-1-3",
        "s1_recent_anom_db": None,
        "s1_previous_anom_db": -1.0,
        "rain_30d_mm": 120.0,
        "clim_rain_30d_mm": 200.0,
    },
]


def run(config_dir, *, cells=CELLS, dry_run=False):
    client = RecordingBigQueryClient(responses={"FROM cells": cells})
    earth = FakeEarth(measurements=MEASURED, chirps_last=date(2026, 9, 30))
    region = load_region(config_dir, "riau")
    summary = job.drying_score(
        region=region,
        aoi=read_aoi(config_dir, region),
        week_start=WEEK,
        today=TODAY,
        earth=earth,
        warehouse=Warehouse(client, project="p", dataset="bara"),
        drying=load_data_config(config_dir).drying,
        dry_run=dry_run,
    )
    return summary, client, earth


def test_reads_the_region_cells_with_a_parameter(config_dir):
    _, client, _ = run(config_dir)

    sql, config = client.queries[0]
    assert "FROM cells" in sql
    assert {p.name: p.value for p in config.query_parameters} == {"region": "riau"}


def test_measures_the_bigquery_cells_for_the_week_window(config_dir):
    _, _, earth = run(config_dir)

    assert ("chirps_last_day", date(2026, 10, 18)) in earth.calls
    _, (cells_table, week_start, window) = earth.calls[-1]
    assert cells_table == "p.bara.cells"
    assert week_start == WEEK
    assert window.s1_recent == DateRange(date(2026, 10, 6), date(2026, 10, 18))
    assert window.rain == DateRange(date(2026, 9, 1), date(2026, 10, 1))


def test_deletes_the_region_week_before_loading(config_dir):
    _, client, _ = run(config_dir)

    delete_sql, delete_config = client.queries[-1]
    assert delete_sql.strip().startswith("DELETE FROM cell_weekly_drying")
    params = {p.name: p.value for p in delete_config.query_parameters}
    assert params == {"region": "riau", "week_start": WEEK}
    assert client.calls[-2:] == ["query", "load"]


def test_loads_scored_rows_by_append_into_the_partitioned_table(config_dir):
    _, client, _ = run(config_dir)

    created = client.created[0]
    assert created.table_id == "cell_weekly_drying"
    assert created.time_partitioning.field == "week_start"
    assert created.clustering_fields == ["region", "cell_id"]
    table_id, rows, config = client.loads[0]
    assert table_id == "p.bara.cell_weekly_drying"
    assert config.write_disposition == "WRITE_APPEND"
    assert [row["rank"] for row in rows] == [1, 2, 3]
    assert rows[0]["cell_id"] == "riau-1-1"
    assert rows[0]["week_start"] == "2026-10-12"
    assert set(rows[0]) == {field.name for field in config.schema}


def test_every_query_caps_bytes_billed_at_one_gigabyte(config_dir):
    _, client, _ = run(config_dir)

    assert len(client.queries) == 2
    for _, config in client.queries:
        assert config.maximum_bytes_billed == MAX_BYTES_BILLED


def test_a_dry_run_scores_but_writes_nothing(config_dir):
    summary, client, _ = run(config_dir, dry_run=True)

    assert len(client.queries) == 1
    assert client.loads == []
    assert client.created == []
    assert summary["dry_run"] is True
    assert summary["cells"] == 3


def test_the_summary_reports_nulls_stale_scores_and_top_cells(config_dir):
    summary, _, _ = run(config_dir)

    assert summary["region"] == "riau"
    assert summary["week"] == "2026-W42"
    assert summary["s1_null"] == 0
    assert summary["stale_s1"] == 1
    assert 0 <= summary["score_min"] <= summary["score_max"] <= 100
    assert [cell["cell_id"] for cell in summary["top"]] == [
        "riau-1-1",
        "riau-1-3",
        "riau-1-2",
    ]
    assert [q["step"] for q in summary["queries"]] == ["read_cells", "delete_week"]


def test_no_cells_is_a_job_error_naming_build_grid(config_dir):
    with pytest.raises(JobError, match="build_grid"):
        run(config_dir, cells=[])


def test_help_exits_zero(capsys):
    with pytest.raises(SystemExit) as exit_info:
        job.main(["--help"], {})

    assert exit_info.value.code == 0
    assert "--week" in capsys.readouterr().out


def test_no_arguments_is_a_usage_error():
    with pytest.raises(SystemExit) as exit_info:
        job.main([], {})

    assert exit_info.value.code == 2


def test_a_bad_week_exits_two(capsys):
    code = job.main(
        ["--region", "riau", "--week", "W42"], {"GOOGLE_CLOUD_PROJECT": "p"}
    )

    assert code == 2
    assert "W42" in capsys.readouterr().err


def test_a_future_week_exits_two(capsys, monkeypatch):
    monkeypatch.setattr(job, "utcnow", lambda: datetime(2026, 10, 17, 4, tzinfo=UTC))

    code = job.main(
        ["--region", "riau", "--week", "2026-W43"], {"GOOGLE_CLOUD_PROJECT": "p"}
    )

    assert code == 2
    assert "2026-W43" in capsys.readouterr().err
