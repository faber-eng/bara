import json
from datetime import UTC, date, datetime

import pytest

from adapters.bigquery import Warehouse
from adapters.events import EventPublisher
from adapters.rankings_store import RankingsStore
from jobs import publish_rankings as job
from jobs.cli import JobError
from tests.fakes import FakeFirestore, FakePubSub, RecordingBigQueryClient

WEEK = date(2026, 10, 12)
NOW = datetime(2026, 10, 17, 12, 0, tzinfo=UTC)


def cell_row(rank):
    return {
        "cell_id": f"riau-{rank}-1",
        "region": "riau",
        "week_start": WEEK,
        "s1_anom_db": -2.0,
        "stale_s1": False,
        "rain_30d_mm": 30.0,
        "rain_deficit_pct": 0.4,
        "canal_dist_m": 100.0,
        "peat_class": 1,
        "drying_score": 99.0 - rank * 0.1,
        "rank": rank,
        "lat": 0.6,
        "lon": 102.1,
        "prev_rank": None,
    }


def dam_feature(number, state):
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [102.1, 0.6]},
        "properties": {
            "id": f"dam-riau-{number:03d}",
            "canal_osm_id": "1",
            "region": "riau",
            "last_state": state,
            "last_checked_at": None,
            "example": True,
        },
    }


DAMS_JSON = {
    "features": [dam_feature(n, "broken" if n == 3 else "intact") for n in range(1, 61)]
}
DAM_CELLS = [
    {
        "dam_id": f"dam-riau-{n:03d}",
        "cell_id": f"riau-{n}-1",
        "drying_score": 50.0 + n / 10,
    }
    for n in range(1, 61)
]


def run(
    tmp_path,
    *,
    cells=200,
    dams=DAMS_JSON,
    dry_run=False,
    firestore=None,
    log=None,
    **options,
):
    log = log if log is not None else []
    bigquery = RecordingBigQueryClient(
        responses={
            "FROM cell_weekly_drying AS d": [cell_row(n) for n in range(1, cells + 1)],
            "JSON_QUERY_ARRAY": DAM_CELLS,
        }
    )
    firestore = firestore if firestore is not None else FakeFirestore()
    pubsub = FakePubSub(message_id="msg-7", log=log)
    if dams is not None:
        (tmp_path / "dams_riau_sample.geojson").write_text(json.dumps(dams))
    summary = job.publish_rankings(
        region="riau",
        week_start=WEEK,
        warehouse=Warehouse(bigquery, project="p", dataset="bara"),
        store=RankingsStore(firestore),
        publisher=EventPublisher(pubsub, "p"),
        data_dir=tmp_path,
        now=NOW,
        new_id=lambda: "evt-1",
        dry_run=dry_run,
        **options,
    )
    return summary, bigquery, firestore, pubsub


def by_kind(firestore, kind):
    prefix = f"rankings/riau/{kind}/"
    return {
        k[len(prefix) :]: v for k, v in firestore.docs.items() if k.startswith(prefix)
    }


def test_writes_200_cells_and_50_dams_with_iso_week_strings(tmp_path):
    summary, _, firestore, _ = run(tmp_path)

    cells = by_kind(firestore, "cells")
    dams = by_kind(firestore, "dams")
    assert len(cells) == 200
    assert len(dams) == 50
    assert cells["riau-1-1"]["week_start"] == "2026-10-12"
    assert cells["riau-1-1"]["rank"] == 1
    assert summary["cells"] == 200
    assert summary["dams"] == 50
    assert summary["dams_in_file"] == 60


def test_dams_are_ranked_by_cell_score_plus_state(tmp_path):
    _, _, firestore, _ = run(tmp_path)

    dams = by_kind(firestore, "dams")
    assert dams["dam-riau-003"]["rank"] == 1
    assert all(dam["example"] is True for dam in dams.values())


def test_the_limits_come_from_the_spec(tmp_path):
    _, bigquery, _, _ = run(tmp_path)

    config = next(c for sql, c in bigquery.queries if "cell_weekly_drying AS d" in sql)
    assert {p.name: p.value for p in config.query_parameters}["limit"] == 200
    assert job.TOP_CELLS == 200
    assert job.TOP_DAMS == 50


