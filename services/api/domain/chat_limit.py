from datetime import datetime, timedelta

from contracts import AreaRunState
from domain.window_limit import decide_within

MESSAGES_PER_WINDOW = 10
WINDOW = timedelta(minutes=10)


def decide(
    state: AreaRunState | None, now: datetime
) -> tuple[AreaRunState | None, int]:
    return decide_within(state, now, MESSAGES_PER_WINDOW, WINDOW)
