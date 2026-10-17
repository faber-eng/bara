from ratelimit import FailureLimiter, RequestLimiter


class FakeTime:
    def __init__(self):
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def make_limiter():
    time = FakeTime()
    return FailureLimiter(max_failures=5, window_seconds=900, clock=time), time


def fail(limiter, key, times):
    for _ in range(times):
        limiter.record_failure(key)


def test_a_new_key_is_not_blocked():
    limiter, _ = make_limiter()

    assert limiter.retry_after("u1") == 0


def test_four_failures_do_not_block():
    limiter, _ = make_limiter()
    fail(limiter, "u1", 4)

    assert limiter.retry_after("u1") == 0


def test_the_fifth_failure_blocks_with_the_seconds_left():
    limiter, time = make_limiter()
    fail(limiter, "u1", 5)
    time.now += 100

    assert limiter.retry_after("u1") == 800


def test_another_key_is_unaffected():
    limiter, _ = make_limiter()
    fail(limiter, "u1", 5)

    assert limiter.retry_after("u2") == 0


def test_failures_expire_after_the_window():
    limiter, time = make_limiter()
    fail(limiter, "u1", 5)
    time.now += 900

    assert limiter.retry_after("u1") == 0


def test_a_success_clears_the_count():
    limiter, _ = make_limiter()
    fail(limiter, "u1", 4)
    limiter.clear("u1")
    limiter.record_failure("u1")

    assert limiter.retry_after("u1") == 0


def test_old_failures_drop_out_one_by_one():
    limiter, time = make_limiter()
    limiter.record_failure("u1")
    time.now += 500
    fail(limiter, "u1", 4)
    assert limiter.retry_after("u1") == 400

    time.now += 400

    assert limiter.retry_after("u1") == 0


def test_the_request_limiter_allows_the_quota_then_returns_the_wait():
    time = FakeTime()
    limiter = RequestLimiter(max_requests=3, window_seconds=60, clock=time)

    assert [limiter.hit("ip") for _ in range(3)] == [0, 0, 0]
    time.now += 10
    assert limiter.hit("ip") == 50


def test_the_request_limiter_frees_the_quota_when_the_window_passes():
    time = FakeTime()
    limiter = RequestLimiter(max_requests=1, window_seconds=60, clock=time)
    limiter.hit("ip")

    time.now += 60

    assert limiter.hit("ip") == 0


def test_the_request_limiter_counts_each_key_apart():
    limiter = RequestLimiter(max_requests=1, window_seconds=60, clock=FakeTime())
    limiter.hit("a")

    assert limiter.hit("b") == 0
    assert limiter.hit("a") > 0


def test_the_request_limiter_keeps_a_bounded_number_of_keys():
    limiter = RequestLimiter(
        max_requests=1, window_seconds=60, clock=FakeTime(), max_keys=3
    )
    for key in ["a", "b", "c", "d"]:
        limiter.hit(key)

    assert limiter.hit("a") == 0
