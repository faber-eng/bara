import asyncio
import re
from collections.abc import Callable, Coroutine, Mapping
from typing import Any

from adapters.firestore_repos import RankingRepository
from bara_agent.tools.result import ToolResult, count_label, entries, tool_error
from contracts import RankedCell
from domain.rankings import newest_week_by_rank
from domain.weeks import iso_week_label

MAX_LIMIT = 200
REGION_ID = re.compile(r"^[a-z][a-z0-9_]*$")


def cell_entry(cell: RankedCell) -> ToolResult:
    return {
        "cell_id": cell.cell_id,
        "drying_score": cell.drying_score,
        "rank": cell.rank,
        "components": cell.components.model_dump(mode="json"),
    }


class RankAreas:
    def __init__(self, rankings: RankingRepository):
        self._rankings = rankings

    @property
    def function(self) -> Callable[..., Coroutine[Any, Any, ToolResult]]:
        return self.rank_areas

    async def rank_areas(self, region: str, limit: int = 10) -> ToolResult:
        """Lists the driest grid cells of a region this week, rank 1 first.

        Args:
            region: Region id from the case, for example riau.
            limit: How many cells to return, 1 to 200.
        """
        if not 1 <= limit <= MAX_LIMIT:
            return tool_error(f"limit must be 1 to {MAX_LIMIT}, got {limit}")
        if not REGION_ID.match(region):
            return tool_error(f"region {region!r} is not a region id")
        top = await asyncio.to_thread(self._rankings.top, region, limit)
        cells = newest_week_by_rank(top)
        week = iso_week_label(cells[0].week_start) if cells else None
        return {
            "region": region,
            "week": week,
            "cells": [cell_entry(cell) for cell in cells],
        }

    @staticmethod
    def summarize(result: Mapping[str, object]) -> str:
        cells = entries(result, "cells")
        label = count_label(len(cells), "cell", "cells")
        if not cells:
            return label
        top = cells[0]
        return f"{label}, top {top['cell_id']} at {top['drying_score']:.1f}"
