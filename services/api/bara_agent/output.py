from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from contracts import AgentDecision

ToolName = Literal["rank_areas", "get_area_facts", "find_people", "assign_task"]


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
