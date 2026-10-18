import asyncio
from collections.abc import Callable, Coroutine, Mapping
from typing import Any, get_args

from adapters.cells import CellRepository
from adapters.firestore_repos import TaskRepository, VolunteerRepository
from bara_agent.tools.result import ToolResult, count_label, entries, tool_error
from contracts import VolunteerRole
from domain.people import PersonMatch, nearest_people

MAX_K = 10
METRES_PER_KM = 1000
ROLES = get_args(VolunteerRole)


def person_entry(match: PersonMatch) -> ToolResult:
    volunteer = match.volunteer
    return {
        "id": volunteer.id,
        "name": volunteer.name,
        "role": volunteer.role,
        "language": volunteer.language,
        "distance_km": round(match.distance_m / METRES_PER_KM, 1),
        "example": volunteer.example,
        "busy": match.busy,
    }


class FindPeople:
    def __init__(
        self,
        cells: CellRepository,
        volunteers: VolunteerRepository,
        tasks: TaskRepository,
    ):
        self._cells = cells
        self._volunteers = volunteers
        self._tasks = tasks

    @property
    def function(self) -> Callable[..., Coroutine[Any, Any, ToolResult]]:
        return self.find_people

    async def find_people(
        self, cell_id: str, role: VolunteerRole, k: int = 3
    ) -> ToolResult:
        """Finds the nearest available people of one role for a grid cell.
        People with no open task come first, nearest first; people who already
        hold an open task (busy true) come after them. Real people and example
        people are listed together.

        Args:
            cell_id: Grid cell id from the case.
            role: volunteer, repair_team or patrol.
            k: How many people to return, 1 to 10.
        """
        if role not in ROLES:
            return tool_error(f"role must be one of {', '.join(ROLES)}, got {role!r}")
        if not 1 <= k <= MAX_K:
            return tool_error(f"k must be 1 to {MAX_K}, got {k}")
        return await asyncio.to_thread(self._lookup, cell_id, role, k)

    def _lookup(self, cell_id: str, role: VolunteerRole, k: int) -> ToolResult:
        centroid = self._cells.centroid(cell_id)
        if centroid is None:
            return tool_error(f"unknown cell {cell_id!r}")
        matches = nearest_people(
            centroid,
            self._volunteers.available(role),
            k,
            self._tasks.open_assignees(),
        )
        return {
            "cell_id": cell_id,
            "role": role,
            "people": [person_entry(match) for match in matches],
        }

    @staticmethod
    def summarize(result: Mapping[str, object]) -> str:
        people = entries(result, "people")
        label = count_label(len(people), "person", "people")
        if not people:
            return label
        nearest = people[0]
        return f"{label}, nearest {nearest['id']} at {nearest['distance_km']} km"
