import hashlib
import itertools
import json
import math
from dataclasses import dataclass

from domain.geo import EARTH_RADIUS_M

MAX_AREA_KM2 = 2500.0
MAX_VERTICES = 500
COORD_DECIMALS = 5
M2_PER_KM2 = 1_000_000


class InvalidPolygon(ValueError):
    pass


class PolygonTooLarge(ValueError):
    def __init__(self, area_km2: float):
        super().__init__(f"polygon covers {area_km2:.0f} km2, the limit is 2500 km2")
        self.area_km2 = area_km2


@dataclass(frozen=True)
class BoundingBox:
    west: float
    south: float
    east: float
    north: float

    def overlaps(self, other: "BoundingBox") -> bool:
        return (
            self.west <= other.east
            and other.west <= self.east
            and self.south <= other.north
            and other.south <= self.north
        )


@dataclass(frozen=True)
class AreaPolygon:
    ring: tuple[tuple[float, float], ...]
    area_km2: float
    box: BoundingBox

    @property
    def geometry(self) -> dict:
        return {"type": "Polygon", "coordinates": [[list(p) for p in self.ring]]}

    @property
    def digest(self) -> str:
        canonical = json.dumps(canonical_ring(self.ring), separators=(",", ":"))
        return hashlib.sha256(canonical.encode()).hexdigest()


def signed_area(ring) -> float:
    return sum(a[0] * b[1] - b[0] * a[1] for a, b in itertools.pairwise(ring))


def canonical_ring(ring) -> list[tuple[float, float]]:
    corners = list(ring[:-1])
    if signed_area(ring) < 0:
        corners.reverse()
    start = corners.index(min(corners))
    rotated = corners[start:] + corners[:start]
    return [*rotated, rotated[0]]


def read_position(raw: object) -> tuple[float, float]:
    if not isinstance(raw, list) or len(raw) < 2:
        raise InvalidPolygon("a position must be [lon, lat]")
    lon, lat = raw[0], raw[1]
    for value in (lon, lat):
        if isinstance(value, bool) or not isinstance(value, int | float):
            raise InvalidPolygon("a position must hold numbers")
        if not math.isfinite(value):
            raise InvalidPolygon("a position must be finite")
    if not -180 <= lon <= 180 or not -90 <= lat <= 90:
        raise InvalidPolygon("a position is outside longitude or latitude range")
    return round(float(lon), COORD_DECIMALS), round(float(lat), COORD_DECIMALS)


def read_ring(raw: object) -> list[tuple[float, float]]:
    if not isinstance(raw, dict) or raw.get("type") != "Polygon":
        raise InvalidPolygon("the body must be a GeoJSON Polygon")
    rings = raw.get("coordinates")
    if not isinstance(rings, list) or len(rings) != 1:
        raise InvalidPolygon("the polygon must have one ring and no holes")
    ring = rings[0]
    if not isinstance(ring, list) or not 4 <= len(ring) <= MAX_VERTICES + 1:
        raise InvalidPolygon(f"the ring must have 4 to {MAX_VERTICES + 1} positions")
    positions = [read_position(position) for position in ring]
    if positions[0] != positions[-1]:
        raise InvalidPolygon("the ring must be closed")
    return positions


def ring_area_km2(ring: list[tuple[float, float]]) -> float:
    total = 0.0
    for (lon_a, lat_a), (lon_b, lat_b) in itertools.pairwise(ring):
        delta = math.radians(lon_b - lon_a)
        total += delta * (
            2 + math.sin(math.radians(lat_a)) + math.sin(math.radians(lat_b))
        )
    return abs(total) * EARTH_RADIUS_M**2 / 2 / M2_PER_KM2


def orientation(a, b, c) -> float:
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def segments_cross(a, b, c, d) -> bool:
    first = orientation(a, b, c) * orientation(a, b, d)
    second = orientation(c, d, a) * orientation(c, d, b)
    return first < 0 and second < 0


def has_self_crossing(ring: list[tuple[float, float]]) -> bool:
    segments = list(itertools.pairwise(ring))
    for i, (a, b) in enumerate(segments):
        for c, d in segments[i + 2 :]:
            if segments_cross(a, b, c, d):
                return True
    return False


def bounding_box(ring: list[tuple[float, float]]) -> BoundingBox:
    lons = [lon for lon, _ in ring]
    lats = [lat for _, lat in ring]
    return BoundingBox(min(lons), min(lats), max(lons), max(lats))


def parse_polygon(raw: object) -> AreaPolygon:
    ring = read_ring(raw)
    if has_self_crossing(ring):
        raise InvalidPolygon("the ring must not cross itself")
    area = round(ring_area_km2(ring), 2)
    if area <= 0:
        raise InvalidPolygon("the polygon has no area")
    if area > MAX_AREA_KM2:
        raise PolygonTooLarge(area)
    return AreaPolygon(tuple(ring), area, bounding_box(ring))
