from collections.abc import Callable, Coroutine, Mapping
from typing import Any, Protocol

from google.adk.tools.tool_context import ToolContext

from adapters.area_limit_store import AreaLimitUnavailable
from adapters.earthengine_area import AreaSourceError
from bara_agent.tools.result import ToolResult, count_label, entries, tool_error
from casework.area_ranking import (
    AreaBusy,
    AreaTimeout,
    OutsideRegions,
    RateLimited,
)
from contracts import AreaRanking
from domain.area_polygon import InvalidPolygon, PolygonTooLarge

AGENT_UID = "agent"
MAX_AREA_RUNS = 2
AREA_RUNS_KEY = "area_runs"


class AreaRankingSource(Protocol):
    async def rank_within_deadline(self, uid: str, raw: object) -> AreaRanking: ...


class RunAreaRanking:
    def __init__(self, ranker: AreaRankingSource):
        self._ranker = ranker

    @property
    def function(self) -> Callable[..., Coroutine[Any, Any, ToolResult]]:
        return self.run_area_ranking

    async def run_area_ranking(
        self, coordinates: list[list[list[float]]], tool_context: ToolContext
    ) -> ToolResult:
        """Ranks the peat cells of an area an ops user drew, by drying score this week.

        Use it only for a drawn area that is not one of the weekly ranked cells.
        Returns the area's top cells (cell_id, centroid, drying_score, rank),
        status "ranked" or "no_peat", area_km2 and a map tile URL.

        Args:
            coordinates: The coordinates of a GeoJSON Polygon inside Riau or the
                Congo Cuvette, up to 2500 km2: one ring of [lon, lat] corners
                with the first corner repeated last, for example
                [[[102.0, 0.5], [102.1, 0.5], [102.1, 0.6], [102.0, 0.5]]].
        """
        spent = tool_context.state.get(AREA_RUNS_KEY, 0)
        if spent >= MAX_AREA_RUNS:
            return tool_error(f"at most {MAX_AREA_RUNS} area runs per agent run")
        tool_context.state[AREA_RUNS_KEY] = spent + 1
        try:
            ranking = await self._ranker.rank_within_deadline(
                AGENT_UID, {"type": "Polygon", "coordinates": coordinates}
            )
        except (InvalidPolygon, PolygonTooLarge, OutsideRegions) as error:
            return tool_error(f"area rejected: {error or type(error).__name__}")
        except (
            RateLimited,
            AreaBusy,
            AreaTimeout,
            AreaSourceError,
            AreaLimitUnavailable,
        ) as error:
            return tool_error(
                f"area ranking unavailable: {error or type(error).__name__}"
            )
        return ranking.model_dump(mode="json")

    @staticmethod
    def summarize(result: Mapping[str, object]) -> str:
        if result.get("status") == "no_peat":
            return "no mapped peat"
        cells = entries(result, "cells")
        label = count_label(len(cells), "cell", "cells")
        if not cells:
            return label
        return f"{label}, top {cells[0]['cell_id']} at {cells[0]['drying_score']:.1f}"
