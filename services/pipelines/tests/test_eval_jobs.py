import json
from datetime import UTC, date, datetime

import pytest

from adapters.bigquery import Warehouse
from jobs import eval_drying, eval_reignition
from jobs.cli import JobError
from tests.fakes import RecordingBigQueryClient

NOW = datetime(2026, 10, 18, 5, 0, tzinfo=UTC)
WEEKS = [
    {"week_start": date(2026, 8, 3), "cells": 100, "hotspots": 20, "captured": 8},
    {"week_start": date(2026, 10, 5), "cells": 100, "hotspots": 0, "captured": 0},
]
DRYING_RESPONSES = {
    "__TABLES__": [{"modified": date(2026, 10, 17)}],
    "firms_detections AS f": WEEKS,
}


def warehouse_with(responses):
    client = RecordingBigQueryClient(responses=responses)
    return Warehouse(client, project="p", dataset="bara"), client


def test_eval_drying_writes_the_table_and_the_report(tmp_path):
    warehouse, client = warehouse_with(DRYING_RESPONSES)

    summary = eval_drying.eval_drying(
        region_id="riau",
        years=(2026,),
        warehouse=warehouse,
        evaluated_at=NOW,
        out_dir=tmp_path,
    )

    [year] = summary["years"]
    assert year["weeks"] == 1
    assert year["capture_rate"] == 0.4
    assert year["lift"] == pytest.approx(4.0)
    assert summary["detections_through"] == "2026-10-15"
    [(table, rows, _)] = client.loads
    assert table == "p.bara.eval_drying"
    assert rows[0]["year"] == 2026
    assert rows[0]["evaluated_at"] == NOW.isoformat()
    written = json.loads((tmp_path / "drying.json").read_text())
    assert written["years"] == summary["years"]
    assert written["follow_weeks"] == [1, 4]


def test_every_query_is_capped(tmp_path):
    warehouse, client = warehouse_with(DRYING_RESPONSES)

    eval_drying.eval_drying(
        region_id="riau",
        years=(2019, 2026),
        warehouse=warehouse,
        evaluated_at=NOW,
        out_dir=tmp_path,
    )

    assert len(client.queries) == 3
    assert all(config.maximum_bytes_billed for _, config in client.queries)


def test_eval_reignition_copies_the_newest_test_rows(tmp_path):
    rows = [
        {
            "evaluated_at": NOW,
            "model": model,
            "split": "test",
            "events": 118,
            "positives": 13,
            "auc": auc,
            "precision_top10": 0.25,
            "recall_top10": 0.2,
        }
        for model, auc in (
            ("reignition_v1", 0.662),
            ("reignition_v1_no_rain_after", 0.637),
            ("detection_days_baseline", 0.708),
        )
    ]
    warehouse, _ = warehouse_with({"FROM eval_reignition": rows})

    summary = eval_reignition.eval_reignition(
        region_id="riau", warehouse=warehouse, out_dir=tmp_path
    )

    assert summary["run_at"] == NOW.isoformat()
    assert summary["baseline"]["auc"] == 0.708
    written = json.loads((tmp_path / "reignition.json").read_text())
    assert written["model"]["auc"] == 0.662


def test_eval_reignition_without_rows_is_a_job_error(tmp_path):
    warehouse, _ = warehouse_with({"FROM eval_reignition": []})

    with pytest.raises(JobError):
        eval_reignition.eval_reignition(
            region_id="riau", warehouse=warehouse, out_dir=tmp_path
        )
