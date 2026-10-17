from collections.abc import Callable, Mapping
from typing import get_args

from adapters.cells import CellRepository
from adapters.firestore_repos import VolunteerRepository
from bara_agent.tools.result import ToolResult, count_label, entries, tool_error
from contracts import VolunteerRole
from domain.people import PersonMatch, nearest_people

MAX_K = 10
ROLES = get_args(VolunteerRole)


def person_entry(match: PersonMatch) -> ToolResult:
    volunteer = match.volunteer
    return {
        "id": volunteer.id,
        "name": volunteer.name,
        "role": volunteer.role,
        "language": volunteer.language,
        "distance_m": match.distance_m,
        "example": volunteer.example,
    }


class FindPeople:
    def __init__(self, cells: CellRepository, volunteers: VolunteerRepository):
        self._cells = cells
        self._volunteers = volunteers

    @property
    def function(self) -> Callable[..., ToolResult]:
        return self.find_people

    def find_people(self, cell_id: str, role: VolunteerRole, k: int = 3) -> ToolResult:
        """Finds the nearest available people of one role for a grid cell,
        nearest first. Real people and example people are listed together.

        Args:
            cell_id: Grid cell id from the case.
            role: volunteer, repair_team or patrol.
            k: How many people to return, 1 to 10.
        """
        if role not in ROLES:
            return tool_error(f"role must be one of {', '.join(ROLES)}, got {role!r}")
        if not 1 <= k <= MAX_K:
            return tool_error(f"k must be 1 to {MAX_K}, got {k}")
        centroid = self._cells.centroid(cell_id)
        if centroid is None:
            return tool_error(f"unknown cell {cell_id!r}")
        matches = nearest_people(centroid, self._volunteers.available(role), k)
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
        return f"{label}, nearest {nearest['id']} at {nearest['distance_m']} m"
