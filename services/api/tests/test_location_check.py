import io

import pytest
from PIL import Image

from casework.photo import GPS_IFD
from contracts import GeoPoint
from domain.evidence import location_ok
from tests.fakes import make_evidence, make_verdict
from tests.test_evidence_check import OBJECT, TARGET, FakeReader, World

METRES_PER_DEGREE = 111_194.9
TOLERANCE_M = 300


def north_of_target(metres: float) -> GeoPoint:
    return GeoPoint(lat=TARGET.lat + metres / METRES_PER_DEGREE, lon=TARGET.lon)


def photo_with_gps(point: GeoPoint) -> bytes:
    exif = Image.Exif()
    exif[GPS_IFD] = {
        1: "N",
        2: (point.lat, 0.0, 0.0),
        3: "E",
        4: (point.lon, 0.0, 0.0),
    }
    buffer = io.BytesIO()
    Image.new("RGB", (20, 10)).save(buffer, "JPEG", exif=exif)
    return buffer.getvalue()


def evidence_at(point, sample=False):
    return make_evidence(
        gcs_uri=f"gs://bucket-test/{OBJECT}", point=point, sample=sample
    )


def test_299_m_from_the_target_passes():
    assert location_ok(TARGET, north_of_target(299), TOLERANCE_M) is True


def test_301_m_from_the_target_fails():
    assert location_ok(TARGET, north_of_target(301), TOLERANCE_M) is False


def test_the_exif_point_wins_over_a_far_device_point():
    world = World(
        evidence=evidence_at(north_of_target(5_000)),
        photo=photo_with_gps(north_of_target(100)),
    )

    checked = world.check()

    assert checked.location_ok is True
    assert world.cases.get("c1").status != "human_review"


def test_the_exif_point_wins_over_a_near_device_point():
    world = World(
        evidence=evidence_at(north_of_target(10)),
        photo=photo_with_gps(north_of_target(5_000)),
    )

    checked = world.check()

    assert checked.location_ok is False
    assert world.cases.get("c1").status == "human_review"


def test_the_device_point_is_used_when_the_photo_has_no_gps():
    world = World(evidence=evidence_at(north_of_target(5_000)))

    checked = world.check()

    assert checked.location_ok is False
    assert "location mismatch" in checked.verdict.reasons
    assert world.cases.get("c1").status == "human_review"


def test_a_sample_photo_far_from_the_dam_goes_to_a_person():
    world = World(evidence=evidence_at(north_of_target(5_000), sample=True))

    world.check()

    assert world.cases.get("c1").status == "human_review"


@pytest.mark.parametrize(
    ("sample", "status"), [(False, "human_review"), (True, "resolved_pending_human")]
)
def test_a_missing_location_sends_only_a_real_photo_to_a_person(sample, status):
    world = World(
        evidence=evidence_at(None, sample=sample),
        reader=FakeReader(make_verdict(dam_state="intact")),
    )

    checked = world.check()

    assert checked.location_ok is None
    assert world.cases.get("c1").status == status
