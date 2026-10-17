from datetime import UTC, datetime

import pytest

from adapters.bigquery import Warehouse
from jobs import train_reignition as job
from jobs.cli import JobError
from tests.fakes import RecordingBigQueryClient

NOW = datetime(2026, 10, 18, 1, 0, tzinfo=UTC)
PREDICTIONS = [
    {"event_id": "a", "reignited": 1, "detection_days": 9, "p_reignite": 0.9},
    {"event_id": "b", "reignited": 0, "detection_days": 1, "p_reignite": 0.2},
]
RESPONSES = {
    "ML.EVALUATE": [{"roc_auc": 0.7, "log_loss": 0.6}],
    "ML.PREDICT": PREDICTIONS,
    "ML.GLOBAL_EXPLAIN": [{"feature": "detection_days", "attribution": 0.3}],
}


def run(*, dry_run=False, responses=RESPONSES):
    client = RecordingBigQueryClient(responses=responses)
    summary = job.train_reignition(
        region_id="riau",
        warehouse=Warehouse(client, project="p", dataset="bara"),
        evaluated_at=NOW,
        dry_run=dry_run,
    )
    return summary, client


def test_a_dry_run_estimates_both_training_queries_and_trains_nothing():
    summary, client = run(dry_run=True)

    assert len(client.queries) == 2
    assert all(config.dry_run for _, config in client.queries)
    assert not any("CREATE" in sql for sql in client.sql_sent())
    assert client.loads == []
    assert [query["estimate"] for query in summary["queries"]] == [True, True]


def test_trains_both_variants_registered_to_vertex_ai():
    _, client = run()

    creates = [sql for sql in client.sql_sent() if "CREATE OR REPLACE MODEL" in sql]
    assert len(creates) == 2
    full, without_after = creates
    assert "`p.bara.reignition_v1`" in full
    assert "model_type = 'LOGISTIC_REG'" in full
    assert "CAST(month AS STRING) AS month" in full
    assert "CAST(peat_class AS STRING) AS peat_class" in full
    assert "data_split_method = 'CUSTOM'" in full
    assert "data_split_col = 'is_eval'" in full
    assert "auto_class_weights = TRUE" in full
    assert "enable_global_explain = TRUE" in full
    assert "model_registry = 'VERTEX_AI'" in full
    assert "vertex_ai_model_id = 'bara_reignition'" in full
    assert "max_iterations = 20" in full
    assert (
        "SELECT * EXCEPT(event_id, cell_id, region, quiet_date, split), "
        "split = 'valid' AS is_eval" in full
    )
    assert "split IN ('train', 'valid')" in full
    assert "`p.bara.reignition_v1_no_rain_after`" in without_after
    assert "vertex_ai_model_id = 'bara_reignition_no_rain_after'" in without_after
    assert "EXCEPT(event_id, cell_id, region, quiet_date, split, rain_7d_after_mm)" in (
        without_after
    )


def test_every_model_query_is_capped():
    _, client = run()

    assert all(
        config.maximum_bytes_billed == 1_000_000_000
        for sql, config in client.queries
        if not config.dry_run
    )


def test_writes_model_and_baseline_rows_for_valid_and_test():
    summary, client = run()

    destination, rows, config = client.loads[0]
    assert destination == "p.bara.eval_reignition"
    assert config.write_disposition == "WRITE_APPEND"
    assert [(row["model"], row["split"]) for row in rows] == [
        ("reignition_v1", "valid"),
        ("detection_days_baseline", "valid"),
        ("reignition_v1", "test"),
        ("detection_days_baseline", "test"),
        ("reignition_v1_no_rain_after", "valid"),
        ("reignition_v1_no_rain_after", "test"),
    ]
    assert rows[0]["auc"] == 0.7
    assert rows[0]["global_explain"] == [
        {"feature": "detection_days", "attribution": 0.3}
    ]
    assert rows[0]["evaluated_at"] == NOW.isoformat()
    assert rows[1]["auc"] == 1.0
    assert summary["bytes_billed"] == 10_485_760 * 12


def test_the_evaluation_sets_are_the_labeled_rows_of_the_split():
    _, client = run()

    evaluate_sql, evaluate_config = next(
        (sql, config) for sql, config in client.queries if "ML.EVALUATE" in sql
    )
    assert "split = @split AND reignited IS NOT NULL" in evaluate_sql
    params = {p.name: p.value for p in evaluate_config.query_parameters}
    assert params == {"region": "riau", "split": "valid"}


def test_no_labeled_events_in_a_split_is_a_job_error():
    with pytest.raises(JobError, match="no labeled events"):
        run(responses={**RESPONSES, "ML.PREDICT": []})


def test_ml_evaluate_without_a_row_is_a_job_error():
    with pytest.raises(JobError, match="ML.EVALUATE"):
        run(responses={**RESPONSES, "ML.EVALUATE": []})
