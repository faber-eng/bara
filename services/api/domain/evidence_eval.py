import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import PurePosixPath

from contracts import EvidenceKind, TaskType

FIELDS = ("subject", "dam_state", "smoke", "hot_ground_signs", "open_flame")
CONFUSION_FIELDS = ("dam_state", "smoke")
UNKNOWN = "unknown"
FAILED = "failed"
KIND_BY_SUFFIX: dict[str, EvidenceKind] = {
    ".jpg": "photo",
    ".jpeg": "photo",
    ".png": "photo",
    ".ogg": "audio",
    ".webm": "audio",
    ".mp3": "audio",
}
DAM_SUBJECT = "canal_dam"


@dataclass(frozen=True)
class LabelRow:
    file: str
    object_path: str
    labels: Mapping[str, str]


@dataclass(frozen=True)
class ScoredItem:
    row: LabelRow
    verdict: Mapping[str, str] | None
    latency_ms: float
    error: str | None


def kind_for(object_path: str) -> EvidenceKind:
    suffix = PurePosixPath(object_path).suffix.lower()
    kind = KIND_BY_SUFFIX.get(suffix)
    if kind is None:
        raise ValueError(f"{object_path} is not a photo or a voice note")
    return kind


def task_type_for(subject: str) -> TaskType:
    if subject == DAM_SUBJECT:
        return "dam_check"
    return "patrol_recheck"


def nearest_rank(values: Sequence[float], share: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = max(math.ceil(share * len(ordered)) - 1, 0)
    return ordered[index]


def predicted(item: ScoredItem, field: str) -> str:
    if item.verdict is None:
        return FAILED
    return item.verdict[field]


def scorable(items: Sequence[ScoredItem], field: str) -> list[ScoredItem]:
    return [item for item in items if item.row.labels[field] != UNKNOWN]


def field_accuracy(items: Sequence[ScoredItem], field: str) -> dict[str, object]:
    counted = scorable(items, field)
    correct = sum(
        1 for item in counted if predicted(item, field) == item.row.labels[field]
    )
    accuracy = correct / len(counted) if counted else None
    return {"field": field, "correct": correct, "n": len(counted), "accuracy": accuracy}


def accuracy_by_field(items: Sequence[ScoredItem]) -> list[dict[str, object]]:
    return [field_accuracy(items, field) for field in FIELDS]


def confusion(items: Sequence[ScoredItem], field: str) -> dict[str, object]:
    counted = scorable(items, field)
    pairs = [(item.row.labels[field], predicted(item, field)) for item in counted]
    labels = sorted({value for pair in pairs for value in pair})
    position = {value: index for index, value in enumerate(labels)}
    matrix = [[0] * len(labels) for _ in labels]
    for actual, guessed in pairs:
        matrix[position[actual]][position[guessed]] += 1
    return {"field": field, "labels": labels, "matrix": matrix}


def latency_summary(items: Sequence[ScoredItem]) -> dict[str, object]:
    timings = [item.latency_ms for item in items if item.error is None]
    return {
        "n": len(timings),
        "p50": nearest_rank(timings, 0.5),
        "p95": nearest_rank(timings, 0.95),
    }


def summarize_set(
    kind: EvidenceKind, prompt_version: str, items: Sequence[ScoredItem]
) -> dict[str, object]:
    return {
        "kind": kind,
        "prompt_version": prompt_version,
        "n": len(items),
        "failed": sum(1 for item in items if item.error is not None),
        "fields": accuracy_by_field(items),
        "confusion": [confusion(items, field) for field in CONFUSION_FIELDS],
        "latency_ms": latency_summary(items),
    }


def parse_label_row(raw: Mapping[str, str]) -> LabelRow:
    return LabelRow(
        file=raw["file"],
        object_path=raw["object_path"],
        labels={field: raw[field] for field in FIELDS},
    )


def verdict_value(item: ScoredItem, field: str) -> str | None:
    if item.verdict is None:
        return None
    return item.verdict[field]


def evidence_row(
    item: ScoredItem, run_at: str, model: str, prompt_version: str
) -> dict[str, object]:
    row: dict[str, object] = {
        "run_at": run_at,
        "file": item.row.file,
        "kind": kind_for(item.row.object_path),
        "model": model,
        "prompt_version": prompt_version,
        "latency_ms": item.latency_ms,
        "error": item.error,
    }
    for field in FIELDS:
        row[f"label_{field}"] = item.row.labels[field]
        row[f"verdict_{field}"] = verdict_value(item, field)
    return row
