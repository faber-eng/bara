from contracts import GeoPoint
from domain.escalation import MAX_PACK_PHOTOS, map_url, pack_photos, pick_contact
from tests.fakes import make_contact, make_evidence, make_verdict


def test_the_map_url_is_a_maps_search_on_the_point():
    url = map_url(GeoPoint(lat=0.5331, lon=102.2047))

    assert url == "https://www.google.com/maps/search/?api=1&query=0.5331,102.2047"


def test_the_pack_keeps_photos_only_checked_ones_first():
    unchecked = make_evidence(id="e1", gcs_uri="gs://b/e1.jpg")
    checked = make_evidence(id="e2", gcs_uri="gs://b/e2.jpg", verdict=make_verdict())
    voice = make_evidence(id="e3", kind="audio", gcs_uri="gs://b/e3.webm")

    assert pack_photos([unchecked, voice, checked]) == [
        "gs://b/e2.jpg",
        "gs://b/e1.jpg",
    ]


def test_the_pack_holds_at_most_the_photo_cap():
    many = [make_evidence(id=f"e{i}", gcs_uri=f"gs://b/e{i}.jpg") for i in range(9)]

    assert len(pack_photos(many)) == MAX_PACK_PHOTOS


def test_a_real_contact_wins_over_an_example_one():
    example = make_contact(id="a-example", example=True)
    real = make_contact(id="z-real", example=False)

    assert pick_contact([example, real], example_case=False) == real


def test_contacts_of_the_same_kind_are_picked_by_id():
    first = make_contact(id="a")
    second = make_contact(id="b")

    assert pick_contact([second, first], example_case=False) == first


def test_no_contact_picks_none():
    assert pick_contact([], example_case=False) is None


def test_an_example_case_never_goes_to_a_real_contact():
    real = make_contact(id="a-real", example=False)
    example = make_contact(id="z-example", example=True)

    assert pick_contact([real, example], example_case=True) == example
    assert pick_contact([real], example_case=True) is None
