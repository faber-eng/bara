from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime

from api_contracts import contracts

TOP_FEATURES = 3
SERVED_MODEL = "reignition_v1_no_rain_after"
PUBLISH_DAYS = 3


class InvalidScore(ValueError):
    pass


@dataclass(frozen=True)
class FeatureAttribution:
    feature: str
    attribution: float


@dataclass(frozen=True)
class EventScore:
    event_id: str
    cell_id: str
    region: str
    quiet_date: date
    p_reignite: float
    top_features: tuple[FeatureAttribution, ...]


@dataclass(frozen=True)
class Fire:
    event_id: str
    region: str
    quiet_date: date
    cells: tuple[EventScore, ...]


def attribution(item: Mapping[str, object]) -> FeatureAttribution:
    return FeatureAttribution(
        feature=str(item["feature"]), attribution=float(item["attribution"])
    )


def strongest(items: Sequence[FeatureAttribution]) -> tuple[FeatureAttribution, ...]:
    ordered = sorted(items, key=lambda item: (-abs(item.attribution), item.feature))
    return tuple(ordered[:TOP_FEATURES])


def probability(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise TypeError(f"p_reignite is not a number: {value!r}")
    if not 0.0 <= float(value) <= 1.0:
        raise ValueError(f"p_reignite {value} is outside 0 to 1")
    return float(value)


def event_score(row: Mapping[str, object]) -> EventScore:
    try:
        quiet_date = row["quiet_date"]
        if not isinstance(quiet_date, date):
            raise TypeError("quiet_date is not a date")
        return EventScore(
            event_id=str(row["event_id"]),
            cell_id=str(row["cell_id"]),
            region=str(row["region"]),
            quiet_date=quiet_date,
            p_reignite=probability(row["p_reignite"]),
            top_features=strongest(
                [attribution(item) for item in row["top_feature_attributions"]]
            ),
        )
    except (KeyError, TypeError, ValueError) as error:
        raise InvalidScore(f"prediction row is malformed: {error}") from error


def fire_event_id(region: str, quiet_date: date) -> str:
    return f"fire-{region}-{quiet_date:%Y%m%d}"


def group_fires(scores: Sequence[EventScore], spots: int) -> list[Fire]:
    by_date: dict[tuple[str, date], list[EventScore]] = {}
    for score in scores:
        by_date.setdefault((score.region, score.quiet_date), []).append(score)
    fires = []
    for (region, quiet_date), cells in sorted(by_date.items()):
        ranked = sorted(cells, key=lambda cell: (-cell.p_reignite, cell.cell_id))
        fires.append(
            Fire(
                event_id=fire_event_id(region, quiet_date),
                region=region,
                quiet_date=quiet_date,
                cells=tuple(ranked[:spots]),
            )
        )
    return fires


def fires_to_publish(
    fires: Sequence[Fire], since: date, only: date | None
) -> list[Fire]:
    if only is not None:
        return [fire for fire in fires if fire.quiet_date == only]
    return [fire for fire in fires if fire.quiet_date >= since]


def quiet_cell(score: EventScore) -> contracts.QuietCell:
    return contracts.QuietCell(
        cell_id=score.cell_id,
        p_reignite=score.p_reignite,
        top_features=[
            contracts.TopFeature(feature=item.feature, attribution=item.attribution)
            for item in score.top_features
        ],
    )


def fire_quiet_event(
    fire: Fire, envelope_id: str, occurred_at: datetime, example: bool
) -> contracts.FireQuietEvent:
    return contracts.FireQuietEvent(
        id=envelope_id,
        occurred_at=occurred_at,
        region=fire.region,
        example=example,
        type="fire.quiet",
        payload=contracts.FireQuiet(
            event_id=fire.event_id, cells=[quiet_cell(cell) for cell in fire.cells]
        ),
    )
