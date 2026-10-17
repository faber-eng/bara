from ratelimit import FailureLimiter


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
