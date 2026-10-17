from collections.abc import Awaitable, Callable, Mapping, Sequence
from typing import Protocol

from google.adk.agents import LlmAgent
from google.adk.models import BaseLlm

from adapters.cells import CellRepository
from adapters.firestore_repos import (
    DamRepository,
    RankingRepository,
    VolunteerRepository,
)
from bara_agent.output import AgentOutput
from bara_agent.prompts import AGENT_NAME, INSTRUCTION
from bara_agent.recorder import Summarizer
from bara_agent.tools.assign_task import Assigner, AssignTask
from bara_agent.tools.find_people import FindPeople
from bara_agent.tools.get_area_facts import GetAreaFacts
from bara_agent.tools.rank_areas import RankAreas
from bara_agent.tools.result import ToolResult


class AgentTool(Protocol):
    @property
    def function(self) -> Callable[..., ToolResult | Awaitable[ToolResult]]: ...

    def summarize(self, result: Mapping[str, object]) -> str: ...


def tool_name(tool: AgentTool) -> str:
    return tool.function.__name__


def summarizers(tools: Sequence[AgentTool]) -> dict[str, Summarizer]:
    return {tool_name(tool): tool.summarize for tool in tools}


def build_coordinator(model: BaseLlm, tools: Sequence[AgentTool]) -> LlmAgent:
    return LlmAgent(
        name=AGENT_NAME,
        model=model,
        instruction=INSTRUCTION,
        tools=[tool.function for tool in tools],
        output_schema=AgentOutput,
    )


def build_tools(
    *,
    rankings: RankingRepository,
    cells: CellRepository,
    dams: DamRepository,
    volunteers: VolunteerRepository,
    assigner: Assigner,
    radius_m: float,
) -> list[AgentTool]:
    return [
        RankAreas(rankings),
        GetAreaFacts(cells, dams, radius_m),
        FindPeople(cells, volunteers),
        AssignTask(assigner),
    ]
