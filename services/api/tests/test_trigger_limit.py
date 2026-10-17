from datetime import UTC, datetime, timedelta

from casework.trigger_gate import TriggerGate
from domain.trigger_limit import DAILY_CAP, MIN_GAP_SECONDS, Refusal, decide
from tests.fakes import InMemoryTriggerGateStore

NOON = datetime(2026, 10, 17, 12, 0, tzinfo=UTC)


class MovingClock:
    def __init__(self, now=NOON):
        self.now = now

    def __call__(self):
        return self.now

    def advance(self, **delta):
        self.now += timedelta(**delta)


def make_gate():
    clock = MovingClock()
    return TriggerGate(InMemoryTriggerGateStore(), clock), clock


def test_the_first_trigger_is_admitted_and_stored():
    state, refusal = decide(None, NOON)

    assert refusal is None
    assert state.day == "2026-10-17"
    assert state.day_count == 1
    assert state.last_trigger_at == NOON


def test_a_second_trigger_inside_60_seconds_waits_the_rest():
    first, _ = decide(None, NOON)

    state, refusal = decide(first, NOON + timedelta(seconds=45))

    assert state is None
    assert refusal == Refusal(reason="gap", retry_after=15)


def test_a_trigger_after_60_seconds_is_admitted_and_counted():
    first, _ = decide(None, NOON)

    state, refusal = decide(first, NOON + timedelta(seconds=MIN_GAP_SECONDS))

    assert refusal is None
    assert state.day_count == 2


def test_the_21st_trigger_of_a_utc_day_waits_for_midnight():
    gate, clock = make_gate()
    for _ in range(DAILY_CAP):
        assert gate.admit() is None
        clock.advance(seconds=60)

    refusal = gate.admit()

    assert refusal.reason == "daily"
    assert refusal.retry_after == 12 * 3600 - 20 * 60


def test_the_count_starts_again_on_the_next_utc_day():
    gate, clock = make_gate()
    for _ in range(DAILY_CAP):
        gate.admit()
        clock.advance(seconds=60)
    clock.now = datetime(2026, 10, 18, 0, 0, 1, tzinfo=UTC)

    assert gate.admit() is None


def test_a_refused_trigger_is_not_counted():
    gate, clock = make_gate()
    gate.admit()

    assert gate.admit().reason == "gap"
    clock.advance(seconds=60)
    assert gate.admit() is None
    assert gate.store.state.day_count == 2
