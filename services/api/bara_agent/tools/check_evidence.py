from collections.abc import Callable, Coroutine, Mapping
from typing import Any, Protocol

from bara_agent.tools.result import ToolResult, tool_error
from casework.evidence_check import CheckedEvidence, CheckError
from casework.evidence_reader import ReaderFailed
from casework.photo import UnreadablePhoto

LOCATION_LABELS: dict[object, str] = {
    True: "location ok",
    False: "location mismatch",
    None: "location unchecked",
}


class Checker(Protocol):
    async def check(self, task_id: str, evidence_id: str) -> CheckedEvidence: ...


class CheckEvidence:
    def __init__(self, checker: Checker):
        self._checker = checker

    @property
    def function(self) -> Callable[..., Coroutine[Any, Any, ToolResult]]:
        return self.check_evidence

    async def check_evidence(self, task_id: str, evidence_id: str) -> ToolResult:
        """Reads the photo a person sent for a task and stores the verdict: what
        the photo shows, how sure the reader is, and whether it was taken at
        the task point.

        Args:
            task_id: Task id from the run input event.
            evidence_id: Evidence id from the run input event.
        """
        try:
            checked = await self._checker.check(task_id, evidence_id)
        except (CheckError, ReaderFailed, UnreadablePhoto) as error:
            return tool_error(str(error))
        return {
            "evidence_id": checked.evidence_id,
            "verdict": checked.verdict.model_dump(mode="json"),
            "location_ok": checked.location_ok,
        }

    @staticmethod
    def summarize(result: Mapping[str, object]) -> str:
        verdict = result["verdict"]
        if not isinstance(verdict, Mapping):
            return "no verdict"
        parts = [
            f"dam {verdict['dam_state']}",
            f"smoke {verdict['smoke']}",
            f"confidence {verdict['confidence']}",
            LOCATION_LABELS[result["location_ok"]],
        ]
        if verdict["needs_human"]:
            parts.append("needs a person")
        return ", ".join(parts)
