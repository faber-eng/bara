import math
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal

from contracts import TriggerGateState

MIN_GAP_SECONDS = 60
DAILY_CAP = 20


@dataclass(frozen=True)
class Refusal:
    reason: Literal["gap", "daily"]
    retry_after: int


def seconds_until_next_day(now: datetime) -> int:
    midnight = (now + timedelta(days=1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    return math.ceil((midnight - now).total_seconds())


def gap_wait(state: TriggerGateState, now: datetime) -> int:
    elapsed = (now - state.last_trigger_at).total_seconds()
    return max(0, math.ceil(MIN_GAP_SECONDS - elapsed))


def todays_count(state: TriggerGateState | None, day: str) -> int:
    if state is None or state.day != day:
        return 0
    return state.day_count


def decide(
    state: TriggerGateState | None, now: datetime
) -> tuple[TriggerGateState | None, Refusal | None]:
    day = now.date().isoformat()
    count = todays_count(state, day)
    if count >= DAILY_CAP:
        return None, Refusal("daily", seconds_until_next_day(now))
    wait = gap_wait(state, now) if state is not None else 0
    if wait > 0:
        return None, Refusal("gap", wait)
    return TriggerGateState(last_trigger_at=now, day=day, day_count=count + 1), None
