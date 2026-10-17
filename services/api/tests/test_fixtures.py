import json
from pathlib import Path

import pytest
from pydantic import BaseModel, ValidationError

from contracts import (
    Bulletin,
    CaseDetail,
    CellFacts,
    Escalation,
    Health,
    PublicSummary,
    Rankings,
)

FIXTURES_DIR = Path(__file__).resolve().parents[3] / "data" / "fixtures"

FIXTURE_MODELS: dict[str, type[BaseModel]] = {
    "rankings.json": Rankings,
    "cell_facts.json": CellFacts,
    "case_detail.json": CaseDetail,
    "escalation.json": Escalation,
    "public_summary.json": PublicSummary,
    "bulletin.json": Bulletin,
    "health.json": Health,
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

    assert on_disk == set(FIXTURE_MODELS)


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
