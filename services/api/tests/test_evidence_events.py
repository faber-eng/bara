import logging
from datetime import UTC, datetime

import pytest

from casework.evidence_check import CheckedEvidence, EvidenceMissing
from contracts import EvidenceReceived, EvidenceReceivedEvent
from events import MalformedPush
from evidence_events import EvidenceReceivedHandler
from tests.fakes import make_drying_ranked_event, make_verdict

NOW = datetime(2026, 10, 17, 12, 0, tzinfo=UTC)


class FakeChecker:
    def __init__(self, error=None):
        self.error = error
        self.calls = []

    async def check(self, task_id, evidence_id):
        self.calls.append((task_id, evidence_id))
        if self.error is not None:
            raise self.error
        return CheckedEvidence(evidence_id, make_verdict(), True, cached=False)


class FakeAgent:
    def __init__(self, error=None):
        self.error = error
        self.runs = []

    async def run_case(self, trigger, case_id, run_id, event=None):
        self.runs.append((trigger, case_id, run_id, event))
        if self.error is not None:
            raise self.error


def evidence_event() -> EvidenceReceivedEvent:
    return EvidenceReceivedEvent(
        id="ev-1",
        type="evidence.received",
        occurred_at=NOW,
        region="riau",
        example=True,
        payload=EvidenceReceived(evidence_id="e1", task_id="t1", case_id="c1"),
    )


def test_the_handler_checks_the_evidence_then_runs_the_agent_with_the_event():
    checker, agent = FakeChecker(), FakeAgent()

    EvidenceReceivedHandler(checker=checker, agent=agent).handle("m1", evidence_event())

    assert checker.calls == [("t1", "e1")]
    assert agent.runs == [
        (
            "evidence.received",
            "c1",
            "m1-c1",
            {"evidence_id": "e1", "task_id": "t1", "case_id": "c1"},
        )
    ]


def test_a_failed_check_still_runs_the_agent_and_logs(caplog):
    checker = FakeChecker(EvidenceMissing("no file"))
    agent = FakeAgent()

    with caplog.at_level(logging.ERROR):
        EvidenceReceivedHandler(checker=checker, agent=agent).handle(
            "m1", evidence_event()
        )

    assert len(agent.runs) == 1
    assert any(
        getattr(r, "fields", {}).get("event") == "evidence_check_failed"
        for r in caplog.records
    )


def test_a_failed_agent_run_is_logged_not_raised(caplog):
    agent = FakeAgent(RuntimeError("model down"))

    with caplog.at_level(logging.ERROR):
        EvidenceReceivedHandler(checker=FakeChecker(), agent=agent).handle(
            "m1", evidence_event()
        )

    assert any(
        getattr(r, "fields", {}).get("event") == "event_case_run_failed"
        for r in caplog.records
    )


def test_another_event_type_is_malformed():
    handler = EvidenceReceivedHandler(checker=FakeChecker(), agent=FakeAgent())

    with pytest.raises(MalformedPush):
        handler.handle("m1", make_drying_ranked_event())
