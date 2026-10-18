from datetime import datetime, timedelta

from contracts import AreaRunState
from domain.window_limit import decide_within

RUNS_PER_HOUR = 10
WINDOW = timedelta(hours=1)


def decide(
    state: AreaRunState | None, now: datetime
) -> tuple[AreaRunState | None, int]:
    return decide_within(state, now, RUNS_PER_HOUR, WINDOW)
