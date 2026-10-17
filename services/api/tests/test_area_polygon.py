import pytest

from domain.area_polygon import (
    InvalidPolygon,
    PolygonTooLarge,
    parse_polygon,
)


def square(west, south, side):
    east, north = west + side, south + side
    ring = [[west, south], [east, south], [east, north], [west, north], [west, south]]
    return {"type": "Polygon", "coordinates": [ring]}


def test_a_ten_by_ten_km_square_near_the_equator_is_about_100_km2():
    polygon = parse_polygon(square(102.0, 0.5, 0.09))

    assert polygon.area_km2 == pytest.approx(100, rel=0.03)


def test_more_than_2500_km2_is_refused_with_the_area():
    with pytest.raises(PolygonTooLarge) as caught:
        parse_polygon(square(102.0, 0.0, 0.6))

    assert caught.value.area_km2 > 2500


def test_exactly_inside_the_limit_is_accepted():
    assert parse_polygon(square(102.0, 0.0, 0.44)).area_km2 < 2500


@pytest.mark.parametrize(
    "raw",
    [
        None,
        {"type": "Point", "coordinates": [1, 2]},
        {"type": "Polygon", "coordinates": []},
        {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [0, 0]]]},
        {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1]]]},
        {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 91], [0, 0]]]},
        {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, "x"], [0, 0]]]},
        {"type": "Polygon", "coordinates": [[[0, 0], [0.1, 0], [0.2, 0], [0, 0]]]},
        {
            "type": "Polygon",
            "coordinates": [[[0, 0], [0.1, 0.1], [0.1, 0], [0, 0.1], [0, 0]]],
        },
    ],
)
def test_a_malformed_or_crossing_ring_is_invalid(raw):
    with pytest.raises(InvalidPolygon):
        parse_polygon(raw)


def test_a_ring_with_holes_is_invalid():
    outer = square(102.0, 0.5, 0.09)["coordinates"][0]
    hole = square(102.02, 0.52, 0.02)["coordinates"][0]

    with pytest.raises(InvalidPolygon):
        parse_polygon({"type": "Polygon", "coordinates": [outer, hole]})


def test_the_same_shape_hashes_the_same_and_a_moved_shape_does_not():
    a = parse_polygon(square(102.0, 0.5, 0.09))
    same = parse_polygon(square(102.000001, 0.5, 0.09))
    moved = parse_polygon(square(102.01, 0.5, 0.09))

    assert a.digest == same.digest
    assert a.digest != moved.digest
    assert len(a.digest) == 64


def test_the_box_overlap_check():
    a = parse_polygon(square(102.0, 0.5, 0.09)).box
    b = parse_polygon(square(102.05, 0.55, 0.09)).box
    far = parse_polygon(square(110.0, 0.5, 0.09)).box

    assert a.overlaps(b)
    assert not a.overlaps(far)


def test_a_polygon_that_rounds_to_zero_km2_is_invalid():
    with pytest.raises(InvalidPolygon):
        parse_polygon(square(102.0, 0.5, 0.0004))


def test_a_rotated_or_reversed_ring_hashes_the_same():
    ring = square(102.0, 0.5, 0.09)["coordinates"][0]
    rotated = ring[1:-1] + ring[:1] + ring[1:2]
    reversed_ring = list(reversed(ring))

    base = parse_polygon({"type": "Polygon", "coordinates": [ring]}).digest

    assert parse_polygon({"type": "Polygon", "coordinates": [rotated]}).digest == base
    assert (
        parse_polygon({"type": "Polygon", "coordinates": [reversed_ring]}).digest
        == base
    )
