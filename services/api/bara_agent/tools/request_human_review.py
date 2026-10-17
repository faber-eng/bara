from collections.abc import Callable, Coroutine, Mapping
from typing import Any, Protocol

from bara_agent.tools.result import ToolResult, tool_error
from casework.review import ReviewRejected


class ReviewSource(Protocol):
    def request(self, case_id: str, reason: str) -> None: ...


class RequestHumanReview:
    def __init__(self, reviewer: ReviewSource):
        self._reviewer = reviewer

    @property
    def function(self) -> Callable[..., Coroutine[Any, Any, ToolResult]]:
        return self.request_human_review

    async def request_human_review(self, case_id: str, reason: str) -> ToolResult:
        """Puts the case in the Ops review queue so a person decides. Use it when
        the evidence is unclear, the photo location does not match the task
        point, or the check failed.

        Args:
            case_id: Case id from the run input.
            reason: One English sentence on why a person must look, with the
                numbers from the tool results.
        """
        try:
            self._reviewer.request(case_id, reason)
        except ReviewRejected as error:
            return tool_error(str(error))
        return {"case_id": case_id, "status": "human_review"}

    @staticmethod
    def summarize(result: Mapping[str, object]) -> str:
        return f"case {result['case_id']} sent to a person"
