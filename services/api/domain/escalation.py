from collections.abc import Sequence

from contracts import Contact, Evidence, GeoPoint

MAX_PACK_PHOTOS = 4
MAPS_SEARCH = "https://www.google.com/maps/search/?api=1&query="


def map_url(point: GeoPoint) -> str:
    return f"{MAPS_SEARCH}{point.lat},{point.lon}"


def photo_order(evidence: Evidence) -> tuple[bool, str]:
    return (evidence.verdict is None, evidence.id)


def pack_photos(evidence: Sequence[Evidence]) -> list[str]:
    photos = sorted(
        (item for item in evidence if item.kind == "photo"), key=photo_order
    )
    return [item.gcs_uri for item in photos[:MAX_PACK_PHOTOS]]


def contact_order(contact: Contact) -> tuple[bool, str]:
    return (contact.example, contact.id)


def may_receive(contact: Contact, example_case: bool) -> bool:
    if example_case:
        return contact.example
    return True


def pick_contact(contacts: Sequence[Contact], example_case: bool) -> Contact | None:
    allowed = [item for item in contacts if may_receive(item, example_case)]
    if not allowed:
        return None
    return min(allowed, key=contact_order)
