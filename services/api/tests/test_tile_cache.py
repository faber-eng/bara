import threading
import time

from tile_cache import TileUrlCache

KEY = ("reignition", "riau", "2026-W42")


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def test_an_entry_expires_after_the_ttl():
    clock = Clock()
    cache = TileUrlCache(ttl_seconds=3600, monotonic=clock)
    builds = []

    def build() -> str:
        builds.append(1)
        return f"url-{len(builds)}"

    assert cache.get_or_build(KEY, build) == "url-1"
    clock.now = 3599
    assert cache.get_or_build(KEY, build) == "url-1"
    clock.now = 3600
    assert cache.get_or_build(KEY, build) == "url-2"


def test_concurrent_cold_requests_make_one_build():
    cache = TileUrlCache()
    builds = []

    def build() -> str:
        builds.append(1)
        time.sleep(0.2)
        return "url"

    results: list[str] = []
    threads = [
        threading.Thread(target=lambda: results.append(cache.get_or_build(KEY, build)))
        for _ in range(8)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert results == ["url"] * 8
    assert len(builds) == 1


def test_different_keys_build_in_parallel():
    cache = TileUrlCache()
    started = time.perf_counter()

    def build() -> str:
        time.sleep(0.3)
        return "url"

    threads = [
        threading.Thread(target=cache.get_or_build, args=((layer, "riau", "w"), build))
        for layer in ("a", "b", "c")
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert time.perf_counter() - started < 0.8


def test_a_build_that_raises_leaves_nothing_cached():
    cache = TileUrlCache()

    def fail() -> str:
        raise RuntimeError("boom")

    try:
        cache.get_or_build(KEY, fail)
    except RuntimeError:
        pass

    assert cache.get_or_build(KEY, lambda: "url") == "url"


def test_waiters_share_the_failure_of_the_build_in_flight():
    cache = TileUrlCache()
    builds = []

    def fail() -> str:
        builds.append(1)
        time.sleep(0.2)
        raise RuntimeError("boom")

    errors: list[str] = []

    def call():
        try:
            cache.get_or_build(KEY, fail)
        except RuntimeError as error:
            errors.append(str(error))

    threads = [threading.Thread(target=call) for _ in range(6)]
    started = time.perf_counter()
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert errors == ["boom"] * 6
    assert len(builds) == 1
    assert time.perf_counter() - started < 0.6
