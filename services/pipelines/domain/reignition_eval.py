import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime

TOP_SHARE = 0.10
BASELINE_MODEL = "detection_days_baseline"
BASELINE_SCORE = "detection_days"
MODEL_SCORE = "p_reignite"
EVAL_SPLITS = ("valid", "test")


class EmptyRanking(ValueError):
    pass


@dataclass(frozen=True)
class ModelVariant:
    name: str
    dropped: tuple[str, ...]
    vertex_model_id: str | None


VARIANTS = (
    ModelVariant("reignition_v1", (), "bara_reignition"),
    ModelVariant(
        "reignition_v1_no_rain_after",
        ("rain_7d_after_mm",),
        "bara_reignition_no_rain_after",
    ),
)


@dataclass(frozen=True)
class Scored:
    event_id: str
    score: float
    label: int


@dataclass(frozen=True)
class RankingMetrics:
    events: int
    positives: int
    auc: float | None
    precision_top10: float
    recall_top10: float


@dataclass(frozen=True)
class Attribution:
    feature: str
    attribution: float


@dataclass(frozen=True)
class EvalRecord:
    evaluated_at: datetime
    region: str
    model: str
    split: str
    events: int
    positives: int
    auc: float | None
    auc_source: str
    precision_top10: float
    recall_top10: float
    log_loss: float | None
    global_explain: tuple[Attribution, ...]


def rank_auc(items: Sequence[Scored]) -> float | None:
    positives = [item.score for item in items if item.label == 1]
    negatives = [item.score for item in items if item.label == 0]
    if not positives or not negatives:
        return None
    wins = 0.0
    for positive in positives:
        for negative in negatives:
            if positive > negative:
                wins += 1.0
            elif positive == negative:
                wins += 0.5
    return wins / (len(positives) * len(negatives))


def top_count(events: int, share: float = TOP_SHARE) -> int:
    return max(1, math.ceil(events * share))


def ranked(items: Sequence[Scored]) -> list[Scored]:
    return sorted(items, key=lambda item: (-item.score, item.event_id))


def ranking_metrics(items: Sequence[Scored]) -> RankingMetrics:
    if not items:
        raise EmptyRanking("no labeled events to rank")
    positives = sum(item.label for item in items)
    top = ranked(items)[: top_count(len(items))]
    hits = sum(item.label for item in top)
    recall = 0.0
    if positives:
        recall = hits / positives
    return RankingMetrics(
        events=len(items),
        positives=positives,
        auc=rank_auc(items),
        precision_top10=hits / len(top),
        recall_top10=recall,
    )


def scored_rows(rows: Sequence[Mapping[str, object]], score: str) -> list[Scored]:
    return [
        Scored(
            event_id=str(row["event_id"]),
            score=float(row[score]),
            label=int(row["reignited"]),
        )
        for row in rows
    ]


def optional_metric(evaluation: Mapping[str, object], field: str) -> float | None:
    value = evaluation.get(field)
    if value is None:
        return None
    return float(value)


def attributions(explain: Sequence[Mapping[str, object]]) -> tuple[Attribution, ...]:
    return tuple(
        Attribution(feature=str(row["feature"]), attribution=float(row["attribution"]))
        for row in explain
    )


def model_record(
    *,
    variant: ModelVariant,
    region: str,
    split: str,
    evaluation: Mapping[str, object],
    predictions: Sequence[Mapping[str, object]],
    explain: Sequence[Mapping[str, object]],
    evaluated_at: datetime,
) -> EvalRecord:
    metrics = ranking_metrics(scored_rows(predictions, MODEL_SCORE))
    return EvalRecord(
        evaluated_at=evaluated_at,
        region=region,
        model=variant.name,
        split=split,
        events=metrics.events,
        positives=metrics.positives,
        auc=optional_metric(evaluation, "roc_auc"),
        auc_source="ml_evaluate",
        precision_top10=metrics.precision_top10,
        recall_top10=metrics.recall_top10,
        log_loss=optional_metric(evaluation, "log_loss"),
        global_explain=attributions(explain),
    )


def baseline_record(
    *,
    region: str,
    split: str,
    predictions: Sequence[Mapping[str, object]],
    evaluated_at: datetime,
) -> EvalRecord:
    metrics = ranking_metrics(scored_rows(predictions, BASELINE_SCORE))
    return EvalRecord(
        evaluated_at=evaluated_at,
        region=region,
        model=BASELINE_MODEL,
        split=split,
        events=metrics.events,
        positives=metrics.positives,
        auc=metrics.auc,
        auc_source="rank",
        precision_top10=metrics.precision_top10,
        recall_top10=metrics.recall_top10,
        log_loss=None,
        global_explain=(),
    )
