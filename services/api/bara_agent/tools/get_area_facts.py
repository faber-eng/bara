from collections.abc import Callable, Mapping

from adapters.cells import CellRepository, CellWeek
from adapters.firestore_repos import DamRepository
from bara_agent.tools.result import ToolResult, count_label, entries, tool_error
from domain.geo import nearby
from domain.weeks import iso_week_label

TREND_WEEKS = 8


def trend(weeks: list[CellWeek]) -> list[ToolResult]:
    oldest_first = sorted(weeks, key=lambda week: week.week_start)
    return [
        {"week": iso_week_label(week.week_start), "drying_score": week.drying_score}
        for week in oldest_first
    ]


class GetAreaFacts:
    def __init__(self, cells: CellRepository, dams: DamRepository, radius_m: float):
        self._cells = cells
        self._dams = dams
        self._radius_m = radius_m

    @property
    def function(self) -> Callable[..., ToolResult]:
        return self.get_area_facts

    def get_area_facts(self, cell_id: str) -> ToolResult:
        """Reads the facts for one grid cell: this week's drying score, rank and
        components, an up-to-8-week trend, the centroid and the dams nearby.

        Args:
            cell_id: Grid cell id from the case or from rank_areas.
        """
        weeks = self._cells.weekly(cell_id, TREND_WEEKS)
        if not weeks:
            return tool_error(f"no drying data for cell {cell_id!r}")
        latest = weeks[0]
        dams = nearby(
            latest.centroid, self._dams.in_region(latest.region), self._radius_m
        )
        return {
            "cell_id": latest.cell_id,
            "region": latest.region,
            "week": iso_week_label(latest.week_start),
            "centroid": latest.centroid.model_dump(mode="json"),
            "components": latest.components.model_dump(mode="json"),
            "drying_score": latest.drying_score,
            "rank": latest.rank,
            "stale_s1": latest.stale_s1,
            "trend": trend(weeks),
            "nearby_dams": [dam.model_dump(mode="json") for dam in dams],
        }

    def summarize(self, result: Mapping[str, object]) -> str:
        dams = count_label(len(entries(result, "nearby_dams")), "dam", "dams")
        return (
            f"{result['cell_id']}: score {result['drying_score']:.1f}, "
            f"rank {result['rank']}, {dams} within {self._radius_m:.0f} m"
        )
