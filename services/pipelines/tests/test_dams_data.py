import itertools
import json
import math

import pytest

from api_contracts import contracts
from tests.conftest import REPO

DATA = REPO / "data"
EARTH_RADIUS_M = 6_371_008.8
MAX_CANAL_DISTANCE_M = 100
TOP_CELLS = 10
EXPECTED_TOP_STATES = {"broken", "damaged", "intact"}


def load(name):
    return json.loads((DATA / name).read_text())["features"]


@pytest.fixture(scope="module")
def dams():
    return load("dams_riau_sample.geojson")


@pytest.fixture(scope="module")
def reference():
    return load("dams_riau_reference.geojson")


def of_kind(reference, kind):
    return [f for f in reference if f["properties"]["kind"] == kind]


def to_metres(lon, lat, origin_lat):
    x = math.radians(lon) * EARTH_RADIUS_M * math.cos(math.radians(origin_lat))
    y = math.radians(lat) * EARTH_RADIUS_M
    return x, y


def segment_distance(point, start, end):
    dx, dy = end[0] - start[0], end[1] - start[1]
    length_sq = dx * dx + dy * dy
    if length_sq == 0:
        return math.dist(point, start)
    t = ((point[0] - start[0]) * dx + (point[1] - start[1]) * dy) / length_sq
    t = max(0.0, min(1.0, t))
    return math.dist(point, (start[0] + t * dx, start[1] + t * dy))


def lines_of(geometry):
    if geometry["type"] == "LineString":
        return [geometry["coordinates"]]
    return geometry["coordinates"]


def distance_to_canal_m(dam, canal):
    lon, lat = dam["geometry"]["coordinates"]
    point = to_metres(lon, lat, lat)
    best = math.inf
    for line in lines_of(canal["geometry"]):
        projected = [to_metres(x, y, lat) for x, y in line]
        for start, end in itertools.pairwise(projected):
            best = min(best, segment_distance(point, start, end))
    return best


def inside(point, ring):
    x, y = point
    odd = False
    for (x1, y1), (x2, y2) in itertools.pairwise(ring):
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            odd = not odd
    return odd


def top_cell_of(dam, top_cells):
    lon, lat = dam["geometry"]["coordinates"]
    for cell in top_cells:
        if inside((lon, lat), cell["geometry"]["coordinates"][0]):
            return cell["properties"]
    return None


def test_between_30_and_60_dams_all_example_with_unique_ids(dams):
    ids = [d["properties"]["id"] for d in dams]
    assert 30 <= len(dams) <= 60
    assert len(set(ids)) == len(ids)
    assert all(d["properties"]["example"] is True for d in dams)


def test_every_dam_validates_as_a_dam_contract(dams):
    for feature in dams:
        lon, lat = feature["geometry"]["coordinates"]
        contracts.Dam.model_validate(
            {**feature["properties"], "point": {"lat": lat, "lon": lon}}
        )


def test_every_dam_is_within_100_m_of_its_own_canal(dams, reference):
    canals = {f["properties"]["dam_id"]: f for f in of_kind(reference, "canal")}
    assert set(canals) == {d["properties"]["id"] for d in dams}
    for dam in dams:
        canal = canals[dam["properties"]["id"]]
        assert canal["properties"]["osm_id"] == dam["properties"]["canal_osm_id"]
        assert distance_to_canal_m(dam, canal) <= MAX_CANAL_DISTANCE_M


def test_every_dam_is_inside_the_riau_focus_aoi(dams):
    aoi = json.loads((DATA / "aoi" / "riau_focus.geojson").read_text())
    ring = aoi["features"][0]["geometry"]["coordinates"][0]
    for dam in dams:
        assert inside(tuple(dam["geometry"]["coordinates"]), ring)


def test_dams_spread_over_the_grid(dams):
    longitudes = [d["geometry"]["coordinates"][0] for d in dams]
    latitudes = [d["geometry"]["coordinates"][1] for d in dams]
    assert max(longitudes) - min(longitudes) > 0.4
    assert max(latitudes) - min(latitudes) > 0.35


def test_exactly_three_dams_sit_in_top_ten_cells_with_one_state_each(dams, reference):
    top_cells = of_kind(reference, "top_cell")
    assert len(top_cells) == TOP_CELLS
    in_top = [
        (d["properties"]["last_state"], top_cell_of(d, top_cells))
        for d in dams
        if top_cell_of(d, top_cells) is not None
    ]
    assert len(in_top) == 3
    assert {state for state, _ in in_top} == EXPECTED_TOP_STATES
    assert len({cell["cell_id"] for _, cell in in_top}) == 3


def test_the_rest_of_the_dams_have_a_mix_of_states(dams):
    states = [d["properties"]["last_state"] for d in dams]
    assert {"intact", "damaged", "broken"} <= set(states)
    assert states.count("intact") > states.count("broken")
