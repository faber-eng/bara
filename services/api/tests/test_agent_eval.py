import asyncio
import json
from datetime import UTC, datetime

import pytest
from google.adk.evaluation.eval_case import (
    IntermediateData,
    Invocation,
    InvocationEvent,
    InvocationEvents,
)
from google.adk.evaluation.eval_metrics import EvalMetric
from google.adk.evaluation.eval_result import EvalSetResult
from google.adk.evaluation.evaluator import EvalStatus
from google.genai import types

from bara_agent.prompts import PROMPT_VERSION
from evals.agent_eval.eval_set import EVAL_SET_PATH, render_eval_set
from evals.agent_eval.metric import trajectory_matches, trajectory_subset_args
from evals.agent_eval.scenarios import build_scenarios
from evals.agent_eval.world import build_world_tools
from evals.run_agent_eval import OUTPUT_PATH, REPO_ROOT, EvalRunMissing, summarize
from tests.fakes import FakeToolContext

REQUIRED_CASES = {
    "dam_broken_assigns_repair",
    "dam_intact_left_for_a_person",
    "low_confidence_goes_to_review",
    "overdue_high_risk_escalates",
    "overdue_low_risk_reassigns",
    "second_overdue_escalates",
    "recheck_smoke_escalates",
    "location_mismatch_goes_to_review",
    "area_check_ranks_the_drawn_area",
}


def call(name: str, **args: object) -> types.FunctionCall:
    return types.FunctionCall(name=name, args=args)


def tools_by_name():
    tools = build_world_tools(build_scenarios(), radius_m=1000.0)
    return {tool.function.__name__: tool.function for tool in tools}


def scenario(scenario_id: str):
    [found] = [item for item in build_scenarios() if item.id == scenario_id]
    return found


def test_the_committed_eval_set_matches_the_builder():
    assert EVAL_SET_PATH.read_text(encoding="utf-8") == render_eval_set()


def test_the_eval_set_covers_every_required_case_once():
    ids = [item.id for item in build_scenarios()]
    assert len(ids) == len(set(ids))
    assert set(ids) == REQUIRED_CASES


def test_every_scenario_has_its_own_case_cell_and_run_input():
    scenarios = build_scenarios()
    assert len({item.case.id for item in scenarios}) == len(scenarios)
    assert len({item.case.cell_id for item in scenarios}) == len(scenarios)
    for item in scenarios:
        data = item.run_input().split("<<<RUN\n")[1].split("\nRUN>>>")[0]
        rendered = json.loads(data)
        assert rendered["trigger"] == item.trigger
        assert rendered["case"]["id"] == item.case.id
        assert rendered["event"] == item.event


def test_an_overdue_run_input_carries_the_task_type_and_assignee():
    item = scenario("overdue_low_risk_reassigns")
    assert item.event == {
        "task_id": "task-overdue_low_risk_reassigns",
        "case_id": "case-overdue_low_risk_reassigns",
        "attempt": 1,
        "task_type": "dam_check",
        "assignee_id": "vol-5a",
    }


def test_trajectory_matches_ignores_args_the_expected_call_leaves_out():
    actual = [call("escalate", case_id="c1", reason="drying_score 91 is 80 or more")]
    assert trajectory_matches(actual, [call("escalate", case_id="c1")])


@pytest.mark.parametrize(
    "actual",
    [
        [call("escalate", case_id="c2", reason="r")],
        [call("escalate", reason="r")],
        [call("request_human_review", case_id="c1", reason="r")],
        [],
        [
            call("escalate", case_id="c1", reason="r"),
            call("escalate", case_id="c1", reason="r"),
        ],
    ],
)
def test_trajectory_matches_fails_on_a_wrong_missing_or_extra_call(actual):
    assert not trajectory_matches(actual, [call("escalate", case_id="c1")])


def test_trajectory_matches_needs_the_expected_order():
    expected = [call("find_people", cell_id="x"), call("assign_task", case_id="c1")]
    actual = [call("assign_task", case_id="c1"), call("find_people", cell_id="x")]
    assert not trajectory_matches(actual, expected)


def invocation(calls: list[types.FunctionCall]) -> Invocation:
    return Invocation(
        user_content=types.Content(role="user", parts=[types.Part(text="run")]),
        intermediate_data=IntermediateData(tool_uses=calls),
    )


def test_the_metric_passes_a_matching_invocation_and_fails_a_wrong_one():
    metric = EvalMetric(metric_name="tool_trajectory_subset_args")
    expected = [invocation([call("escalate", case_id="c1")])]

    good = trajectory_subset_args(
        metric, [invocation([call("escalate", case_id="c1", reason="r")])], expected
    )
    bad = trajectory_subset_args(
        metric, [invocation([call("request_human_review", case_id="c1")])], expected
    )

    assert good.overall_eval_status == EvalStatus.PASSED
    assert good.overall_score == 1.0
    assert bad.overall_eval_status == EvalStatus.FAILED
    assert bad.overall_score == 0.0


def test_check_evidence_returns_the_fixed_verdict_of_the_scenario():
    item = scenario("location_mismatch_goes_to_review")
    result = asyncio.run(
        tools_by_name()["check_evidence"](
            item.event["task_id"], item.event["evidence_id"]
        )
    )
    assert result["location_ok"] is False
    assert result["verdict"]["dam_state"] == "broken"


