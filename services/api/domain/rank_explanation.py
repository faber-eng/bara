import math
import re
from collections.abc import Mapping

NUMBER = re.compile(r"-?\d+(?:\.\d+)?")
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


class ExplanationRejected(Exception):
    pass


def known_values(facts: Mapping[str, object]) -> dict[str, float]:
    components = facts["components"]
    candidates = {
        "drying_score": facts["drying_score"],
        "rank": facts["rank"],
        **{key: components[key] for key in FIELDS[2:]},
    }
    return {key: value for key, value in candidates.items() if value is not None}


def decimals(token: str) -> int:
    if "." not in token:
        return 0
    return len(token.split(".")[1])


def matches_value(token: str, value: float) -> bool:
    return round(value, decimals(token)) == float(token)


def numbers_in(text: str, cell_id: str) -> list[str]:
    return NUMBER.findall(text.replace(cell_id, ""))


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
