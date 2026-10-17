import threading
import time
from collections.abc import Callable
from concurrent.futures import Future
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
        self._in_flight: dict[TileKey, Future[str]] = {}
        self._guard = threading.Lock()

    def get_or_build(self, key: TileKey, build: Callable[[], str]) -> str:
        fresh, flight, owner = self._join(key)
        if fresh is not None:
            return fresh
        if not owner:
            return flight.result()
        return self._build(key, build, flight)

    def _build(
        self, key: TileKey, build: Callable[[], str], flight: Future[str]
    ) -> str:
        try:
            url = build()
            self._store(key, url)
        except BaseException as error:
            flight.set_exception(error)
            raise
        else:
            flight.set_result(url)
            return url
        finally:
            self._leave(key)

    def _join(self, key: TileKey) -> tuple[str | None, Future[str], bool]:
        with self._guard:
            entry = self._entries.get(key)
            if entry is not None and entry.expires_at > self._monotonic():
                return entry.url, Future(), False
            flight = self._in_flight.get(key)
            if flight is not None:
                return None, flight, False
            flight = Future()
            self._in_flight[key] = flight
            return None, flight, True

    def _leave(self, key: TileKey) -> None:
        with self._guard:
            self._in_flight.pop(key, None)

    def _store(self, key: TileKey, url: str) -> None:
        now = self._monotonic()
        with self._guard:
            self._entries = {
                k: entry for k, entry in self._entries.items() if entry.expires_at > now
            }
            self._entries[key] = CachedUrl(url, now + self._ttl)
