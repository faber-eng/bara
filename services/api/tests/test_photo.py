import io

import pytest
from PIL import Image

from casework.photo import MAX_EDGE_PX, UnreadablePhoto, exif_point, prepare_photo
from contracts import GeoPoint

GPS_IFD = 0x8825


def jpeg(width: int, height: int, exif: Image.Exif | None = None) -> bytes:
    buffer = io.BytesIO()
    image = Image.new("RGB", (width, height), "olive")
    if exif is None:
        image.save(buffer, "JPEG")
    else:
        image.save(buffer, "JPEG", exif=exif)
    return buffer.getvalue()


def gps_exif(lat_ref: str, lat: tuple, lon_ref: str, lon: tuple) -> Image.Exif:
    exif = Image.Exif()
    exif[GPS_IFD] = {1: lat_ref, 2: lat, 3: lon_ref, 4: lon}
    return exif


def size_of(data: bytes) -> tuple[int, int]:
    return Image.open(io.BytesIO(data)).size


def test_a_large_photo_is_resized_to_the_max_edge():
    prepared = prepare_photo(jpeg(4000, 3000))

    assert size_of(prepared.data) == (MAX_EDGE_PX, 1200)
    assert prepared.mime_type == "image/jpeg"


def test_a_small_photo_keeps_its_size():
    prepared = prepare_photo(jpeg(800, 600))

    assert size_of(prepared.data) == (800, 600)


def test_a_png_is_sent_as_jpeg():
    buffer = io.BytesIO()
    Image.new("RGBA", (100, 50), (10, 20, 30, 128)).save(buffer, "PNG")

    prepared = prepare_photo(buffer.getvalue())

    assert prepared.mime_type == "image/jpeg"
    assert size_of(prepared.data) == (100, 50)


def test_bytes_that_are_not_an_image_are_refused():
    with pytest.raises(UnreadablePhoto):
        prepare_photo(b"not an image")


def test_the_exif_gps_point_is_read_in_degrees():
    exif = gps_exif("N", (0.0, 30.0, 0.0), "E", (101.0, 24.0, 36.0))

    point = exif_point(jpeg(10, 10, exif))

    assert point is not None
    assert point.lat == pytest.approx(0.5)
    assert point.lon == pytest.approx(101.41)


def test_south_and_west_refs_give_negative_degrees():
    exif = gps_exif("S", (2.0, 15.0, 0.0), "W", (10.0, 30.0, 0.0))

    point = exif_point(jpeg(10, 10, exif))

    assert point == GeoPoint(lat=-2.25, lon=-10.5)


def test_a_photo_without_gps_has_no_point():
    assert exif_point(jpeg(10, 10)) is None


def test_unreadable_bytes_have_no_point():
    assert exif_point(b"not an image") is None
