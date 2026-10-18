import re
from collections.abc import Iterable
from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from contracts import AgentDecision

ISO_TIME = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}")
LONG_NUMBER = re.compile(r"\d+\.\d{3,}")

ToolName = Literal[
    "rank_areas",
    "get_area_facts",
    "find_people",
    "assign_task",
    "check_evidence",
    "escalate",
    "request_human_review",
    "run_area_ranking",
]


class AgentOutput(BaseModel):
    model_config = ConfigDict(frozen=True)

    decision: Annotated[str, Field(min_length=1)]
    reason: Annotated[str, Field(min_length=1)]
    evidence: Annotated[list[ToolName], Field(min_length=1)]
    next_check_at: AwareDatetime | None

    def to_decision(self) -> AgentDecision:
        return AgentDecision(
            decision=self.decision,
            reason=self.reason,
            evidence=list(self.evidence),
            next_check_at=self.next_check_at,
        )


def names_an_id(text: str, ids: Iterable[str]) -> bool:
    return any(re.search(rf"\b{re.escape(item)}\b", text) for item in ids)


def readability_problems(text: str, person_ids: Iterable[str]) -> list[str]:
    problems = []
    if ISO_TIME.search(text) is not None:
        problems.append("iso time")
    if LONG_NUMBER.search(text) is not None:
        problems.append("long number")
    if names_an_id(text, person_ids):
        problems.append("person id")
    return problems
