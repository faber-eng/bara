import pytest

from contracts import GeoPoint
from domain.geo import haversine_m, nearby
from tests.fakes import make_dam

CENTER = GeoPoint(lat=0.5, lon=101.4)


def test_same_point_is_zero_metres():
    assert haversine_m(CENTER, CENTER) == 0


def test_a_tenth_of_a_degree_of_longitude_at_the_equator_is_about_11_km():
    east = GeoPoint(lat=0.5, lon=101.5)

    assert haversine_m(CENTER, east) == pytest.approx(11_120, rel=0.01)


def test_distance_is_symmetric():
    other = GeoPoint(lat=0.61, lon=101.33)

    assert haversine_m(CENTER, other) == haversine_m(other, CENTER)


def test_a_dam_exactly_on_the_radius_is_included_and_one_metre_out_is_not():
    edge = make_dam(id="edge", point=GeoPoint(lat=0.5, lon=101.409))
    radius = haversine_m(CENTER, edge.point)

    assert [d.dam_id for d in nearby(CENTER, [edge], radius)] == ["edge"]
    assert nearby(CENTER, [edge], radius - 1) == []


def test_nearby_dams_are_sorted_nearest_first_with_whole_metres():
    far = make_dam(id="far", point=GeoPoint(lat=0.5, lon=101.408))
    near = make_dam(id="near", point=GeoPoint(lat=0.5, lon=101.401))
    outside = make_dam(id="outside", point=GeoPoint(lat=0.5, lon=101.5))

    found = nearby(CENTER, [far, outside, near], 1_000)

    assert [d.dam_id for d in found] == ["near", "far"]
    assert [d.distance_m for d in found] == [
        round(haversine_m(CENTER, near.point)),
        round(haversine_m(CENTER, far.point)),
    ]
    assert found[0].last_state == near.last_state
