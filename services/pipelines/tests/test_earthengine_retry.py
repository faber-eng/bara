import ee
import pytest

from adapters.earthengine import with_retries


class FlakyCall:
    def __init__(self, failures: int):
        self.failures = failures
        self.calls = 0

    def __call__(self) -> str:
        self.calls += 1
        if self.calls <= self.failures:
            raise ee.EEException("Too many concurrent aggregations.")
        return "page"


def test_a_call_that_fails_then_succeeds_is_retried_with_a_growing_wait():
    waits: list[float] = []
    call = FlakyCall(failures=2)

    assert with_retries(call, attempts=3, wait=waits.append) == "page"
    assert call.calls == 3
    assert waits == [5.0, 10.0]


def test_the_last_failure_is_raised():
    call = FlakyCall(failures=3)

    with pytest.raises(ee.EEException):
        with_retries(call, attempts=3, wait=lambda _: None)
    assert call.calls == 3


def test_other_errors_are_not_retried():
    def broken() -> str:
        raise KeyError("features")

    with pytest.raises(KeyError):
        with_retries(broken, attempts=3, wait=lambda _: None)
