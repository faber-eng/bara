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


class UnusedAssigner:
    async def assign(self, request):
        raise AssertionError("not called")


class UnusedChecker:
    async def check(self, task_id, evidence_id):
        raise AssertionError("not called")


def registered_names() -> set[str]:
    tools = build_tools(
        rankings=RankingRepository(lambda region: InMemoryCollection(RankedCell)),
        cells=CellRepository(FakeWarehouse()),
        dams=DamRepository(InMemoryCollection(Dam)),
        volunteers=VolunteerRepository(InMemoryCollection(Volunteer)),
        assigner=UnusedAssigner(),
        checker=UnusedChecker(),
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
    assert PROMPT_VERSION == "agent-v3"


def test_instruction_steps_end_with_one_assign_task_call():
    assert "4. Call assign_task once" in INSTRUCTION
    assert 'task_type "dam_check"' in INSTRUCTION


def test_the_agent_never_picks_deadline_hours_and_skips_an_empty_crew():
    assert "Leave deadline_hours out." in INSTRUCTION
    assert "If find_people returns no people, do not call assign_task" in INSTRUCTION


def test_an_evidence_run_checks_the_evidence_from_the_event_first():
    assert (
        "1. Call check_evidence with the event task_id and evidence_id." in INSTRUCTION
    )


def test_a_broken_dam_gets_a_repair_team():
    assert 'role "repair_team"' in INSTRUCTION
    assert 'task_type "dam_repair"' in INSTRUCTION


def test_a_verdict_for_a_person_stops_the_run():
    assert "needs_human is true" in INSTRUCTION
