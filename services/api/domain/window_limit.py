import math
from datetime import datetime, timedelta

from contracts import AreaRunState


def recent_runs(
    state: AreaRunState | None, now: datetime, window: timedelta
) -> list[datetime]:
    if state is None:
        return []
    return [run for run in state.runs if now - run < window]


def retry_after(runs: list[datetime], now: datetime, window: timedelta) -> int:
    release = min(runs) + window
    return max(1, math.ceil((release - now).total_seconds()))


def decide_within(
    state: AreaRunState | None, now: datetime, limit: int, window: timedelta
) -> tuple[AreaRunState | None, int]:
    runs = recent_runs(state, now, window)
    if len(runs) >= limit:
        return None, retry_after(runs, now, window)
    return AreaRunState(runs=[*runs, now]), 0
