import asyncio
import inspect
from datetime import UTC, datetime

import pytest

from bara_agent.tools.assign_task import AssignTask
from casework.assignment import Assignment, AssignmentRejected
from casework.messenger import MessengerFailed
from tests.fakes import make_message, make_task

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


def call(tool: AssignTask, **overrides):
    fields = {
        "case_id": "c1",
        "assignee_id": "v1",
        "task_type": "dam_check",
        "instructions_hint": "Check the left side.",
    }
    return asyncio.run(tool.assign_task(**{**fields, **overrides}))


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
