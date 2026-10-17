import math
import threading
import time
from collections import OrderedDict, defaultdict, deque
from collections.abc import Callable


class FailureLimiter:
    def __init__(
        self,
        max_failures: int,
        window_seconds: float,
        clock: Callable[[], float] = time.monotonic,
    ):
        self._max_failures = max_failures
        self._window_seconds = window_seconds
        self._clock = clock
        self._failures: dict[str, deque[float]] = defaultdict(deque)

    def record_failure(self, key: str) -> None:
        self._failures[key].append(self._clock())

    def clear(self, key: str) -> None:
        self._failures.pop(key, None)

    def retry_after(self, key: str) -> int:
        recent = self._recent(key)
        if len(recent) < self._max_failures:
            return 0
        release_at = recent[0] + self._window_seconds
        return max(1, math.ceil(release_at - self._clock()))

    def _recent(self, key: str) -> deque[float]:
        failures = self._failures[key]
        cutoff = self._clock() - self._window_seconds
        while failures and failures[0] <= cutoff:
            failures.popleft()
        if not failures:
            self._failures.pop(key, None)
        return failures


MAX_TRACKED_KEYS = 10_000


class RequestLimiter:
    def __init__(
        self,
        max_requests: int,
        window_seconds: float,
        clock: Callable[[], float] = time.monotonic,
        max_keys: int = MAX_TRACKED_KEYS,
    ):
        self._max_requests = max_requests
        self._window_seconds = window_seconds
        self._clock = clock
        self._max_keys = max_keys
        self._lock = threading.Lock()
        self._hits: OrderedDict[str, deque[float]] = OrderedDict()

    def hit(self, key: str) -> int:
        with self._lock:
            now = self._clock()
            hits = self._hits.pop(key, None) or deque()
            self._hits[key] = hits
            self._evict_over_limit()
            return self._record(hits, now)

    def _record(self, hits: deque[float], now: float) -> int:
        cutoff = now - self._window_seconds
        while hits and hits[0] <= cutoff:
            hits.popleft()
        if len(hits) >= self._max_requests:
            return max(1, math.ceil(hits[0] + self._window_seconds - now))
        hits.append(now)
        return 0

    def _evict_over_limit(self) -> None:
        while len(self._hits) > self._max_keys:
            self._hits.popitem(last=False)
