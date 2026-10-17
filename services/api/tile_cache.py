import threading
import time
from collections.abc import Callable
from dataclasses import dataclass

TILE_URL_TTL_SECONDS = 3600

TileKey = tuple[str, str, str]


@dataclass(frozen=True)
class CachedUrl:
    url: str
    expires_at: float


class TileUrlCache:
    def __init__(
        self,
        ttl_seconds: float = TILE_URL_TTL_SECONDS,
        monotonic: Callable[[], float] = time.monotonic,
    ):
        self._ttl = ttl_seconds
        self._monotonic = monotonic
        self._entries: dict[TileKey, CachedUrl] = {}
        self._locks: dict[TileKey, threading.Lock] = {}
        self._guard = threading.Lock()

    def get_or_build(self, key: TileKey, build: Callable[[], str]) -> str:
        fresh = self._fresh(key)
        if fresh is not None:
            return fresh
        with self._lock_for(key):
            fresh = self._fresh(key)
            if fresh is not None:
                return fresh
            url = build()
            self._store(key, url)
            return url

    def _fresh(self, key: TileKey) -> str | None:
        entry = self._entries.get(key)
        if entry is None or entry.expires_at <= self._monotonic():
            return None
        return entry.url

    def _lock_for(self, key: TileKey) -> threading.Lock:
        with self._guard:
            return self._locks.setdefault(key, threading.Lock())

    def _store(self, key: TileKey, url: str) -> None:
        now = self._monotonic()
        with self._guard:
            self._entries = {
                k: entry for k, entry in self._entries.items() if entry.expires_at > now
            }
            self._entries[key] = CachedUrl(url, now + self._ttl)
