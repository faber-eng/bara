import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import get_args

import pytest
from pydantic import BaseModel, TypeAdapter, ValidationError

from contracts import (
    Bulletin,
    CaseDetail,
    CaseStatus,
    CaseSummary,
    CellFacts,
    ClockState,
    Escalation,
    Health,
    Inbox,
    PublicSummary,
    Rankings,
    TileLayer,
)

FIXTURES_DIR = Path(__file__).resolve().parents[3] / "data" / "fixtures"

FIXTURE_MODELS: dict[str, type[BaseModel]] = {
    "rankings.json": Rankings,
    "rankings_riau_200.json": Rankings,
    "cell_facts.json": CellFacts,
    "case_detail.json": CaseDetail,
    "escalation.json": Escalation,
    "public_summary.json": PublicSummary,
    "bulletin.json": Bulletin,
    "health.json": Health,
    "clock.json": ClockState,
    "tiles_drying.json": TileLayer,
    "inbox.json": Inbox,
}

LIST_FIXTURE_MODELS: dict[str, type[BaseModel]] = {
    "cases.json": CaseSummary,
}


def load_fixture(name: str) -> dict:
    return json.loads((FIXTURES_DIR / name).read_text())


def top_level_keys() -> list[tuple[str, str]]:
    return [(name, key) for name in FIXTURE_MODELS for key in load_fixture(name)]


def renamed(document: dict, key: str) -> dict:
    copy = dict(document)
    copy[f"{key}_renamed"] = copy.pop(key)
    return copy


def test_every_fixture_file_has_a_contract():
    on_disk = {path.name for path in FIXTURES_DIR.glob("*.json")}

    assert on_disk == set(FIXTURE_MODELS) | set(LIST_FIXTURE_MODELS)


@pytest.mark.parametrize("name", FIXTURE_MODELS)
def test_fixture_validates_against_its_contract(name):
    FIXTURE_MODELS[name].model_validate(load_fixture(name))


@pytest.mark.parametrize(("name", "key"), top_level_keys())
def test_renaming_a_top_level_key_fails(name, key):
    with pytest.raises(ValidationError):
        FIXTURE_MODELS[name].model_validate(renamed(load_fixture(name), key))


def test_renaming_a_nested_task_field_fails():
    case_detail = load_fixture("case_detail.json")
    case_detail["tasks"][0] = renamed(case_detail["tasks"][0], "deadline_at")

    with pytest.raises(ValidationError):
        CaseDetail.model_validate(case_detail)


@pytest.mark.parametrize("name", LIST_FIXTURE_MODELS)
def test_list_fixture_validates_against_its_contract(name):
    TypeAdapter(list[LIST_FIXTURE_MODELS[name]]).validate_python(load_fixture(name))


def test_renaming_a_case_summary_key_fails():
    cases = load_fixture("cases.json")
    cases[0] = renamed(cases[0], "task_status")

    with pytest.raises(ValidationError):
        TypeAdapter(list[CaseSummary]).validate_python(cases)


def test_cases_fixture_covers_every_case_status():
    statuses = {entry["case"]["status"] for entry in load_fixture("cases.json")}

    assert statuses == set(get_args(CaseStatus))


def test_cases_fixture_deadlines_are_relative_to_the_clock_fixture():
    now = datetime.fromisoformat(load_fixture("clock.json")["now"])
    cases = TypeAdapter(list[CaseSummary]).validate_python(load_fixture("cases.json"))
    gaps = [entry.next_deadline_at - now for entry in cases if entry.next_deadline_at]

    assert timedelta(days=3, hours=9) in gaps
    assert any(timedelta(0) < gap < timedelta(hours=1) for gap in gaps)
    assert timedelta(hours=-2) in gaps
    assert any(entry.next_deadline_at is None for entry in cases)


def test_riau_rankings_fixture_has_200_strictly_ranked_cells_and_50_dams():
    rankings = Rankings.model_validate(load_fixture("rankings_riau_200.json"))
    scores = [cell.drying_score for cell in rankings.cells]

    assert [cell.rank for cell in rankings.cells] == list(range(1, 201))
    assert scores == sorted(set(scores), reverse=True)
    assert len(rankings.dams) == 50


def test_riau_rankings_fixture_mixes_missing_and_present_values():
    cells = Rankings.model_validate(load_fixture("rankings_riau_200.json")).cells

    assert any(cell.rank_change is None for cell in cells)
    assert any(cell.explanation is None for cell in cells)
    assert any(cell.explanation is not None for cell in cells)
    assert any(cell.stale_s1 and cell.components.s1_anom_db is None for cell in cells)
