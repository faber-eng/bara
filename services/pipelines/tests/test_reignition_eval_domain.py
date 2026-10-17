from datetime import UTC, datetime

import pytest

from domain.reignition_eval import (
    BASELINE_MODEL,
    VARIANTS,
    EmptyRanking,
    Scored,
    baseline_record,
    empty_eval_splits,
    feature_exclusions,
    model_record,
    rank_auc,
    ranking_metrics,
    scored_rows,
    top_count,
)

NOW = datetime(2026, 10, 18, 1, 0, tzinfo=UTC)


def scored(*pairs):
    return [
        Scored(f"e{index}", score, label) for index, (score, label) in enumerate(pairs)
    ]


def test_auc_is_one_when_every_positive_outranks_every_negative():
    assert rank_auc(scored((0.9, 1), (0.8, 1), (0.2, 0), (0.1, 0))) == 1.0


def test_auc_counts_a_tie_as_half():
    assert rank_auc(scored((0.5, 1), (0.5, 0))) == 0.5


def test_auc_is_none_without_both_classes():
    assert rank_auc(scored((0.9, 1), (0.8, 1))) is None


@pytest.mark.parametrize(("events", "top"), [(1, 1), (10, 1), (11, 2), (118, 12)])
def test_top_ten_percent_rounds_up_and_keeps_at_least_one(events, top):
    assert top_count(events) == top


def test_precision_and_recall_at_the_top_ten_percent():
    items = scored(
        (0.95, 1),
        (0.9, 0),
        (0.8, 1),
        (0.7, 0),
        (0.6, 0),
        (0.5, 0),
        (0.4, 1),
        (0.3, 0),
        (0.2, 0),
        (0.1, 0),
        (0.05, 0),
    )

    metrics = ranking_metrics(items)

    assert metrics.events == 11
    assert metrics.positives == 3
    assert metrics.precision_top10 == 0.5
    assert metrics.recall_top10 == pytest.approx(1 / 3)


def test_ties_at_the_cut_share_the_remaining_slots():
    items = [Scored("b", 1.0, 0), Scored("a", 1.0, 1)] + scored(*[(0.0, 0)] * 8)

    metrics = ranking_metrics(items)

    assert metrics.precision_top10 == 0.5
    assert metrics.recall_top10 == 0.5


def test_tie_sharing_does_not_depend_on_event_ids():
    first = [Scored("a", 1.0, 0), Scored("b", 1.0, 1)] + scored(*[(0.0, 0)] * 8)
    second = [Scored("a", 1.0, 1), Scored("b", 1.0, 0)] + scored(*[(0.0, 0)] * 8)

    assert ranking_metrics(first) == ranking_metrics(second)


def test_recall_is_none_without_positives():
    assert ranking_metrics(scored((0.9, 0), (0.1, 0))).recall_top10 is None


def test_auc_with_ties_matches_the_pairwise_count():
    items = scored((0.9, 1), (0.5, 1), (0.5, 0), (0.5, 0), (0.1, 1), (0.1, 0))

    assert rank_auc(items) == pytest.approx(5.5 / 9)


def test_no_events_is_an_error():
    with pytest.raises(EmptyRanking):
        ranking_metrics([])


PREDICTIONS = [
    {"event_id": "a", "reignited": 1, "detection_days": 9, "p_reignite": 0.9},
    {"event_id": "b", "reignited": 0, "detection_days": 1, "p_reignite": 0.2},
    {"event_id": "c", "reignited": 0, "detection_days": 3, "p_reignite": 0.4},
]


def test_scored_rows_read_the_named_score_and_the_label():
    items = scored_rows(PREDICTIONS, "detection_days")

    assert items[0] == Scored("a", 9.0, 1)


def test_both_variants_register_to_vertex_and_one_drops_rain_after():
    full, without_after = VARIANTS

    assert full.name == "reignition_v1"
    assert full.dropped == ()
    assert full.vertex_model_id == "bara_reignition"
    assert without_after.dropped == ("rain_7d_after_mm",)
    assert without_after.vertex_model_id == "bara_reignition_no_rain_after"


def test_only_the_full_variant_writes_the_baseline():
    full, without_after = VARIANTS

    assert full.with_baseline is True
    assert without_after.with_baseline is False


def test_keys_and_dropped_columns_are_never_features():
    assert feature_exclusions(VARIANTS[1]) == (
        "event_id",
        "cell_id",
        "region",
        "quiet_date",
        "split",
        "rain_7d_after_mm",
    )


def test_empty_eval_splits_names_each_split_without_labeled_events():
    assert empty_eval_splits({"valid": 117, "test": 0}) == ["test"]
    assert empty_eval_splits({"valid": 117, "test": 118}) == []


def test_a_model_record_ranks_by_p_reignite_and_keeps_the_ml_evaluate_auc():
    record = model_record(
        variant=VARIANTS[0],
        region="riau",
        split="test",
        evaluation={"roc_auc": 0.71, "log_loss": 0.55},
        predictions=PREDICTIONS,
        explain=[
            {"feature": "detection_days", "attribution": 0.3},
            {"feature": "month", "attribution": 0.1},
        ],
        evaluated_at=NOW,
    )

    assert record.model == "reignition_v1"
    assert record.auc == 1.0
    assert record.ml_evaluate_auc == 0.71
    assert record.log_loss == 0.55
    assert record.events == 3
    assert record.positives == 1
    assert record.precision_top10 == 1.0
    assert record.global_explain[0].feature == "detection_days"


def test_the_baseline_record_ranks_by_detection_days():
    record = baseline_record(
        region="riau", split="valid", predictions=PREDICTIONS, evaluated_at=NOW
    )

    assert record.model == BASELINE_MODEL
    assert record.auc == 1.0
    assert record.ml_evaluate_auc is None
    assert record.log_loss is None
    assert record.global_explain == ()
