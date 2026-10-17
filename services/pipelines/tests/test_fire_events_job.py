from datetime import date

import pytest

from adapters.bigquery import Warehouse
from ee_lib.config import load_data_config, load_region, read_aoi
from jobs import fire_events as job
from jobs.cli import JobError
from tests.fakes import FakeFireEarth, RecordingBigQueryClient

TODAY = date(2026, 10, 17)
FIRMS_LAST = date(2026, 10, 17)
LAST_FULL_DAY = date(2026, 10, 16)


def feature(day: str, lon=102.28, lat=0.83, t21=312.9, confidence=36):
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [lon, lat]},
        "properties": {"T21": t21, "confidence": confidence, "detect_date": day},
    }


SIGHTINGS = [
    {
        "cell_id": "riau-1-1",
        "detect_date": date(2019, 8, 1),
        "inside": True,
        "t21": 320.0,
        "confidence": 60,
    },
    {
        "cell_id": "riau-1-1",
        "detect_date": date(2019, 8, 12),
        "inside": False,
        "t21": 315.0,
        "confidence": 40,
    },
    {
        "cell_id": "riau-1-2",
        "detect_date": date(2026, 10, 15),
        "inside": True,
        "t21": 330.0,
        "confidence": 80,
    },
    {
        "cell_id": "riau-1-3",
        "detect_date": date(2026, 9, 1),
        "inside": True,
        "t21": 330.0,
        "confidence": 80,
    },
]


DETECTIONS = {2019: [feature("2019-08-01")], 2026: [feature("2026-10-15")]}


def run(config_dir, *, sightings=SIGHTINGS, dry_run=False, detections=DETECTIONS):
    client = RecordingBigQueryClient(responses={"FROM cells AS cell": sightings})
    earth = FakeFireEarth(features_by_year=detections, firms_last=FIRMS_LAST)
    region = load_region(config_dir, "riau")
    data = load_data_config(config_dir)
    summary = job.fire_events(
        region="riau",
        aoi=read_aoi(config_dir, region),
        rules=data.reignition,
        grid_cell_m=data.grid_cell_m,
        today=TODAY,
        earth=earth,
        warehouse=Warehouse(client, project="p", dataset="bara"),
        dry_run=dry_run,
    )
    return summary, client, earth


def test_reads_firms_one_year_at_a_time_to_the_last_full_day(config_dir):
    _, _, earth = run(config_dir)

    assert earth.calls[0] == ("firms_last_day", date(2026, 10, 18))
    reads = [args for name, args in earth.calls if name == "fire_detections"]
    assert len(reads) == 26
    assert reads[0] == (2000, date(2001, 1, 1), date(2002, 1, 1))
    assert reads[-1] == (2000, date(2026, 1, 1), date(2026, 10, 17))


def test_replaces_the_region_detections_before_reading_sightings(config_dir):
    _, client, _ = run(config_dir)

    sql = client.sql_sent()
    assert "DELETE FROM firms_detections WHERE region = @region;" in sql[0]
    assert (
        "INSERT INTO firms_detections SELECT * FROM firms_detections_staging"
        in (sql[0])
    )
    destination, rows, config = client.loads[0]
    assert destination == "p.bara.firms_detections_staging"
    assert config.write_disposition == "WRITE_TRUNCATE"
    assert rows == [
        {
            "region": "riau",
            "detect_date": "2019-08-01",
            "point": "POINT(102.28 0.83)",
            "t21": 312.9,
            "confidence": 36.0,
        },
        {
            "region": "riau",
            "detect_date": "2026-10-15",
            "point": "POINT(102.28 0.83)",
            "t21": 312.9,
            "confidence": 36.0,
        },
    ]
    assert client.calls[:3] == ["create", "load", "query"]


def test_reads_sightings_within_the_label_radius(config_dir):
    _, client, _ = run(config_dir)

    sql, config = client.queries[1]
    assert "ST_DWITHIN(cell.centroid, detection.point, @radius_m)" in sql
    params = {p.name: p.value for p in config.query_parameters}
    assert params == {"region": "riau", "radius_m": 1000}


def test_writes_quiet_events_with_their_label(config_dir):
    summary, client, _ = run(config_dir)

    assert "DELETE FROM fire_events WHERE region = @region;" in client.sql_sent()[-1]
    destination, rows, _ = client.loads[-1]
    assert destination == "p.bara.fire_events_staging"
    assert rows == [
        {
            "event_id": "riau-1-1-20190801",
            "cell_id": "riau-1-1",
            "region": "riau",
            "start_date": "2019-08-01",
            "last_detection_date": "2019-08-01",
            "quiet_date": "2019-08-04",
            "detection_days": 1,
            "max_t21": 320.0,
            "mean_confidence": 60.0,
            "reignited": 1,
        },
        {
            "event_id": "riau-1-3-20260901",
            "cell_id": "riau-1-3",
            "region": "riau",
            "start_date": "2026-09-01",
            "last_detection_date": "2026-09-01",
            "quiet_date": "2026-09-04",
            "detection_days": 1,
            "max_t21": 330.0,
            "mean_confidence": 80.0,
            "reignited": 0,
        },
    ]
    assert summary["events"] == 2
    assert summary["reignited"] == 1
    assert summary["unlabeled"] == 0
    assert summary["observed_until"] == LAST_FULL_DAY
    assert summary["years"] == {
        2019: {"events": 1, "reignited": 1},
        2026: {"events": 1, "reignited": 0},
    }


def test_dry_run_estimates_the_sightings_query_and_writes_nothing(config_dir):
    summary, client, _ = run(config_dir, dry_run=True)

    assert client.loads == []
    assert len(client.queries) == 1
    assert client.queries[0][1].dry_run is True
    assert summary["detections"] == 2
    assert summary["queries"][0]["estimate"] is True


def test_no_detections_is_a_job_error_before_any_write(config_dir):
    client = RecordingBigQueryClient()
    earth = FakeFireEarth(features_by_year={}, firms_last=FIRMS_LAST)
    region = load_region(config_dir, "riau")
    data = load_data_config(config_dir)

    with pytest.raises(JobError, match="no FIRMS detections"):
        job.fire_events(
            region="riau",
            aoi=read_aoi(config_dir, region),
            rules=data.reignition,
            grid_cell_m=data.grid_cell_m,
            today=TODAY,
            earth=earth,
            warehouse=Warehouse(client, project="p", dataset="bara"),
            dry_run=False,
        )
    assert client.calls == []


def test_no_events_is_a_job_error(config_dir):
    with pytest.raises(JobError, match="no fire events"):
        run(config_dir, sightings=[])


def test_a_malformed_firms_feature_is_a_job_error(config_dir):
    client = RecordingBigQueryClient()
    earth = FakeFireEarth(
        features_by_year={2019: [{"geometry": None}]}, firms_last=FIRMS_LAST
    )
    region = load_region(config_dir, "riau")
    data = load_data_config(config_dir)

    with pytest.raises(JobError, match="FIRMS feature is malformed"):
        job.fire_events(
            region="riau",
            aoi=read_aoi(config_dir, region),
            rules=data.reignition,
            grid_cell_m=data.grid_cell_m,
            today=TODAY,
            earth=earth,
            warehouse=Warehouse(client, project="p", dataset="bara"),
            dry_run=False,
        )
