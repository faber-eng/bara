from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Protocol

from contracts import ClockSettings

SECONDS_PER_HOUR = 3600


class ClockStore(Protocol):
    def get(self) -> ClockSettings | None: ...

    def put(self, settings: ClockSettings) -> None: ...


def require_aware(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("datetime must be timezone-aware")
    return value


def is_due(deadline_at: datetime, now: datetime) -> bool:
    return require_aware(deadline_at) <= require_aware(now)


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
        if hours <= 0:
            raise ValueError("advance hours must be greater than zero")
        added = round(hours * SECONDS_PER_HOUR)
        self._save(self.offset_seconds() + added, updated_by)

    def reset(self, updated_by: str) -> None:
        self._save(0, updated_by)

    def _save(self, offset_seconds: int, updated_by: str) -> None:
        self._store.put(
            ClockSettings(offset_seconds=offset_seconds, updated_by=updated_by)
        )
