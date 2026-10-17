import threading
import time
from collections import OrderedDict
from collections.abc import Callable

from contracts import AreaRanking

CACHE_TTL_SECONDS = 3600.0
CACHE_MAX_ENTRIES = 256


class AreaRankingCache:
    def __init__(
        self,
        ttl_seconds: float = CACHE_TTL_SECONDS,
        max_entries: int = CACHE_MAX_ENTRIES,
        clock: Callable[[], float] = time.monotonic,
    ):
        self._ttl = ttl_seconds
        self._max_entries = max_entries
        self._clock = clock
        self._lock = threading.Lock()
        self._entries: OrderedDict[str, tuple[float, AreaRanking]] = OrderedDict()

    def get(self, key: str) -> AreaRanking | None:
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                return None
            expires_at, ranking = entry
            if expires_at <= self._clock():
                del self._entries[key]
                return None
            self._entries.move_to_end(key)
            return ranking

    def put(self, key: str, ranking: AreaRanking) -> None:
        with self._lock:
            self._entries[key] = (self._clock() + self._ttl, ranking)
            self._entries.move_to_end(key)
            while len(self._entries) > self._max_entries:
                self._entries.popitem(last=False)
