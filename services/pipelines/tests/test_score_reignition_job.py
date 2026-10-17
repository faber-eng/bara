import json
from datetime import UTC, date, datetime

import pytest

from adapters.bigquery import Warehouse
from adapters.events import EventPublisher
from ee_lib.config import load_data_config
from jobs import score_reignition as job
from jobs.cli import JobError, UsageError
from tests.fakes import FakePubSub, RecordingBigQueryClient

TODAY = date(2026, 8, 12)
NOW = datetime(2026, 8, 12, 1, 0, tzinfo=UTC)
SINCE = date(2026, 6, 13)


def prediction(cell_id, quiet, p):
    return {
        "event_id": f"{cell_id}-{quiet:%Y%m%d}",
        "cell_id": cell_id,
        "region": "riau",
        "quiet_date": quiet,
        "p_reignite": p,
        "top_feature_attributions": [
            {"feature": "mean_confidence", "attribution": -0.3},
            {"feature": "month", "attribution": 0.1},
        ],
    }


PREDICTIONS = [
    prediction("riau-1-1", date(2026, 8, 10), 0.4),
    prediction("riau-1-2", date(2026, 8, 10), 0.9),
    prediction("riau-1-3", date(2026, 8, 10), 0.7),
    prediction("riau-1-4", date(2026, 8, 10), 0.6),
    prediction("riau-2-1", date(2026, 7, 1), 0.8),
]


def run(*, only=None, example=False, dry_run=False, rows=PREDICTIONS):
    client = RecordingBigQueryClient(responses={"ML.EXPLAIN_PREDICT": rows})
    pubsub = FakePubSub()
    summary = job.score_reignition(
        region_id="riau",
        since=SINCE,
        today=TODAY,
        only=only,
        example=example,
        spots=3,
        warehouse=Warehouse(client, project="p", dataset="bara"),
        publisher=EventPublisher(pubsub, "p"),
        now=NOW,
        new_id=lambda: "env-1",
        dry_run=dry_run,
    )
    return summary, client, pubsub


def published(pubsub):
    return [json.loads(data) for _, data, _ in pubsub.published]


def test_scores_with_the_served_model_and_top_three_explanations():
    _, client, _ = run()

    sql, config = client.queries[0]
    assert "ML.EXPLAIN_PREDICT" in sql
    assert "MODEL `p.bara.reignition_v1_no_rain_after`" in sql
    assert "STRUCT(3 AS top_k_features)" in sql
    assert "IF(predicted_reignited = 1, probability, 1 - probability)" in sql
    params = {p.name: p.value for p in config.query_parameters}
    assert params == {"region": "riau", "since": SINCE}


def test_rewrites_the_scores_since_the_day():
    _, client, _ = run()

    destination, rows, _ = client.loads[0]
    assert destination == "p.bara.reignition_scores_staging"
    assert rows[1] == {
        "event_id": "riau-1-2-20260810",
        "cell_id": "riau-1-2",
        "region": "riau",
        "quiet_date": "2026-08-10",
        "model": "reignition_v1_no_rain_after",
        "p_reignite": 0.9,
        "top_features": [
            {"feature": "mean_confidence", "attribution": -0.3},
            {"feature": "month", "attribution": 0.1},
        ],
        "scored_at": NOW.isoformat(),
    }
    sql, _ = client.queries[-1]
    assert "DELETE FROM reignition_scores WHERE region = @region" in sql
    assert "AND quiet_date >= @since" in sql


def test_publishes_fire_quiet_with_the_three_most_likely_cells_of_a_recent_fire():
    summary, _, pubsub = run()

    events = published(pubsub)
    assert len(events) == 1
    event = events[0]
    assert event["type"] == "fire.quiet"
    assert event["example"] is False
    assert event["payload"]["event_id"] == "fire-riau-20260810"
    assert [cell["cell_id"] for cell in event["payload"]["cells"]] == [
        "riau-1-2",
        "riau-1-3",
        "riau-1-4",
    ]
    assert event["payload"]["cells"][0]["p_reignite"] == 0.9
    assert event["payload"]["cells"][0]["top_features"][0] == {
        "feature": "mean_confidence",
        "attribution": -0.3,
    }
    assert summary["published"] == [
        {"event_id": "fire-riau-20260810", "message_id": "msg-1"}
    ]


def test_a_quiet_date_publishes_only_that_fire_as_example_data():
    _, _, pubsub = run(only=date(2026, 7, 1), example=True)

    events = published(pubsub)
    assert [event["payload"]["event_id"] for event in events] == ["fire-riau-20260701"]
    assert events[0]["example"] is True


def test_a_quiet_date_without_a_fire_is_a_job_error():
    with pytest.raises(JobError, match="2026-07-02"):
        run(only=date(2026, 7, 2))


def test_dry_run_writes_and_publishes_nothing():
    summary, client, pubsub = run(dry_run=True)

    assert client.loads == []
    assert pubsub.published == []
    assert summary["fires"][0]["event_id"] == "fire-riau-20260810"


def test_a_malformed_prediction_is_a_job_error():
    with pytest.raises(JobError, match="malformed"):
        run(rows=[{**PREDICTIONS[0], "p_reignite": None}])


def test_since_reaches_back_to_the_quiet_date_asked_for(config_dir):
    data = load_data_config(config_dir)

    assert job.resolve_since(False, 60, TODAY, data, None) == SINCE
    assert job.resolve_since(False, 60, TODAY, data, date(2026, 1, 5)) == date(
        2026, 1, 5
    )
    assert job.resolve_since(True, 60, TODAY, data, None) == date(2015, 1, 1)
    with pytest.raises(UsageError):
        job.resolve_since(False, 0, TODAY, data, None)
