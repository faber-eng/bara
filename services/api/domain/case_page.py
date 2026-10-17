import base64
import binascii
from dataclasses import dataclass
from datetime import datetime

from contracts import Case

DEFAULT_LIMIT = 50
MAX_LIMIT = 200


class InvalidCursor(Exception):
    pass


@dataclass(frozen=True)
class CasePage:
    cases: list[Case]
    next_cursor: str | None


def encode_cursor(case: Case) -> str:
    raw = f"{case.opened_at.isoformat()}|{case.id}"
    return base64.urlsafe_b64encode(raw.encode()).decode()


def decode_cursor(cursor: str) -> tuple[datetime, str]:
    try:
        raw = base64.urlsafe_b64decode(cursor.encode()).decode()
        opened_at, case_id = raw.split("|", 1)
        position = datetime.fromisoformat(opened_at)
    except (binascii.Error, UnicodeDecodeError, ValueError) as error:
        raise InvalidCursor(cursor) from error
    if position.utcoffset() is None:
        raise InvalidCursor(cursor)
    return position, case_id


def comes_after(case: Case, position: tuple[datetime, str]) -> bool:
    return (case.opened_at, case.id) < position


def page_of(newest_first: list[Case], limit: int, cursor: str | None) -> CasePage:
    remaining = newest_first
    if cursor is not None:
        position = decode_cursor(cursor)
        remaining = [case for case in newest_first if comes_after(case, position)]
    page = remaining[:limit]
    if len(remaining) <= limit:
        return CasePage(page, None)
    return CasePage(page, encode_cursor(page[-1]))
