from collections.abc import Iterable
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from types import MappingProxyType

from contracts import GeoPoint, TaskType, Volunteer, VolunteerRole
from domain.geo import haversine_m

ROLE_FOR_TASK: MappingProxyType[TaskType, VolunteerRole] = MappingProxyType(
    {"dam_check": "volunteer", "dam_repair": "repair_team", "patrol_recheck": "patrol"}
)


@dataclass(frozen=True)
class PersonMatch:
    volunteer: Volunteer
    distance_m: int
    busy: bool


def match_order(match: PersonMatch) -> tuple[bool, int, bool, str]:
    return (
        match.busy,
        match.distance_m,
        match.volunteer.example,
        match.volunteer.id,
    )


def nearest_people(
    center: GeoPoint,
    volunteers: Iterable[Volunteer],
    k: int,
    busy_ids: AbstractSet[str],
) -> list[PersonMatch]:
    matches = [
        PersonMatch(
            volunteer,
            round(haversine_m(center, volunteer.home)),
            volunteer.id in busy_ids,
        )
        for volunteer in volunteers
    ]
    matches.sort(key=match_order)
    return matches[:k]
