from typing import get_args

from adapters.cells import CellRepository
from adapters.firestore_repos import (
    DamRepository,
    RankingRepository,
    VolunteerRepository,
)
from bara_agent.agent import build_tools, tool_name
from bara_agent.output import ToolName
from bara_agent.prompts import INSTRUCTION, PROMPT_VERSION
from contracts import Dam, RankedCell, Volunteer
from tests.fakes import FakeWarehouse, InMemoryCollection


def registered_names() -> set[str]:
    tools = build_tools(
        rankings=RankingRepository(lambda region: InMemoryCollection(RankedCell)),
        cells=CellRepository(FakeWarehouse()),
        dams=DamRepository(InMemoryCollection(Dam)),
        volunteers=VolunteerRepository(InMemoryCollection(Volunteer)),
        radius_m=1_000,
    )
    return {tool_name(tool) for tool in tools}


def test_instruction_names_exactly_the_registered_tools_and_the_evidence_enum():
    names = set(get_args(ToolName))

    assert registered_names() == names
    assert all(name in INSTRUCTION for name in names)


def test_instruction_has_no_braces_for_adk_to_read_as_state():
    assert "{" not in INSTRUCTION
    assert "}" not in INSTRUCTION


def test_instruction_carries_the_never_close_rule_and_the_fraction_glossary():
    assert "never close a case" in INSTRUCTION
    assert "0.62 means 62%" in INSTRUCTION


def test_prompt_version():
    assert PROMPT_VERSION == "agent-v1"
