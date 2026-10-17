import asyncio

from bara_agent.tools.check_evidence import CheckEvidence
from casework.evidence_check import CheckedEvidence, EvidenceMissing, UnknownEvidence
from casework.evidence_reader import ReaderFailed
from tests.fakes import make_verdict


class FakeChecker:
    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error
        self.calls = []

    async def check(self, task_id, evidence_id):
        self.calls.append((task_id, evidence_id))
        if self.error is not None:
            raise self.error
        return self.result


def checked(**verdict_fields):
    return CheckedEvidence(
        evidence_id="e1",
        verdict=make_verdict(**verdict_fields),
        location_ok=True,
        cached=False,
    )


def call(checker, task_id="t1", evidence_id="e1"):
    return asyncio.run(CheckEvidence(checker).check_evidence(task_id, evidence_id))


def test_check_evidence_returns_the_verdict_and_the_location_result():
    checker = FakeChecker(checked(dam_state="broken"))

    result = call(checker)

    assert checker.calls == [("t1", "e1")]
    assert result["evidence_id"] == "e1"
    assert result["location_ok"] is True
    assert result["verdict"]["dam_state"] == "broken"
    assert result["verdict"]["needs_human"] is False


def test_check_evidence_turns_a_check_error_into_a_tool_error():
    for error in (
        UnknownEvidence("no evidence"),
        EvidenceMissing("no file"),
        ReaderFailed("bad reply"),
    ):
        result = call(FakeChecker(error=error))

        assert result == {"error": str(error)}


def test_check_evidence_summary():
    result = call(FakeChecker(checked(dam_state="broken", confidence=0.86)))

    assert CheckEvidence.summarize(result) == (
        "dam broken, smoke none, confidence 0.86, location ok"
    )


def test_check_evidence_summary_names_a_person_review():
    result = call(FakeChecker(checked(needs_human=True)))

    assert CheckEvidence.summarize(result).endswith("needs a person")