def test_publishes_drying_ranked_as_real_data_after_the_firestore_write(tmp_path):
    log = []
    firestore = FakeFirestore()
    original = firestore.batch

    def logging_batch():
        batch = original()
        commit = batch.commit
        batch.commit = lambda: (log.append("commit"), commit())[1]
        return batch

    firestore.batch = logging_batch

    summary, _, _, pubsub = run(tmp_path, firestore=firestore, log=log)

    path, data, _ = pubsub.published[0]
    event = json.loads(data)
    assert log.index("publish") > max(i for i, e in enumerate(log) if e == "commit")
    assert path.endswith("/topics/drying.ranked")
    assert event["example"] is False
    assert event["payload"]["week"] == "2026-W42"
    assert summary["message_id"] == "msg-7"


def test_replaces_the_previous_set(tmp_path):
    firestore = FakeFirestore(
        {"rankings/riau/cells/riau-999-9": {}, "rankings/riau/dams/dam-riau-999": {}}
    )

    summary, _, firestore, _ = run(tmp_path, firestore=firestore)

    assert "rankings/riau/cells/riau-999-9" not in firestore.docs
    assert "rankings/riau/dams/dam-riau-999" not in firestore.docs
    assert summary["deleted"] == {"cells": 1, "dams": 1}


def test_dry_run_writes_and_publishes_nothing(tmp_path):
    summary, _, firestore, pubsub = run(tmp_path, dry_run=True)

    assert firestore.docs == {}
    assert pubsub.published == []
    assert summary["dry_run"] is True
    assert summary["cells"] == 200


def test_no_scored_cells_is_a_job_error_and_writes_nothing(tmp_path):
    firestore = FakeFirestore({"rankings/riau/cells/old": {}})

    with pytest.raises(JobError):
        run(tmp_path, cells=0, firestore=firestore)

    assert "rankings/riau/cells/old" in firestore.docs


def test_a_region_without_a_dams_file_publishes_cells_only(tmp_path):
    summary, bigquery, firestore, _ = run(tmp_path, dams=None)

    assert len(by_kind(firestore, "dams")) == 0
    assert summary["dams"] == 0
    assert not any("JSON_QUERY_ARRAY" in sql for sql, _ in bigquery.queries)


def test_a_malformed_dams_file_stops_before_any_write(tmp_path):
    bad = {"features": [{**dam_feature(1, "intact")}]}
    bad["features"][0]["properties"]["extra"] = 1
    firestore = FakeFirestore()

    with pytest.raises(JobError):
        run(tmp_path, dams=bad, firestore=firestore)

    assert firestore.docs == {}


def test_every_publish_also_keeps_the_week_snapshot(tmp_path):
    _, _, firestore, _ = run(tmp_path)

    prefix = "rankings/riau/weeks/2026-W42"
    snapshot_cells = [k for k in firestore.docs if k.startswith(f"{prefix}/cells/")]
    snapshot_dams = [k for k in firestore.docs if k.startswith(f"{prefix}/dams/")]
    assert len(snapshot_cells) == 200
    assert len(snapshot_dams) == 50
    assert firestore.docs[f"{prefix}/cells/riau-1-1"]["rank"] == 1


def test_a_backfill_week_writes_only_its_snapshot_and_sends_no_event(tmp_path):
    firestore = FakeFirestore({"rankings/riau/cells/keep": {"v": 1}})

    summary, _, firestore, pubsub = run(
        tmp_path, firestore=firestore, latest=False, announce=False
    )

    assert firestore.docs["rankings/riau/cells/keep"] == {"v": 1}
    assert "rankings/riau/weeks/2026-W42/cells/riau-1-1" in firestore.docs
    assert pubsub.published == []
    assert "message_id" not in summary


def test_the_newest_backfill_week_refreshes_the_latest_set_without_an_event(tmp_path):
    summary, _, firestore, pubsub = run(tmp_path, latest=True, announce=False)

    assert len(by_kind(firestore, "cells")) == 200
    assert pubsub.published == []
    assert "message_id" not in summary


def test_only_a_full_flow_region_announces_its_ranking(config_dir):
    from ee_lib.config import load_region

    assert job.announces(load_region(config_dir, "riau")) is True
    assert job.announces(load_region(config_dir, "congo_cuvette")) is False
def test_writes_a_run_record_with_the_exact_run_time_before_it_announces(tmp_path):
    _, _, firestore, pubsub = run(tmp_path)

    record = firestore.docs["rankings/riau/weeks/2026-W42"]
    assert record == {
        "ran_at": NOW,
        "s1_pass_date": "2026-10-12",
        "cells": 200,
        "dams": 50,
    }
    assert len(pubsub.published) == 1


def test_a_dry_run_writes_no_run_record(tmp_path):
    _, _, firestore, _ = run(tmp_path, dry_run=True)

    assert "rankings/riau/weeks/2026-W42" not in firestore.docs
