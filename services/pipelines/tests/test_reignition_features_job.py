from datetime import date

import pytest

from adapters.bigquery import Warehouse
from ee_lib.config import load_data_config, load_region, read_aoi
from ee_lib.weeks import DateRange
from jobs import reignition_features as job
from jobs.cli import JobError, UsageError
from tests.fakes import FakeFeatureEarth, RecordingBigQueryClient

TODAY = date(2026, 10, 17)
SINCE = date(2015, 1, 1)
EVENTS = [
    {
        "event_id": "riau-1-1-20190801",
        "cell_id": "riau-1-1",
        "region": "riau",
        "start_date": date(2019, 8, 1),
        "quiet_date": date(2019, 8, 10),
        "reignited": 1,
        "detection_days": 4,
        "max_t21": 330.5,
        "mean_confidence": 62.5,
        "peat_class": 1,
        "canal_dist_m": 250.0,
        "burned_years": [2016, 2017, 2018],
    },
    {
        "event_id": "riau-1-2-20260920",
        "cell_id": "riau-1-2",
        "region": "riau",
        "start_date": date(2026, 9, 20),
        "quiet_date": date(2026, 9, 27),
        "reignited": None,
        "detection_days": 1,
        "max_t21": 310.0,
        "mean_confidence": 40.0,
        "peat_class": 2,
        "canal_dist_m": 900.0,
        "burned_years": [],
    },
]
MEASURES = [
    {
        "cell_id": "riau-1-1",
        "quiet_date": "2019-08-10",
        "s1_anom_db": -1.5,
        "rain_7d_before_mm": 2.0,
        "rain_14d_before_mm": 10.0,
        "rain_7d_after_mm": 30.0,
    },
    {
        "cell_id": "riau-1-2",
        "quiet_date": "2026-09-27",
        "s1_anom_db": None,
        "rain_7d_before_mm": 5.0,
        "rain_14d_before_mm": 8.0,
    },
]
PEAT = [
    {"cell_id": "riau-1-1", "peat_fraction": 1.0},
    {"cell_id": "riau-1-2", "peat_fraction": 0.4},
]


def run(config_dir, *, events=EVENTS, measures=MEASURES, dry_run=False):
    client = RecordingBigQueryClient(responses={"FROM fire_events": events})
    earth = FakeFeatureEarth(
        measures=measures, peat=PEAT, chirps_last=date(2026, 9, 30)
    )
    region = load_region(config_dir, "riau")
    summary = job.reignition_features(
        region=region,
        aoi=read_aoi(config_dir, region),
        data=load_data_config(config_dir),
        since=SINCE,
        today=TODAY,
        earth=earth,
        warehouse=Warehouse(client, project="p", dataset="bara"),
        dry_run=dry_run,
    )
    return summary, client, earth


def test_reads_the_events_since_the_day(config_dir):
    _, client, _ = run(config_dir)

    sql, config = client.queries[0]
    assert "FROM fire_events AS event" in sql
    params = {p.name: p.value for p in config.query_parameters}
    assert params == {"region": "riau", "since": SINCE}


def test_measures_each_quiet_date_with_its_windows(config_dir):
    _, _, earth = run(config_dir)

    name, (cells_table, dates) = earth.calls[2]
    assert name == "reignition_measures"
    assert cells_table == "p.bara.cells"
    first_date, first_cells, first_windows = dates[0]
    assert first_date == date(2019, 8, 10)
    assert first_cells == ["riau-1-1"]
    assert first_windows.s1 == DateRange(date(2019, 7, 29), date(2019, 8, 10))
    assert dates[1][2].rain_7d_after is None


