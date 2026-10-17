from contracts import GeoPoint
from domain.people import nearest_people
from tests.fakes import make_volunteer

CENTER = GeoPoint(lat=0.5, lon=101.4)


def at(lon: float) -> GeoPoint:
    return GeoPoint(lat=0.5, lon=lon)


def ids(found) -> list[str]:
    return [match.volunteer.id for match in found]


def test_people_are_ordered_by_distance():
    far = make_volunteer(id="far", home=at(101.45))
    near = make_volunteer(id="near", home=at(101.41))

    found = nearest_people(CENTER, [far, near], 3)

    assert ids(found) == ["near", "far"]
    assert found[0].distance_m < found[1].distance_m


def test_k_caps_the_result():
    people = [make_volunteer(id=f"v{i}", home=at(101.4 + i / 100)) for i in range(5)]

    assert ids(nearest_people(CENTER, people, 2)) == ["v0", "v1"]


def test_no_people_gives_an_empty_list():
    assert nearest_people(CENTER, [], 3) == []


def test_a_real_volunteer_wins_a_distance_tie_then_the_id_decides():
    sample_a = make_volunteer(id="a", home=at(101.41), example=True)
    real = make_volunteer(id="z", home=at(101.41), example=False)
    sample_b = make_volunteer(id="b", home=at(101.41), example=True)

    found = nearest_people(CENTER, [sample_b, sample_a, real], 3)

    assert ids(found) == ["z", "a", "b"]


def test_distance_is_whole_metres_and_the_example_label_is_kept():
    sample = make_volunteer(id="s", home=at(101.41), example=True)

    [match] = nearest_people(CENTER, [sample], 1)

    assert match.distance_m == round(match.distance_m)
    assert isinstance(match.distance_m, int)
    assert match.volunteer.example is True
