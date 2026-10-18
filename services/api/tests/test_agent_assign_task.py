import asyncio
import inspect
from datetime import UTC, datetime

import pytest

from bara_agent.tools.assign_task import AssignTask
from casework.assignment import Assignment, AssignmentRejected
from casework.messenger import MessengerFailed
from tests.fakes import FakeToolContext, make_message, make_task

DEADLINE = datetime(2026, 10, 20, 12, 0, tzinfo=UTC)


class FakeAssigner:
    def __init__(self, outcome):
        self.outcome = outcome
        self.requests = []

    async def assign(self, request):
        self.requests.append(request)
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome


def done() -> Assignment:
    return Assignment(
        task=make_task(id="task-1", deadline_at=DEADLINE),
        message=make_message(text="Cek sekat dam-7."),
        assignee_name="Eko Prasetyo",
        deadline_local="Tuesday 20 October 2026, 19:00 WIB",
    )


def call(tool: AssignTask, context=None, **overrides):
    fields = {
        "case_id": "c1",
        "assignee_id": "v1",
        "task_type": "dam_check",
        "instructions_hint": "Check the left side.",
    }
    return asyncio.run(
        tool.assign_task(
            **{**fields, **overrides}, tool_context=context or FakeToolContext()
        )
    )


def test_assign_task_is_an_async_tool_named_assign_task():
    tool = AssignTask(FakeAssigner(done()))

    assert tool.function.__name__ == "assign_task"
    assert inspect.iscoroutinefunction(tool.function)


def test_assign_task_returns_the_task_id_deadlines_name_and_message():
    assigner = FakeAssigner(done())

    result = call(AssignTask(assigner), deadline_hours=48)

    assert result == {
        "task_id": "task-1",
        "deadline_at": "2026-10-20T12:00:00+00:00",
        "deadline_local": "Tuesday 20 October 2026, 19:00 WIB",
        "assignee_name": "Eko Prasetyo",
        "message": "Cek sekat dam-7.",
    }
    request = assigner.requests[0]
    assert request.case_id == "c1"
    assert request.assignee_id == "v1"
    assert request.task_type == "dam_check"
    assert request.instructions_hint == "Check the left side."
    assert request.deadline_hours == 48


def test_no_deadline_hours_passes_none():
    assigner = FakeAssigner(done())

    call(AssignTask(assigner))

    assert assigner.requests[0].deadline_hours is None


def test_an_unknown_task_type_is_an_error_without_a_call():
    assigner = FakeAssigner(done())

    result = call(AssignTask(assigner), task_type="dam_party")

    assert "task_type" in result["error"]
    assert assigner.requests == []


@pytest.mark.parametrize(
    "error",
    [AssignmentRejected("case c1 is escalated"), MessengerFailed("too long")],
)
def test_a_rejection_or_messenger_failure_is_a_tool_error(error):
    result = call(AssignTask(FakeAssigner(error)))

    assert str(error) in result["error"]


def test_assign_task_summary():
    summary = AssignTask.summarize(
        {
            "task_id": "task-1",
            "deadline_at": "2026-10-20T12:00:00+00:00",
            "message": "Cek sekat.",
        }
    )

    assert summary == "task task-1 due 2026-10-20T12:00:00+00:00"


def test_a_second_assign_in_one_run_is_refused_and_creates_nothing():
    assigner = FakeAssigner(done())
    tool = AssignTask(assigner)
    context = FakeToolContext()

    first = call(tool, context)
    second = call(tool, context, assignee_id="v2")

    assert first["task_id"] == "task-1"
    assert "a task is already assigned in this run" in str(second["error"])
    assert len(assigner.requests) == 1


def test_a_rejected_assign_does_not_use_up_the_run_slot():
    outcomes = [AssignmentRejected("no such person"), done()]

    class Flaky:
        def __init__(self):
            self.requests = []

        async def assign(self, request):
            self.requests.append(request)
            outcome = outcomes.pop(0)
            if isinstance(outcome, Exception):
                raise outcome
            return outcome

    tool = AssignTask(Flaky())
    context = FakeToolContext()

    first = call(tool, context)
    second = call(tool, context, assignee_id="v2")

    assert "error" in first
    assert second["task_id"] == "task-1"


def test_a_new_agent_run_may_assign_again():
    assigner = FakeAssigner(done())
    tool = AssignTask(assigner)

    call(tool, FakeToolContext())
    again = call(tool, FakeToolContext())

    assert again["task_id"] == "task-1"
    assert len(assigner.requests) == 2
