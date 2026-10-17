from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, timedelta

from domain.drying import optional_number
from ee_lib.config import SplitYears
from ee_lib.weeks import DateRange, EventWindows

RAIN_BEFORE_SHORT_DAYS = 7
RAIN_BEFORE_LONG_DAYS = 14
RAIN_AFTER_DAYS = 7


class MissingMeasurement(ValueError):
    pass


@dataclass(frozen=True)
class TrainingRow:
    event_id: str
    cell_id: str
    region: str
    quiet_date: date
    split: str
    reignited: int | None
    peat_class: int
    peat_fraction: float
    canal_dist_m: float
    s1_anom_db: float | None
    rain_7d_before_mm: float | None
    rain_14d_before_mm: float | None
    rain_7d_after_mm: float | None
    detection_days: int
    max_t21: float
    mean_confidence: float
    month: int
    prior_years_burned: int


def split_for(year: int, years: SplitYears) -> str | None:
    if years.train[0] <= year <= years.train[1]:
        return "train"
    if year == years.valid:
        return "valid"
    if year == years.test:
        return "test"
    return None


def covered(span: DateRange, chirps_last: date) -> DateRange | None:
    if span.end > chirps_last + timedelta(days=1):
        return None
    return span


def wet_baseline_year(quiet_date: date, wet_months: Sequence[int]) -> int:
    if quiet_date.month > max(wet_months):
        return quiet_date.year
    return quiet_date.year - 1


def event_windows(
    quiet_date: date, s1_days: int, chirps_last: date, wet_months: Sequence[int]
) -> EventWindows:
    def before(days: int) -> DateRange:
        return DateRange(quiet_date - timedelta(days=days), quiet_date)

    after = DateRange(quiet_date, quiet_date + timedelta(days=RAIN_AFTER_DAYS))
    return EventWindows(
        s1=before(s1_days),
        rain_7d_before=covered(before(RAIN_BEFORE_SHORT_DAYS), chirps_last),
        rain_14d_before=covered(before(RAIN_BEFORE_LONG_DAYS), chirps_last),
        rain_7d_after=covered(after, chirps_last),
        s1_baseline_year=wet_baseline_year(quiet_date, wet_months),
    )


def measure_key(cell_id: str, quiet_date: date) -> tuple[str, str]:
    return cell_id, quiet_date.isoformat()


def index_measures(
    measures: Sequence[Mapping[str, object]],
) -> dict[tuple[str, str], Mapping[str, object]]:
    return {
        (str(measure["cell_id"]), str(measure["quiet_date"])): measure
        for measure in measures
    }


def event_quiet_date(event: Mapping[str, object]) -> date:
    quiet_date = event["quiet_date"]
    if not isinstance(quiet_date, date):
        raise MissingMeasurement(f"event {event['event_id']!r} has no quiet_date")
    return quiet_date


def event_start_date(event: Mapping[str, object]) -> date:
    start_date = event["start_date"]
    if not isinstance(start_date, date):
        raise MissingMeasurement(f"event {event['event_id']!r} has no start_date")
    return start_date


def prior_years_burned(
    burned_years: Sequence[object], start_year: int, history_from_year: int
) -> int:
    years = {year for year in burned_years if isinstance(year, int)}
    return sum(1 for year in years if history_from_year <= year < start_year)


def burned_years_of(event: Mapping[str, object]) -> Sequence[object]:
    years = event["burned_years"]
    if years is None:
        return []
    if not isinstance(years, Sequence):
        raise MissingMeasurement(f"event {event['event_id']!r} has no burned_years")
    return years


def training_row(
    event: Mapping[str, object],
    quiet_date: date,
    measure: Mapping[str, object],
    peat_fraction: float,
    split: str,
    history_from_year: int,
) -> TrainingRow:
    return TrainingRow(
        event_id=str(event["event_id"]),
        cell_id=str(event["cell_id"]),
        region=str(event["region"]),
        quiet_date=quiet_date,
        split=split,
        reignited=event["reignited"],
        peat_class=int(event["peat_class"]),
        peat_fraction=peat_fraction,
        canal_dist_m=float(event["canal_dist_m"]),
        s1_anom_db=optional_number(measure, "s1_anom_db"),
        rain_7d_before_mm=optional_number(measure, "rain_7d_before_mm"),
        rain_14d_before_mm=optional_number(measure, "rain_14d_before_mm"),
        rain_7d_after_mm=optional_number(measure, "rain_7d_after_mm"),
        detection_days=int(event["detection_days"]),
        max_t21=float(event["max_t21"]),
        mean_confidence=float(event["mean_confidence"]),
        month=quiet_date.month,
        prior_years_burned=prior_years_burned(
            burned_years_of(event), event_start_date(event).year, history_from_year
        ),
    )


def training_rows(
    events: Sequence[Mapping[str, object]],
    measures: Sequence[Mapping[str, object]],
    peat_fractions: Mapping[str, float],
    years: SplitYears,
    history_from_year: int,
) -> list[TrainingRow]:
    by_key = index_measures(measures)
    rows: list[TrainingRow] = []
    for event in events:
        quiet_date = event_quiet_date(event)
        split = split_for(quiet_date.year, years)
        if split is None:
            continue
        cell_id = str(event["cell_id"])
        measure = by_key.get(measure_key(cell_id, quiet_date))
        if measure is None:
            raise MissingMeasurement(f"no Earth Engine measure for {event['event_id']}")
        if cell_id not in peat_fractions:
            raise MissingMeasurement(f"no peat_fraction for {cell_id}")
        rows.append(
            training_row(
                event,
                quiet_date,
                measure,
                peat_fractions[cell_id],
                split,
                history_from_year,
            )
        )
    return rows


def cells_by_date(events: Sequence[Mapping[str, object]]) -> dict[date, list[str]]:
    dates: dict[date, list[str]] = {}
    for event in events:
        dates.setdefault(event_quiet_date(event), []).append(str(event["cell_id"]))
    return dates
