from datetime import UTC, datetime

import pytest

from adapters.firestore_repos import (
    CaseRepository,
    EvidenceRepository,
    TaskRepository,
)
from contracts import Case, CaseRisk, Evidence, Task, TaskOverdue, TaskOverdueEvent
from events import MalformedPush
from overdue_events import TaskOverdueHandler
from tests.fakes import (
    InMemoryCollection,
    make_case,
    make_drying_ranked_event,
    make_task,
)

NOW = datetime(2026, 10, 17, 12, 0, tzinfo=UTC)


class FakeAgent:
    def __init__(self, error=None):
        self.error = error
        self.runs = []

    async def run_case(self, trigger, case_id, run_id, event=None):
        self.runs.append((trigger, case_id, run_id, event))
        if self.error is not None:
            raise self.error


class UnusedEscalator:
    async def escalate(self, case_id, reason):
        raise AssertionError("not called")


def overdue_event(attempt=1) -> TaskOverdueEvent:
    return TaskOverdueEvent(
        id="ev-1",
        type="task.overdue",
        occurred_at=NOW,
        region="riau",
        example=True,
        payload=TaskOverdue(task_id="t1", case_id="c1", attempt=attempt),
    )


def make_handler(agent, case_status="overdue", task=None):
    cases = InMemoryCollection(Case)
    cases.put(
        "c1",
        make_case(
            status=case_status, risk=CaseRisk(drying_score=40.0, p_reignite=None)
        ),
    )
    tasks = InMemoryCollection(Task)
    stored = task or make_task(status="overdue", assignee_id="vol-ari")
    tasks.put(stored.id, stored)
    return TaskOverdueHandler(
        cases=CaseRepository(cases),
        tasks=TaskRepository(tasks),
        evidence=EvidenceRepository(InMemoryCollection(Evidence)),
        agent=agent,
        escalator=UnusedEscalator(),
    )


def test_an_overdue_case_runs_the_agent_with_the_event_and_the_missed_assignee():
    agent = FakeAgent()

    make_handler(agent).handle("m1", overdue_event(attempt=1))

    assert agent.runs == [
        (
            "task.overdue",
            "c1",
            "m1-c1",
            {
                "task_id": "t1",
                "case_id": "c1",
                "attempt": 1,
                "task_type": "dam_check",
                "assignee_id": "vol-ari",
            },
        )
    ]


@pytest.mark.parametrize("status", ["assigned", "escalated", "closed"])
def test_a_case_that_is_no_longer_overdue_is_skipped(status):
    agent = FakeAgent()

    make_handler(agent, case_status=status).handle("m1", overdue_event())

    assert agent.runs == []


def test_an_unknown_case_is_skipped():
    agent = FakeAgent()
    handler = TaskOverdueHandler(
        cases=CaseRepository(InMemoryCollection(Case)),
        tasks=TaskRepository(InMemoryCollection(Task)),
        evidence=EvidenceRepository(InMemoryCollection(Evidence)),
        agent=agent,
        escalator=UnusedEscalator(),
    )

    handler.handle("m1", overdue_event())

    assert agent.runs == []


def test_an_unknown_task_is_skipped():
    agent = FakeAgent()

    make_handler(agent, task=make_task(id="other")).handle("m1", overdue_event())

    assert agent.runs == []


@pytest.mark.parametrize("status", ["open", "done", "reassigned", "cancelled"])
def test_an_event_for_a_task_that_is_no_longer_overdue_is_skipped(status):
    agent = FakeAgent()
    handler = make_handler(agent, task=make_task(status=status))

    handler.handle("m1", overdue_event())

    assert agent.runs == []


def test_an_agent_failure_raises_so_pubsub_delivers_again():
    agent = FakeAgent(error=RuntimeError("model down"))

    with pytest.raises(RuntimeError):
        make_handler(agent).handle("m1", overdue_event())


def test_an_event_of_another_type_is_malformed():
    with pytest.raises(MalformedPush):
        make_handler(FakeAgent()).handle("m1", make_drying_ranked_event())
