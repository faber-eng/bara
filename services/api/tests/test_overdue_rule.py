from datetime import UTC, datetime

import pytest

from adapters.firestore_repos import (
    CaseRepository,
    EvidenceRepository,
    TaskRepository,
)
from casework.escalation import EscalationRejected
from contracts import (
    Case,
    CaseRisk,
    Evidence,
    HistoryFlags,
    Task,
    TaskOverdue,
    TaskOverdueEvent,
)
from domain.escalation import field_signs, overdue_escalation_reason, smoke_ever_seen
from overdue_events import TaskOverdueHandler
from tests.fakes import (
    InMemoryCollection,
    make_case,
    make_escalation,
    make_evidence,
    make_task,
    make_verdict,
)

NOW = datetime(2026, 10, 17, 12, 0, tzinfo=UTC)
LOW = CaseRisk(drying_score=40.0, p_reignite=0.1)


class FakeAgent:
    def __init__(self):
        self.runs = []

    async def run_case(self, trigger, case_id, run_id, event=None):
        self.runs.append((trigger, case_id, event))


class FakeEscalator:
    def __init__(self, error=None):
        self.error = error
        self.calls = []

    async def escalate(self, case_id, reason):
        self.calls.append((case_id, reason))
        if self.error is not None:
            raise self.error
        return make_escalation()


def overdue_event(attempt) -> TaskOverdueEvent:
    return TaskOverdueEvent(
        id="ev-1",
        type="task.overdue",
        occurred_at=NOW,
        region="riau",
        example=True,
        payload=TaskOverdue(task_id="t1", case_id="c1", attempt=attempt),
    )


class World:
    def __init__(self, *, risk=LOW, smoke_seen=False, evidence=(), attempt=1):
        self.attempt = attempt
        self.agent = FakeAgent()
        self.escalator = FakeEscalator()
        cases = self.cases = InMemoryCollection(Case)
        cases.put(
            "c1",
            make_case(
                status="overdue",
                risk=risk,
                history_flags=HistoryFlags(smoke_seen=smoke_seen),
            ),
        )
        tasks = InMemoryCollection(Task)
        tasks.put("t1", make_task(status="overdue", attempt=attempt))
        stored = InMemoryCollection(Evidence)
        for item in evidence:
            stored.put(item.id, item)
        self.handler = TaskOverdueHandler(
            cases=CaseRepository(cases),
            tasks=TaskRepository(tasks),
            evidence=EvidenceRepository(stored),
            agent=self.agent,
            escalator=self.escalator,
        )

    def overdue(self):
        self.handler.handle("m1", overdue_event(self.attempt))


def smoke_photo(smoke="wisps"):
    return make_evidence(
        id="e9", case_id="c1", verdict=make_verdict(smoke=smoke, dam_state="intact")
    )


def test_low_risk_first_overdue_goes_to_the_agent_to_reassign_once():
    world = World()

    world.overdue()

    assert world.escalator.calls == []
    assert [run[0] for run in world.agent.runs] == ["task.overdue"]


def test_second_overdue_escalates_without_the_agent():
    world = World(attempt=2)

    world.overdue()

    assert world.agent.runs == []
    assert len(world.escalator.calls) == 1
    case_id, reason = world.escalator.calls[0]
    assert case_id == "c1"
    assert "second overdue" in reason


def test_smoke_flag_on_the_case_escalates():
    world = World(smoke_seen=True)

    world.overdue()

    assert world.agent.runs == []
    assert "smoke" in world.escalator.calls[0][1]


@pytest.mark.parametrize("smoke", ["wisps", "plume"])
def test_smoke_on_any_stored_verdict_escalates_even_with_the_flag_unset(smoke):
    world = World(evidence=[smoke_photo(smoke)])

    world.overdue()

    assert world.agent.runs == []
    assert "smoke" in world.escalator.calls[0][1]


def test_a_clean_verdict_does_not_escalate():
    world = World(evidence=[smoke_photo("none")])

    world.overdue()

    assert world.escalator.calls == []
    assert len(world.agent.runs) == 1


@pytest.mark.parametrize(
    ("risk", "field"),
    [
        (CaseRisk(drying_score=80.0, p_reignite=None), "drying_score 80"),
        (CaseRisk(drying_score=None, p_reignite=0.5), "p_reignite 0.5"),
    ],
)
def test_high_risk_escalates(risk, field):
    world = World(risk=risk)

    world.overdue()

    assert world.agent.runs == []
    assert field in world.escalator.calls[0][1]


def test_just_under_both_limits_does_not_escalate():
    world = World(risk=CaseRisk(drying_score=79.9, p_reignite=0.49))

    world.overdue()

    assert world.escalator.calls == []


def test_a_null_risk_value_does_not_meet_its_rule():
    case = make_case(risk=CaseRisk(drying_score=None, p_reignite=None))

    assert overdue_escalation_reason(case, 1, []) is None


def test_the_agent_still_runs_when_the_code_escalation_is_rejected():
    world = World(attempt=2)
    world.escalator.error = EscalationRejected("no brigade contact in riau")

    world.overdue()

    assert len(world.agent.runs) == 1


def test_smoke_ever_seen_reads_the_flag_and_the_verdicts():
    flagged = make_case(history_flags=HistoryFlags(smoke_seen=True))
    plain = make_case()

    assert smoke_ever_seen(flagged, []) is True
    assert smoke_ever_seen(plain, [make_evidence(verdict=None)]) is False
    assert smoke_ever_seen(plain, [smoke_photo("plume")]) is True


def test_a_voice_note_that_mentions_smoke_is_not_proof():
    plain = make_case()
    spoken = make_evidence(
        id="e8",
        case_id="c1",
        kind="audio",
        verdict=make_verdict(smoke="plume", dam_state="unknown"),
    )

    assert smoke_ever_seen(plain, [spoken]) is False
    assert field_signs([spoken]) is None


def test_an_unexpected_escalation_error_goes_up_and_the_agent_does_not_run():
    world = World(attempt=2)
    world.escalator.error = RuntimeError("store down")

    with pytest.raises(RuntimeError):
        world.overdue()

    assert world.agent.runs == []


def test_the_agent_does_not_run_when_the_case_left_overdue_during_a_rejection():
    world = World(attempt=2)

    async def rejected_after_change(case_id, reason):
        world.cases.update("c1", {"status": "assigned"})
        raise EscalationRejected("case c1 changed while escalating; read it again")

    world.escalator.escalate = rejected_after_change

    world.overdue()

    assert world.agent.runs == []


def test_smoke_in_field_signs_only_when_the_photos_show_smoke():
    from domain.escalation import FieldSigns, smoke_in

    assert smoke_in(None) is False
    assert (
        smoke_in(FieldSigns(smoke="none", open_flame=True, hot_ground=False)) is False
    )
    assert (
        smoke_in(FieldSigns(smoke="wisps", open_flame=False, hot_ground=False)) is True
    )
