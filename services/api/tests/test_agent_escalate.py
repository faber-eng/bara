import asyncio

from bara_agent.tools.escalate import Escalate
from casework.escalation import EscalationRejected
from tests.fakes import make_escalation


class FakeEscalator:
    def __init__(self, error=None):
        self.error = error
        self.calls = []

    async def escalate(self, case_id, reason):
        self.calls.append((case_id, reason))
        if self.error is not None:
            raise self.error
        return make_escalation(id="x1", contact_id="ct1", brief_en="Send a crew.")


def call(escalator):
    return asyncio.run(Escalate(escalator).escalate("c1", "Smoke wisps on the photo."))


def test_escalate_returns_the_escalation_and_its_contact():
    escalator = FakeEscalator()

    result = call(escalator)

    assert escalator.calls == [("c1", "Smoke wisps on the photo.")]
    assert result == {
        "escalation_id": "x1",
        "contact_id": "ct1",
        "brief_en": "Send a crew.",
    }


def test_a_rejected_escalation_is_a_tool_error():
    result = call(FakeEscalator(EscalationRejected("no brigade contact in riau")))

    assert result == {"error": "no brigade contact in riau"}


def test_escalate_summary():
    summary = Escalate.summarize({"escalation_id": "x1", "contact_id": "ct1"})

    assert summary == "escalation x1 to ct1"
