import math
from datetime import datetime, timedelta

from contracts import AreaRunState

RUNS_PER_HOUR = 10
WINDOW = timedelta(hours=1)


def recent_runs(state: AreaRunState | None, now: datetime) -> list[datetime]:
    if state is None:
        return []
    return [run for run in state.runs if now - run < WINDOW]


def retry_after(runs: list[datetime], now: datetime) -> int:
    release = min(runs) + WINDOW
    return max(1, math.ceil((release - now).total_seconds()))


def decide(
    state: AreaRunState | None, now: datetime
) -> tuple[AreaRunState | None, int]:
    runs = recent_runs(state, now)
    if len(runs) >= RUNS_PER_HOUR:
        return None, retry_after(runs, now)
    return AreaRunState(runs=[*runs, now]), 0
