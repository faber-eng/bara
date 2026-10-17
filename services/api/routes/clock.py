from fastapi import APIRouter, Request
from starlette.datastructures import State

from config import Settings
from contracts import ClockState
from domain.clock import Clock

router = APIRouter(prefix="/api")


def read_clock_state(state: State) -> ClockState:
    settings: Settings = state.settings
    clock: Clock = state.adapters.clock
    reading = clock.reading()
    return ClockState(
        now=reading.now,
        offset_seconds=reading.offset_seconds,
        judge_mode=settings.judge_mode.enabled,
    )


@router.get("/clock", response_model=ClockState)
def clock_state(request: Request) -> ClockState:
    return read_clock_state(request.app.state)
