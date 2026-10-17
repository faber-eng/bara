import math
import time
from collections import defaultdict, deque
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
