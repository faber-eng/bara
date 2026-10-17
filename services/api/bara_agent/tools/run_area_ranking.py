from collections.abc import Callable, Mapping
from typing import Protocol

from bara_agent.tools.result import ToolResult, count_label, entries, tool_error
from casework.area_ranking import (
    AreaBusy,
    OutsideRegions,
    RateLimited,
)
from contracts import AreaRanking
from domain.area_polygon import InvalidPolygon, PolygonTooLarge

AGENT_UID = "agent"


class AreaRankingSource(Protocol):
    def rank(self, uid: str, raw: object) -> AreaRanking: ...


class RunAreaRanking:
    def __init__(self, ranker: AreaRankingSource):
        self._ranker = ranker

    @property
    def function(self) -> Callable[..., ToolResult]:
        return self.run_area_ranking

    def run_area_ranking(self, geojson: dict) -> ToolResult:
        """Ranks the peat cells of a drawn area by drying score for this week.

        Args:
            geojson: A GeoJSON Polygon geometry, one ring, up to 2500 km2.
        """
        try:
            ranking = self._ranker.rank(AGENT_UID, geojson)
        except (InvalidPolygon, PolygonTooLarge, OutsideRegions) as error:
            return tool_error(f"area rejected: {error or type(error).__name__}")
        except (RateLimited, AreaBusy) as error:
            return tool_error(f"area ranking unavailable: {error or 'busy'}")
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
