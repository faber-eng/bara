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
from tests.fakes import FakeWarehouse, InMemoryCollection, UnusedAreaRanker


class UnusedAssigner:
    async def assign(self, request):
        raise AssertionError("not called")


class UnusedChecker:
    async def check(self, task_id, evidence_id):
        raise AssertionError("not called")


class UnusedReviewer:
    def request(self, case_id, reason):
        raise AssertionError("not called")


class UnusedEscalator:
    async def escalate(self, case_id, reason):
        raise AssertionError("not called")


def registered_names() -> set[str]:
    tools = build_tools(
        rankings=RankingRepository(lambda region: InMemoryCollection(RankedCell)),
        cells=CellRepository(FakeWarehouse()),
        dams=DamRepository(InMemoryCollection(Dam)),
        volunteers=VolunteerRepository(InMemoryCollection(Volunteer)),
        assigner=UnusedAssigner(),
        checker=UnusedChecker(),
        escalator=UnusedEscalator(),
        reviewer=UnusedReviewer(),
        area_ranker=UnusedAreaRanker(),
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
    assert PROMPT_VERSION == "agent-v7"


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


def test_fire_signs_escalate_before_any_repair_task():
    escalate = INSTRUCTION.index("call escalate once with the case id")
    repair = INSTRUCTION.index('role "repair_team"')

    assert escalate < repair
    assert "4. Otherwise, if the verdict's dam_state is broken" in INSTRUCTION


def overdue_section() -> str:
    start = INSTRUCTION.index("## When the trigger is task.overdue")
    return INSTRUCTION[start : INSTRUCTION.index("## Rules")]


def test_an_overdue_task_on_a_high_risk_case_escalates_first():
    section = overdue_section()

    assert "drying_score is 80 or more" in section
    assert "p_reignite is 0.5 or more" in section
    assert "smoke_seen is true" in section
    assert "attempt is 2 or more" in section
    assert section.index("call escalate once") < section.index("find_people")


def test_an_overdue_task_is_reassigned_once_to_someone_else():
    section = overdue_section()

    assert "other than the event assignee_id" in section
    assert "with the event task_type" in section
    assert 'dam_check: role "volunteer"' in section
    assert 'dam_repair: role "repair_team"' in section
    assert 'patrol_recheck: role "patrol"' in section
    assert "Leave deadline_hours out." in section


def test_an_overdue_task_with_nobody_else_escalates():
    assert "If no other person is found, call escalate once" in overdue_section()


def test_a_failed_reassignment_escalates():
    assert "If assign_task returns an error, call escalate once" in overdue_section()


def test_an_unclear_or_misplaced_photo_is_sent_to_a_person_by_the_tool():
    start = INSTRUCTION.index("## When the trigger is evidence.received")
    section = INSTRUCTION[
        start : INSTRUCTION.index("## When the trigger is task.overdue")
    ]

    assert "or location_ok is false, call request_human_review once" in section
    assert section.index("request_human_review") < section.index("call escalate once")


def test_the_coordinator_can_rank_a_drawn_area():
    assert "run_area_ranking" in registered_names()


def area_check_section() -> str:
    start = INSTRUCTION.index("## When the trigger is area.check")
    return INSTRUCTION[start : INSTRUCTION.index("## Rules")]


def test_an_area_check_ranks_the_drawn_area_once_and_nothing_else():
    section = area_check_section()

    assert "once with the coordinates of the event area" in section
    assert "call no other tool" in section


def test_the_weekly_ranked_cells_never_take_an_area_run():
    assert (
        "Never call run_area_ranking for the case cell or the weekly ranked cells"
        in (area_check_section())
    )
