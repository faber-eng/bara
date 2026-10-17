import io
from dataclasses import dataclass

from PIL import Image, ImageOps, UnidentifiedImageError

from contracts import GeoPoint

MAX_EDGE_PX = 1600
JPEG_QUALITY = 85
GPS_IFD = 0x8825
LAT_REF, LAT, LON_REF, LON = 1, 2, 3, 4
NEGATIVE_REFS = frozenset({"S", "W"})


class UnreadablePhoto(Exception):
    pass


@dataclass(frozen=True)
class PreparedPhoto:
    data: bytes
    mime_type: str


def open_image(data: bytes) -> Image.Image:
    try:
        image = Image.open(io.BytesIO(data))
        image.load()
    except (UnidentifiedImageError, OSError) as error:
        raise UnreadablePhoto("the file is not a readable image") from error
    return image


def prepare_photo(data: bytes) -> PreparedPhoto:
    image = ImageOps.exif_transpose(open_image(data)).convert("RGB")
    image.thumbnail((MAX_EDGE_PX, MAX_EDGE_PX))
    buffer = io.BytesIO()
    image.save(buffer, "JPEG", quality=JPEG_QUALITY)
    return PreparedPhoto(buffer.getvalue(), "image/jpeg")


def degrees(parts: tuple, ref: str) -> float:
    whole, minutes, seconds = (float(part) for part in parts)
    value = whole + minutes / 60 + seconds / 3600
    if ref in NEGATIVE_REFS:
        return -value
    return value


def exif_point(data: bytes) -> GeoPoint | None:
    try:
        gps = Image.open(io.BytesIO(data)).getexif().get_ifd(GPS_IFD)
    except (UnidentifiedImageError, OSError):
        return None
    if not all(key in gps for key in (LAT_REF, LAT, LON_REF, LON)):
        return None
    try:
        return GeoPoint(
            lat=degrees(gps[LAT], gps[LAT_REF]), lon=degrees(gps[LON], gps[LON_REF])
        )
    except (TypeError, ValueError, ZeroDivisionError):
        return None
