from collections.abc import Callable, Coroutine, Mapping
from typing import Any, Protocol

from bara_agent.tools.result import ToolResult, tool_error
from casework.escalation import EscalationRejected
from contracts import Escalation


class EscalationSource(Protocol):
    async def escalate(self, case_id: str, reason: str) -> Escalation: ...


class Escalate:
    def __init__(self, escalator: EscalationSource):
        self._escalator = escalator

    @property
    def function(self) -> Callable[..., Coroutine[Any, Any, ToolResult]]:
        return self.escalate

    async def escalate(self, case_id: str, reason: str) -> ToolResult:
        """Hands the case to the fire brigade: writes the brief in Indonesian
        and English, sends it with the photos, the map link and the timeline,
        and moves the case to escalated.

        Args:
            case_id: Case id from the run input.
            reason: One English sentence on why the case needs a crew now,
                with the numbers from the tool results.
        """
        try:
            escalation = await self._escalator.escalate(case_id, reason)
        except EscalationRejected as error:
            return tool_error(str(error))
        return {
            "escalation_id": escalation.id,
            "contact_id": escalation.contact_id,
            "brief_en": escalation.brief_en,
        }

    @staticmethod
    def summarize(result: Mapping[str, object]) -> str:
        return f"escalation {result['escalation_id']} to {result['contact_id']}"
