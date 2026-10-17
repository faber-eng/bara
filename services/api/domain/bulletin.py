import math
import re
from collections.abc import Mapping, Sequence

from contracts import CitedValue, PublicSummary

BULLETIN_PROMPT_VERSION = "bulletin-v1"
TEMPLATE_PROMPT_VERSION = "bulletin-template-v1"
MAX_SENTENCES = 4
EXACT_TOLERANCE = 1e-9
NUMBER = re.compile(r"(?<![\w.-])-?\d+(?:[.,]\d+)?(?![\w])")

FIELDS = (
    "high_risk_cells",
    "dams_broken",
    "cases_open",
    "cases_escalated",
    "cases_closed",
    "median_days_to_repair",
    "tasks_on_time_pct",
)
FIELD_NAMES = {
    "high_risk_cells": ("high-risk cells", "sel berisiko tinggi", "cells"),
    "dams_broken": ("dams broken or damaged", "bendungan rusak", "dams"),
    "cases_open": ("open cases", "kasus terbuka", "cases"),
    "cases_escalated": ("escalated cases", "kasus dieskalasi", "cases"),
    "cases_closed": ("cases closed this week", "kasus ditutup minggu ini", "cases"),
    "median_days_to_repair": (
        "median days to repair a dam",
        "median hari untuk memperbaiki bendungan",
        "days",
    ),
    "tasks_on_time_pct": (
        "share of tasks done on time",
        "persentase tugas selesai tepat waktu",
        "percent",
    ),
}


class BulletinRejected(Exception):
    pass


def summary_values(summary: PublicSummary) -> dict[str, float]:
    values = {field: getattr(summary, field) for field in FIELDS}
    return {field: value for field, value in values.items() if value is not None}


def summary_facts(summary: PublicSummary) -> list[dict[str, object]]:
    facts = []
    for field, value in summary_values(summary).items():
        name_en, name_id, unit = FIELD_NAMES[field]
        facts.append(
            {
                "field": field,
                "name_en": name_en,
                "name_id": name_id,
                "unit": unit,
                "value": value,
            }
        )
    return facts


def numbers_in(text: str) -> list[float]:
    return [float(token.replace(",", ".")) for token in NUMBER.findall(text)]


def same_number(left: float, right: float) -> bool:
    return math.isclose(left, right, rel_tol=0, abs_tol=EXACT_TOLERANCE)


def check_cited(cited: Sequence[CitedValue], values: Mapping[str, float]) -> None:
    if not cited:
        raise BulletinRejected("no cited fields")
    seen = [item.field for item in cited]
    if len(set(seen)) != len(seen):
        raise BulletinRejected("a field is cited twice")
    for item in cited:
        if item.field not in values:
            raise BulletinRejected(f"cited field {item.field} is not in the summary")
        if not isinstance(item.value, int | float) or not same_number(
            item.value, values[item.field]
        ):
            raise BulletinRejected(
                f"cited {item.field} is {item.value}, the summary says {values[item.field]}"
            )


def check_text(language: str, text: str, cited: Sequence[CitedValue]) -> None:
    written = numbers_in(text)
    for number in written:
        if not any(same_number(number, item.value) for item in cited):
            raise BulletinRejected(
                f"the {language} text number {number:g} is not cited"
            )
    for item in cited:
        if not any(same_number(number, item.value) for number in written):
            raise BulletinRejected(
                f"cited {item.field} does not appear in the {language} text"
            )


def check_bulletin(
    text_id: str, text_en: str, cited: Sequence[CitedValue], summary: PublicSummary
) -> None:
    check_cited(cited, summary_values(summary))
    check_text("id", text_id, cited)
    check_text("en", text_en, cited)


def template_bulletin(
    summary: PublicSummary,
) -> tuple[str, str, list[CitedValue]]:
    region = summary.region.title()
    risk, broken = summary.high_risk_cells, summary.dams_broken
    opened, escalated = summary.cases_open, summary.cases_escalated
    closed = summary.cases_closed
    text_en = (
        f"This week in {region}, {risk} cells are at high risk and {broken} dams "
        f"are broken or damaged. {opened} cases are open, {escalated} are "
        f"escalated and {closed} are closed."
    )
    text_id = (
        f"Minggu ini di {region}, {risk} sel berisiko tinggi dan {broken} "
        f"bendungan rusak. {opened} kasus terbuka, {escalated} dieskalasi dan "
        f"{closed} ditutup."
    )
    cited = [
        CitedValue(field=field, value=getattr(summary, field))
        for field in (
            "high_risk_cells",
            "dams_broken",
            "cases_open",
            "cases_escalated",
            "cases_closed",
        )
    ]
    return text_id, text_en, cited
