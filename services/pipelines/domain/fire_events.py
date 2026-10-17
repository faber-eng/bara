from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, timedelta


class InvalidSighting(ValueError):
    pass


class InvalidDetection(ValueError):
    pass


@dataclass(frozen=True)
class Detection:
    detect_date: date
    lon: float
    lat: float
    t21: float
    confidence: float


@dataclass(frozen=True)
class Sighting:
    cell_id: str
    day: date
    inside: bool
    t21: float
    confidence: float


@dataclass(frozen=True)
class EventRules:
    quiet_days: int
    label_window_days: tuple[int, int]
    first_year: int
    last_year: int


@dataclass(frozen=True)
class FireEvent:
    event_id: str
    cell_id: str
    region: str
    start_date: date
    last_detection_date: date
    quiet_date: date
    detection_days: int
    max_t21: float
    mean_confidence: float
    reignited: int | None


def detection(feature: Mapping[str, object]) -> Detection:
    try:
        lon, lat = feature["geometry"]["coordinates"]
        properties = feature["properties"]
        return Detection(
            detect_date=date.fromisoformat(properties["detect_date"]),
            lon=float(lon),
            lat=float(lat),
            t21=float(properties["T21"]),
            confidence=float(properties["confidence"]),
        )
    except (KeyError, TypeError, ValueError) as error:
        raise InvalidDetection(f"FIRMS feature is malformed: {error}") from error


def sighting(row: Mapping[str, object]) -> Sighting:
    day = row.get("detect_date")
    if not isinstance(day, date):
        raise InvalidSighting(f"row for {row.get('cell_id')!r} has no detect_date")
    return Sighting(
        cell_id=str(row["cell_id"]),
        day=day,
        inside=bool(row["inside"]),
        t21=float(row["t21"]),
        confidence=float(row["confidence"]),
    )


def by_cell(sightings: Iterable[Sighting]) -> dict[str, list[Sighting]]:
    cells: dict[str, list[Sighting]] = defaultdict(list)
    for item in sightings:
        cells[item.cell_id].append(item)
    return cells


def detection_buffer_m(label_radius_m: int, grid_cell_m: int) -> int:
    return label_radius_m + grid_cell_m


def day_runs(days: Sequence[date], quiet_days: int) -> list[list[date]]:
    runs: list[list[date]] = []
    for day in days:
        if runs and (day - runs[-1][-1]).days <= quiet_days:
            runs[-1].append(day)
        else:
            runs.append([day])
    return runs


def reignition_label(
    quiet_date: date,
    near_days: Sequence[date],
    window: tuple[int, int],
    observed_until: date,
) -> int | None:
    first = quiet_date + timedelta(days=window[0])
    last = quiet_date + timedelta(days=window[1])
    if last > observed_until:
        return None
    if any(first <= day <= last for day in near_days):
        return 1
    return 0


def run_event(
    region: str,
    cell_id: str,
    run: list[date],
    inside: list[Sighting],
    near_days: Sequence[date],
    rules: EventRules,
    observed_until: date,
) -> FireEvent | None:
    own = [item for item in inside if run[0] <= item.day <= run[-1]]
    if not own:
        return None
    quiet_date = run[-1] + timedelta(days=rules.quiet_days)
    if quiet_date > observed_until:
        return None
    if not rules.first_year <= quiet_date.year <= rules.last_year:
        return None
    start = min(item.day for item in own)
    return FireEvent(
        event_id=f"{cell_id}-{start:%Y%m%d}",
        cell_id=cell_id,
        region=region,
        start_date=start,
        last_detection_date=max(item.day for item in own),
        quiet_date=quiet_date,
        detection_days=len({item.day for item in own}),
        max_t21=max(item.t21 for item in own),
        mean_confidence=sum(item.confidence for item in own) / len(own),
        reignited=reignition_label(
            quiet_date, near_days, rules.label_window_days, observed_until
        ),
    )


def cell_events(
    region: str,
    cell_id: str,
    sightings: list[Sighting],
    rules: EventRules,
    observed_until: date,
) -> list[FireEvent]:
    near_days = sorted({item.day for item in sightings})
    inside = [item for item in sightings if item.inside]
    events = (
        run_event(region, cell_id, run, inside, near_days, rules, observed_until)
        for run in day_runs(near_days, rules.quiet_days)
    )
    return [event for event in events if event is not None]


def build_events(
    region: str,
    sightings: Iterable[Sighting],
    rules: EventRules,
    observed_until: date,
) -> list[FireEvent]:
    events: list[FireEvent] = []
    for cell_id, cell_sightings in sorted(by_cell(sightings).items()):
        events.extend(
            cell_events(region, cell_id, cell_sightings, rules, observed_until)
        )
    return events