def test_rewrites_the_training_rows_since_the_day(config_dir):
    summary, client, _ = run(config_dir)

    destination, rows, _ = client.loads[0]
    assert destination == "p.bara.reignition_training_staging"
    assert rows[0] == {
        "event_id": "riau-1-1-20190801",
        "cell_id": "riau-1-1",
        "region": "riau",
        "quiet_date": "2019-08-10",
        "split": "train",
        "reignited": 1,
        "peat_class": 1,
        "peat_fraction": 1.0,
        "canal_dist_m": 250.0,
        "s1_anom_db": -1.5,
        "rain_7d_before_mm": 2.0,
        "rain_14d_before_mm": 10.0,
        "rain_7d_after_mm": 30.0,
        "detection_days": 4,
        "max_t21": 330.5,
        "mean_confidence": 62.5,
        "month": 8,
        "prior_years_burned": 3,
    }
    assert rows[1]["split"] == "test"
    assert rows[1]["rain_7d_after_mm"] is None
    sql, _ = client.queries[-1]
    assert "DELETE FROM reignition_training WHERE region = @region" in sql
    assert "AND quiet_date >= @since" in sql
    assert summary["splits"] == {
        "test": {"rows": 1, "reignited": 0, "unlabeled": 1},
        "train": {"rows": 1, "reignited": 1, "unlabeled": 0},
    }
    assert summary["nulls"]["s1_anom_db"] == 1
    assert summary["nulls"]["rain_7d_after_mm"] == 1


def test_dry_run_writes_nothing(config_dir):
    summary, client, _ = run(config_dir, dry_run=True)

    assert client.loads == []
    assert summary["rows"] == 2


def test_peat_is_measured_before_the_quiet_dates(config_dir):
    _, _, earth = run(config_dir)

    assert [name for name, _ in earth.calls] == [
        "chirps_last_day",
        "peat_fractions",
        "reignition_measures",
    ]


def test_no_events_since_the_day_clears_the_rows_since_the_day(config_dir):
    summary, client, earth = run(config_dir, events=[])

    assert client.loads == []
    assert earth.calls == []
    sql, _ = client.queries[-1]
    assert "DELETE FROM reignition_training WHERE region = @region" in sql
    assert "AND quiet_date >= @since" in sql
    assert "INSERT" not in sql
    assert summary["rows"] == 0


def test_no_events_on_a_dry_run_clears_nothing(config_dir):
    _, client, _ = run(config_dir, events=[], dry_run=True)

    assert len(client.queries) == 1


def test_a_null_quiet_date_is_a_job_error(config_dir):
    events = [{**EVENTS[0], "quiet_date": None}]

    with pytest.raises(JobError, match="quiet_date"):
        run(config_dir, events=events)


def test_a_missing_measure_is_a_job_error(config_dir):
    with pytest.raises(JobError, match="no Earth Engine measure"):
        run(config_dir, measures=MEASURES[:1])


def test_since_is_the_first_train_year_for_a_full_rebuild(config_dir):
    data = load_data_config(config_dir)

    assert job.resolve_since(True, 60, TODAY, data, None) == date(2015, 1, 1)
    assert job.resolve_since(False, 60, TODAY, data, None) == date(2026, 8, 18)


@pytest.mark.parametrize(
    ("oldest_open", "since"),
    [
        (date(2026, 9, 1), date(2026, 8, 18)),
        (date(2026, 5, 2), date(2026, 5, 2)),
        (date(2010, 5, 2), date(2015, 1, 1)),
    ],
)
def test_an_incremental_run_reaches_back_to_the_oldest_open_row(
    config_dir, oldest_open, since
):
    data = load_data_config(config_dir)

    assert job.resolve_since(False, 60, TODAY, data, oldest_open) == since


def test_the_oldest_open_row_is_read_with_a_capped_query(config_dir):
    client = RecordingBigQueryClient(
        responses={"MIN(quiet_date)": [{"oldest": date(2026, 5, 2)}]},
        existing=["reignition_training"],
    )
    warehouse = Warehouse(client, project="p", dataset="bara")

    assert job.oldest_open_quiet_date(warehouse, "riau") == date(2026, 5, 2)
    sql, config = client.queries[0]
    assert "reignited IS NULL OR rain_7d_after_mm IS NULL" in sql
    assert config.maximum_bytes_billed == 1_000_000_000


def test_no_table_yet_means_no_open_row(config_dir):
    client = RecordingBigQueryClient()
    warehouse = Warehouse(client, project="p", dataset="bara")

    assert job.oldest_open_quiet_date(warehouse, "riau") is None
    assert client.queries == []


def test_days_below_one_is_a_usage_error(config_dir):
    with pytest.raises(UsageError):
        job.resolve_since(False, 0, TODAY, load_data_config(config_dir), None)
