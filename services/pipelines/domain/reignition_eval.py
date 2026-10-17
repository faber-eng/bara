import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime

TOP_SHARE = 0.10
BASELINE_MODEL = "detection_days_baseline"
BASELINE_SCORE = "detection_days"
MODEL_SCORE = "p_reignite"
EVAL_SPLITS = ("valid", "test")
KEY_COLUMNS = ("event_id", "cell_id", "region", "quiet_date", "split")


class EmptyRanking(ValueError):
    pass


@dataclass(frozen=True)
class ModelVariant:
    name: str
    dropped: tuple[str, ...]
    vertex_model_id: str | None
    with_baseline: bool


VARIANTS = (
    ModelVariant("reignition_v1", (), "bara_reignition", with_baseline=True),
    ModelVariant(
        "reignition_v1_no_rain_after",
        ("rain_7d_after_mm",),
        "bara_reignition_no_rain_after",
        with_baseline=False,
    ),
)


def feature_exclusions(variant: ModelVariant) -> tuple[str, ...]:
    return KEY_COLUMNS + variant.dropped


def labeled_count(labeled: Mapping[str, object], split: str) -> int:
    value = labeled.get(split)
    if value is None:
        return 0
    return int(str(value))


def empty_eval_splits(labeled: Mapping[str, object]) -> list[str]:
    return [split for split in EVAL_SPLITS if labeled_count(labeled, split) == 0]


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
    recall_top10: float | None


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
    ml_evaluate_auc: float | None
    precision_top10: float
    recall_top10: float | None
    log_loss: float | None
    global_explain: tuple[Attribution, ...]


def average_ranks(scores: Sequence[float]) -> list[float]:
    order = sorted(range(len(scores)), key=lambda index: scores[index])
    ranks = [0.0] * len(scores)
    start = 0
    while start < len(order):
        end = start
        while end + 1 < len(order) and scores[order[end + 1]] == scores[order[start]]:
            end += 1
        average = (start + end) / 2 + 1
        for position in range(start, end + 1):
            ranks[order[position]] = average
        start = end + 1
    return ranks


def rank_auc(items: Sequence[Scored]) -> float | None:
    positives = sum(item.label for item in items)
    negatives = len(items) - positives
    if positives == 0 or negatives == 0:
        return None
    ranks = average_ranks([item.score for item in items])
    positive_rank_sum = sum(
        rank for rank, item in zip(ranks, items, strict=True) if item.label == 1
    )
    wins = positive_rank_sum - positives * (positives + 1) / 2
    return wins / (positives * negatives)


def top_count(events: int, share: float = TOP_SHARE) -> int:
    return max(1, math.ceil(events * share))


def expected_top_hits(items: Sequence[Scored], top: int) -> float:
    cut = sorted((item.score for item in items), reverse=True)[top - 1]
    above = [item for item in items if item.score > cut]
    tied = [item for item in items if item.score == cut]
    slots = top - len(above)
    tied_positives = sum(item.label for item in tied)
    return sum(item.label for item in above) + slots * tied_positives / len(tied)


def recall_or_none(hits: float, positives: int) -> float | None:
    if positives == 0:
        return None
    return hits / positives


def ranking_metrics(items: Sequence[Scored]) -> RankingMetrics:
    if not items:
        raise EmptyRanking("no labeled events to rank")
    positives = sum(item.label for item in items)
    top = top_count(len(items))
    hits = expected_top_hits(items, top)
    return RankingMetrics(
        events=len(items),
        positives=positives,
        auc=rank_auc(items),
        precision_top10=hits / top,
        recall_top10=recall_or_none(hits, positives),
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
        auc=metrics.auc,
        ml_evaluate_auc=optional_metric(evaluation, "roc_auc"),
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
        ml_evaluate_auc=None,
        precision_top10=metrics.precision_top10,
        recall_top10=metrics.recall_top10,
        log_loss=None,
        global_explain=(),
    )
