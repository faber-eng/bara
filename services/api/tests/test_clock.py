import math
from datetime import UTC, datetime, timedelta

import pytest

from contracts import ClockSettings
from domain.clock import Clock, is_due
from tests.fakes import InMemoryClockStore

REAL_NOW = datetime(2026, 10, 17, 12, 0, tzinfo=UTC)


def make_clock(offset_seconds=0, store=None):
    store = store or InMemoryClockStore(
        ClockSettings(offset_seconds=offset_seconds, updated_by="seed")
    )
    return Clock(store, lambda: REAL_NOW), store


def test_now_is_utcnow_plus_the_offset():
    clock, _ = make_clock(offset_seconds=3600)

    assert clock.now() == REAL_NOW + timedelta(hours=1)


def test_now_is_timezone_aware_utc():
    clock, _ = make_clock()

    assert clock.now().utcoffset() == timedelta(0)


def test_with_no_stored_settings_the_offset_is_zero():
    clock, _ = make_clock(store=InMemoryClockStore(None))

    assert clock.now() == REAL_NOW


def test_advance_48_makes_a_47h_deadline_due_and_a_49h_deadline_not_due():
    clock, _ = make_clock()
    soon = REAL_NOW + timedelta(hours=47)
    later = REAL_NOW + timedelta(hours=49)

    assert is_due(soon, clock.now()) is False
    clock.advance(48, "judge-1")

    assert is_due(soon, clock.now()) is True
    assert is_due(later, clock.now()) is False


def test_a_deadline_equal_to_now_is_due():
    assert is_due(REAL_NOW, REAL_NOW) is True


def test_advances_accumulate_and_persist_through_the_store():
    clock, store = make_clock()

    clock.advance(6, "judge-1")
    clock.advance(24, "judge-2")

    assert store.get() == ClockSettings(offset_seconds=30 * 3600, updated_by="judge-2")
    assert clock.now() == REAL_NOW + timedelta(hours=30)


def test_a_second_clock_on_the_same_store_sees_the_offset():
    clock, store = make_clock()
    clock.advance(12, "judge-1")

    other = Clock(store, lambda: REAL_NOW)

    assert other.now() == REAL_NOW + timedelta(hours=12)


def test_reset_returns_the_offset_to_zero():
    clock, store = make_clock()
    clock.advance(30, "judge-1")

    clock.reset("judge-1")

    assert clock.now() == REAL_NOW
    assert store.get() == ClockSettings(offset_seconds=0, updated_by="judge-1")


@pytest.mark.parametrize("hours", [0, -1, -0.5])
def test_advance_rejects_zero_and_negative(hours):
    clock, _ = make_clock()

    with pytest.raises(ValueError):
        clock.advance(hours, "judge-1")


def test_a_rejected_advance_leaves_the_store_alone():
    clock, store = make_clock()

    with pytest.raises(ValueError):
        clock.advance(0, "judge-1")

    assert store.get() == ClockSettings(offset_seconds=0, updated_by="seed")


def test_is_due_rejects_naive_datetimes():
    naive = datetime(2026, 10, 17, 12, 0)

    with pytest.raises(ValueError):
        is_due(naive, REAL_NOW)
    with pytest.raises(ValueError):
        is_due(REAL_NOW, naive)


def test_a_naive_utcnow_is_rejected():
    clock = Clock(InMemoryClockStore(None), lambda: datetime(2026, 10, 17, 12, 0))

    with pytest.raises(ValueError):
        clock.now()


@pytest.mark.parametrize("hours", [math.inf, -math.inf, math.nan, 1e9, 24 * 365 + 1])
def test_advance_rejects_non_finite_and_over_cap_hours(hours):
    clock, store = make_clock()

    with pytest.raises(ValueError):
        clock.advance(hours, "judge-1")

    assert store.get() == ClockSettings(offset_seconds=0, updated_by="seed")


def test_advance_accepts_exactly_the_per_call_cap():
    clock, _ = make_clock()

    clock.advance(24 * 365, "judge-1")

    assert clock.now() == REAL_NOW + timedelta(hours=24 * 365)


def test_advance_rejects_a_total_over_ten_years():
    clock, store = make_clock()
    for _ in range(10):
        clock.advance(24 * 365, "judge-1")
    before = store.get()

    with pytest.raises(ValueError):
        clock.advance(24 * 365, "judge-1")

    assert store.get() == before


def test_two_advances_on_separate_clocks_both_count():
    store = InMemoryClockStore(None)
    first = Clock(store, lambda: REAL_NOW)
    second = Clock(store, lambda: REAL_NOW)

    first.advance(5, "a")
    second.advance(7, "b")

    assert first.now() == REAL_NOW + timedelta(hours=12)


def test_a_stale_read_does_not_lose_the_other_advance():
    class StaleStore(InMemoryClockStore):
        def get(self):
            return ClockSettings(offset_seconds=0, updated_by="stale")

    store = StaleStore(None)
    clock = Clock(store, lambda: REAL_NOW)
    clock.advance(5, "a")
    clock.advance(7, "b")

    assert store._settings.offset_seconds == 12 * 3600
