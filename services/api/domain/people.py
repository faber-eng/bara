from collections.abc import Iterable
from dataclasses import dataclass

from contracts import GeoPoint, Volunteer
from domain.geo import haversine_m


@dataclass(frozen=True)
class PersonMatch:
    volunteer: Volunteer
    distance_m: int


def match_order(match: PersonMatch) -> tuple[int, bool, str]:
    return (match.distance_m, match.volunteer.example, match.volunteer.id)


def nearest_people(
    center: GeoPoint, volunteers: Iterable[Volunteer], k: int
) -> list[PersonMatch]:
    matches = [
        PersonMatch(volunteer, round(haversine_m(center, volunteer.home)))
        for volunteer in volunteers
    ]
    matches.sort(key=match_order)
    return matches[:k]
