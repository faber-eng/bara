import math
from collections.abc import Iterable

from contracts import Dam, GeoPoint, NearbyDam

EARTH_RADIUS_M = 6_371_000


def haversine_m(a: GeoPoint, b: GeoPoint) -> float:
    lat_a, lat_b = math.radians(a.lat), math.radians(b.lat)
    d_lat = lat_b - lat_a
    d_lon = math.radians(b.lon - a.lon)
    h = (
        math.sin(d_lat / 2) ** 2
        + math.cos(lat_a) * math.cos(lat_b) * math.sin(d_lon / 2) ** 2
    )
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(h))


def nearby(center: GeoPoint, dams: Iterable[Dam], radius_m: float) -> list[NearbyDam]:
    distances = [(haversine_m(center, dam.point), dam) for dam in dams]
    within = [(distance, dam) for distance, dam in distances if distance <= radius_m]
    within.sort(key=lambda pair: (pair[0], pair[1].id))
    return [
        NearbyDam(dam_id=dam.id, distance_m=round(distance), last_state=dam.last_state)
        for distance, dam in within
    ]
