import logging
from datetime import UTC, datetime

import pytest

from casework.evidence_check import CheckedEvidence, EvidenceMissing
from contracts import EvidenceReceived, EvidenceReceivedEvent
from events import MalformedPush
from evidence_events import EvidenceReceivedHandler
from tests.fakes import make_drying_ranked_event, make_verdict

NOW = datetime(2026, 10, 17, 12, 0, tzinfo=UTC)
BROKEN = make_verdict(dam_state="broken")


class FakeChecker:
    def __init__(self, verdict=BROKEN, stored=True, awaits_agent=True, error=None):
        self.verdict = verdict
        self.stored = stored
        self.awaits_agent = awaits_agent
        self.error = error
        self.calls = []
        self.flagged = []

    async def check(self, task_id, evidence_id):
        self.calls.append((task_id, evidence_id))
        if self.error is not None:
            raise self.error
        return CheckedEvidence(
            evidence_id,
            self.verdict,
            True,
            stored=self.stored,
            from_cache=False,
            awaits_agent=self.awaits_agent,
        )

    def flag_for_person(self, case_id):
        self.flagged.append(case_id)


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


def handle(checker, agent):
    EvidenceReceivedHandler(checker=checker, agent=agent).handle("m1", evidence_event())


def has_event(caplog, name):
    return any(getattr(r, "fields", {}).get("event") == name for r in caplog.records)


def test_a_broken_dam_verdict_runs_the_agent_with_the_event_then_checks_the_case():
    checker, agent = FakeChecker(), FakeAgent()

    handle(checker, agent)

    assert checker.calls == [("t1", "e1")]
    assert agent.runs == [
        (
            "evidence.received",
            "c1",
            "m1-c1",
            {"evidence_id": "e1", "task_id": "t1", "case_id": "c1"},
        )
    ]
    assert checker.flagged == ["c1"]


def test_a_verdict_the_case_does_not_wait_on_does_not_run_the_agent():
    checker, agent = FakeChecker(awaits_agent=False), FakeAgent()

    handle(checker, agent)

    assert agent.runs == []
    assert checker.flagged == ["c1"]


def test_a_repeat_event_whose_verdict_was_already_stored_does_nothing(caplog):
    checker, agent = FakeChecker(stored=False, awaits_agent=False), FakeAgent()

    with caplog.at_level(logging.INFO):
        handle(checker, agent)

    assert agent.runs == []
    assert checker.flagged == []
    assert has_event(caplog, "evidence_already_checked")


def test_a_failed_check_sends_the_case_to_a_person_without_the_agent(caplog):
    checker = FakeChecker(error=EvidenceMissing("no file"))
    agent = FakeAgent()

    with caplog.at_level(logging.ERROR):
        handle(checker, agent)

    assert agent.runs == []
    assert checker.flagged == ["c1"]
    assert has_event(caplog, "evidence_check_failed")


def test_an_unexpected_check_error_propagates_for_a_retry():
    checker = FakeChecker(error=RuntimeError("firestore down"))

    with pytest.raises(RuntimeError):
        handle(checker, FakeAgent())

    assert checker.flagged == []


def test_a_failed_agent_run_is_logged_and_the_case_goes_to_a_person(caplog):
    checker = FakeChecker()
    agent = FakeAgent(RuntimeError("model down"))

    with caplog.at_level(logging.ERROR):
        handle(checker, agent)

    assert has_event(caplog, "event_case_run_failed")
    assert checker.flagged == ["c1"]


def test_another_event_type_is_malformed():
    handler = EvidenceReceivedHandler(checker=FakeChecker(), agent=FakeAgent())

    with pytest.raises(MalformedPush):
        handler.handle("m1", make_drying_ranked_event())
