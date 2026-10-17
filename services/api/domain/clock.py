import math
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Protocol

from contracts import ClockSettings

SECONDS_PER_HOUR = 3600
MAX_ADVANCE_HOURS = 24 * 365
MAX_TOTAL_SECONDS = 10 * 365 * 24 * SECONDS_PER_HOUR


class ClockStore(Protocol):
    def get(self) -> ClockSettings | None: ...

    def put(self, settings: ClockSettings) -> None: ...

    def add_seconds(self, seconds: int, updated_by: str) -> None: ...


def require_aware(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("datetime must be timezone-aware")
    return value


def is_due(deadline_at: datetime, now: datetime) -> bool:
    return require_aware(deadline_at) <= require_aware(now)


def advance_seconds(hours: float) -> int:
    if not math.isfinite(hours):
        raise ValueError("advance hours must be finite")
    if hours <= 0:
        raise ValueError("advance hours must be greater than zero")
    if hours > MAX_ADVANCE_HOURS:
        raise ValueError(f"advance hours must not exceed {MAX_ADVANCE_HOURS}")
    return round(hours * SECONDS_PER_HOUR)


class Clock:
    def __init__(self, store: ClockStore, utcnow: Callable[[], datetime]):
        self._store = store
        self._utcnow = utcnow

    def offset_seconds(self) -> int:
        settings = self._store.get()
        if settings is None:
            return 0
        return settings.offset_seconds

    def now(self) -> datetime:
        real_now = require_aware(self._utcnow())
        return real_now + timedelta(seconds=self.offset_seconds())

    def advance(self, hours: float, updated_by: str) -> None:
        added = advance_seconds(hours)
        if self.offset_seconds() + added > MAX_TOTAL_SECONDS:
            raise ValueError("total clock offset must not exceed 10 years")
        self._store.add_seconds(added, updated_by)

    def reset(self, updated_by: str) -> None:
        self._save(0, updated_by)

    def _save(self, offset_seconds: int, updated_by: str) -> None:
        self._store.put(
            ClockSettings(offset_seconds=offset_seconds, updated_by=updated_by)
        )