def test_check_evidence_on_unknown_evidence_returns_an_error():
    result = asyncio.run(tools_by_name()["check_evidence"]("task-x", "ev-x"))
    assert "error" in result


def test_find_people_lists_the_overdue_assignee_first_then_the_other_volunteer():
    result = asyncio.run(tools_by_name()["find_people"]("eval-cell-5", "volunteer"))
    assert [person["id"] for person in result["people"][:2]] == ["vol-5a", "vol-5b"]


def test_find_people_finds_the_repair_team_of_the_broken_dam_case_first():
    result = asyncio.run(tools_by_name()["find_people"]("eval-cell-1", "repair_team"))
    assert result["people"][0]["id"] == "repair-1"


def test_the_action_tools_accept_every_call():
    tools = tools_by_name()
    assigned = asyncio.run(
        tools["assign_task"](
            "case-a", "repair-1", "dam_repair", "Fix the gap.", FakeToolContext()
        )
    )
    escalated = asyncio.run(tools["escalate"]("case-a", "Smoke seen."))
    reviewed = asyncio.run(tools["request_human_review"]("case-a", "Blurred."))
    assert assigned["task_id"] == "task-new-case-a"
    assert assigned["assignee_name"] == "Budi Santoso"
    assert assigned["deadline_local"] == "Tuesday 20 October 2026, 10:00 WIB"
    assert escalated["escalation_id"] == "esc-case-a"
    assert reviewed == {"case_id": "case-a", "status": "human_review"}


def case_result(eval_id: str, status: int, model: str | None) -> dict:
    events = InvocationEvents(
        invocation_events=[
            InvocationEvent(author="bara_coordinator", model_version=model)
        ]
    )
    actual = Invocation(
        user_content=types.Content(role="user", parts=[types.Part(text="run")]),
        intermediate_data=events,
    )
    return {
        "eval_set_id": "bara_agent",
        "eval_id": eval_id,
        "final_eval_status": status,
        "overall_eval_metric_results": [],
        "eval_metric_result_per_invocation": [
            {
                "actual_invocation": actual.model_dump(mode="json"),
                "eval_metric_results": [],
            }
        ],
        "session_id": f"s-{eval_id}",
    }


def eval_set_result(*cases: dict) -> EvalSetResult:
    return EvalSetResult.model_validate(
        {
            "eval_set_result_id": "r1",
            "eval_set_id": "bara_agent",
            "eval_case_results": list(cases),
        }
    )


def test_summarize_writes_the_agent_part_in_case_order():
    result = eval_set_result(
        case_result("b", EvalStatus.FAILED.value, "gemini-3.1-pro-preview"),
        case_result("a", EvalStatus.PASSED.value, "gemini-3.1-pro-preview"),
    )

    summary = summarize(result, ["a", "b"], datetime(2026, 10, 18, 5, 0, tzinfo=UTC))

    assert summary == {
        "run_at": "2026-10-18T05:00:00Z",
        "model": "gemini-3.1-pro-preview",
        "prompt_version": PROMPT_VERSION,
        "cases": 2,
        "passed": 1,
        "pass_rate": 0.5,
        "results": [{"case": "a", "passed": True}, {"case": "b", "passed": False}],
    }


def test_summarize_names_every_model_that_answered():
    result = eval_set_result(
        case_result("a", EvalStatus.PASSED.value, "gemini-3.1-pro-preview"),
        case_result("b", EvalStatus.PASSED.value, "gemini-2.5-pro"),
    )
    summary = summarize(result, ["a", "b"], datetime(2026, 10, 18, tzinfo=UTC))
    assert summary["model"] == "gemini-2.5-pro, gemini-3.1-pro-preview"


def test_summarize_refuses_a_result_with_a_missing_case_or_no_model():
    with pytest.raises(EvalRunMissing):
        summarize(
            eval_set_result(case_result("a", EvalStatus.PASSED.value, "m")),
            ["a", "b"],
            datetime(2026, 10, 18, tzinfo=UTC),
        )
    with pytest.raises(EvalRunMissing):
        summarize(
            eval_set_result(case_result("a", EvalStatus.PASSED.value, None)),
            ["a"],
            datetime(2026, 10, 18, tzinfo=UTC),
        )


def test_the_agent_part_lands_in_the_repo_docs_eval_folder():
    assert (REPO_ROOT / "services" / "api" / "evals").is_dir()
    assert OUTPUT_PATH == REPO_ROOT / "docs" / "eval" / "agent.json"


def test_the_area_check_case_expects_one_area_run_on_the_drawn_polygon():
    item = scenario("area_check_ranks_the_drawn_area")

    assert item.trigger == "area.check"
    assert [(call.name, call.args) for call in item.expected] == [
        ("run_area_ranking", {"coordinates": item.event["area"]["coordinates"]})
    ]


def test_the_eval_world_ranks_a_drawn_area_without_earth_engine():
    item = scenario("area_check_ranks_the_drawn_area")
    result = asyncio.run(
        tools_by_name()["run_area_ranking"](
            item.event["area"]["coordinates"], FakeToolContext()
        )
    )
    assert result["status"] == "ranked"
    assert result["cells"][0]["rank"] == 1
