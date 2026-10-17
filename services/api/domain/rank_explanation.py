import math
import re
from collections.abc import Mapping
from dataclasses import dataclass

from contracts import RankExplanation

EXPLAIN_PROMPT_VERSION = "explain-v2"
METRES_PER_KM = 1000
NUMBER = re.compile(r"(?<![\w.-])-?\d+(?:\.\d+)?(?![\w])")
EXACT_TOLERANCE = 1e-9

FIELDS = (
    "drying_score",
    "rank",
    "s1_anom_db",
    "rain_30d_mm",
    "rain_deficit_pct",
    "canal_dist_m",
    "peat_class",
)


FIELD_WORDS = {
    "drying_score": "drying score",
    "rank": "rank this week",
    "s1_anom_db": "radar dryness signal",
    "rain_30d_mm": "rainfall over the past month",
    "rain_deficit_pct": "rain deficit",
    "canal_dist_m": "distance to the nearest canal",
    "peat_class": "peat class",
}


class ExplanationRejected(Exception):
    pass


@dataclass(frozen=True)
class Shown:
    number: float
    written: str


def known_values(facts: Mapping[str, object]) -> dict[str, float]:
    components = facts["components"]
    candidates = {
        "drying_score": facts["drying_score"],
        "rank": facts["rank"],
        **{key: components[key] for key in FIELDS[2:]},
    }
    return {key: value for key, value in candidates.items() if value is not None}


def is_current(explanation: RankExplanation | None) -> bool:
    if explanation is None:
        return False
    return explanation.prompt_version == EXPLAIN_PROMPT_VERSION


def shown_decimal(value: float, unit: str) -> Shown:
    number = round(value, 1)
    return Shown(number, f"{number:.1f}{unit}")


def shown_whole(value: float, unit: str) -> Shown:
    number = round(value)
    return Shown(number, f"{number}{unit}")


def shown_distance(metres: float) -> Shown:
    if metres < METRES_PER_KM:
        return shown_whole(metres, " m")
    return shown_decimal(metres / METRES_PER_KM, " km")


def shown_score(value: float) -> Shown:
    return shown_decimal(value, "")


def shown_count(value: float) -> Shown:
    return shown_whole(value, "")


def shown_decibels(value: float) -> Shown:
    return shown_decimal(value, " dB")


def shown_millimetres(value: float) -> Shown:
    return shown_whole(value, " mm")


def shown_percent(fraction: float) -> Shown:
    return shown_whole(fraction * 100, "%")


SHOWERS = {
    "drying_score": shown_score,
    "rank": shown_count,
    "s1_anom_db": shown_decibels,
    "rain_30d_mm": shown_millimetres,
    "rain_deficit_pct": shown_percent,
    "canal_dist_m": shown_distance,
    "peat_class": shown_count,
}


def shown_values(values: Mapping[str, float]) -> dict[str, Shown]:
    return {field: SHOWERS[field](value) for field, value in values.items()}


def shown_numbers(values: Mapping[str, float]) -> dict[str, float]:
    return {field: shown.number for field, shown in shown_values(values).items()}


def matches_value(token: str, value: float) -> bool:
    return math.isclose(float(token), value, rel_tol=0, abs_tol=EXACT_TOLERANCE)


def numbers_in(text: str, cell_id: str) -> list[str]:
    return NUMBER.findall(text.replace(cell_id, " "))


def check_cited(cited: Mapping[str, float], facts: Mapping[str, float]) -> None:
    if not cited:
        raise ExplanationRejected("no cited numbers")
    for field, value in cited.items():
        if field not in facts:
            raise ExplanationRejected(f"cited field {field} is not a known field")
        if not math.isclose(value, facts[field], rel_tol=0, abs_tol=EXACT_TOLERANCE):
            raise ExplanationRejected(
                f"cited {field} is {value}, the data says {facts[field]}"
            )


def check_numbers(text: str, cited: Mapping[str, float], cell_id: str) -> None:
    tokens = numbers_in(text, cell_id)
    for token in tokens:
        if not any(matches_value(token, value) for value in cited.values()):
            raise ExplanationRejected(f"the text number {token} is not cited")
    for field, value in cited.items():
        if not any(matches_value(token, value) for token in tokens):
            raise ExplanationRejected(f"cited {field} does not appear in the text")


def check_explanation(
    text: str, cited: Mapping[str, float], facts: Mapping[str, float], cell_id: str
) -> None:
    check_cited(cited, facts)
    check_numbers(text, cited, cell_id)
