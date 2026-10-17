from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, timedelta

from domain.reignition_eval import BASELINE_MODEL, VARIANTS

TOP_SHARE = 0.10
FOLLOW_WEEKS = (1, 4)
DAYS_PER_WEEK = 7
QUOTED_SPLIT = "test"
METRIC_KEYS = ("auc", "precision_top10", "recall_top10")


@dataclass(frozen=True)
class WeekCapture:
    week_start: date
    cells: int
    hotspots: int
    captured: int


def follow_window(week_start: date) -> tuple[date, date]:
    first, last = FOLLOW_WEEKS
    return (
        week_start + timedelta(days=first * DAYS_PER_WEEK),
        week_start + timedelta(days=(last + 1) * DAYS_PER_WEEK),
    )


def complete_weeks(weeks: Sequence[WeekCapture], through: date) -> list[WeekCapture]:
    return [week for week in weeks if follow_window(week.week_start)[1] <= through]


def year_summary(year: int, weeks: Sequence[WeekCapture]) -> dict[str, object]:
    hotspots = sum(week.hotspots for week in weeks)
    captured = sum(week.captured for week in weeks)
    capture_rate = captured / hotspots if hotspots else None
    lift = capture_rate / TOP_SHARE if capture_rate is not None else None
    return {
        "year": year,
        "weeks": len(weeks),
        "hotspots": hotspots,
        "captured": captured,
        "capture_rate": capture_rate,
        "lift": lift,
    }


def model_metrics(row: Mapping[str, object]) -> dict[str, object]:
    return {"name": row["model"], **{key: row[key] for key in METRIC_KEYS}}


def newest_rows(rows: Sequence[Mapping[str, object]]) -> list[Mapping[str, object]]:
    quoted = [row for row in rows if row["split"] == QUOTED_SPLIT]
    if not quoted:
        raise ValueError(f"bara.eval_reignition has no {QUOTED_SPLIT} rows")
    newest = max(str(row["evaluated_at"]) for row in quoted)
    return [row for row in quoted if str(row["evaluated_at"]) == newest]


def reignition_summary(
    region: str, rows: Sequence[Mapping[str, object]]
) -> dict[str, object]:
    by_model = {str(row["model"]): row for row in newest_rows(rows)}
    trained, served = (variant.name for variant in VARIANTS)
    missing = [
        name for name in (trained, served, BASELINE_MODEL) if name not in by_model
    ]
    if missing:
        raise ValueError(f"the newest evaluation has no rows for {', '.join(missing)}")
    first = by_model[trained]
    return {
        "run_at": str(first["evaluated_at"]),
        "region": region,
        "split": QUOTED_SPLIT,
        "events": first["events"],
        "positives": first["positives"],
        "model": model_metrics(first),
        "served": model_metrics(by_model[served]),
        "baseline": model_metrics(by_model[BASELINE_MODEL]),
    }
