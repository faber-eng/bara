from fastapi import APIRouter, Request

from config import Settings
from contracts import ClockState
from domain.clock import Clock

router = APIRouter(prefix="/api")


@router.get("/clock", response_model=ClockState)
def clock_state(request: Request) -> ClockState:
    settings: Settings = request.app.state.settings
    clock: Clock = request.app.state.adapters.clock
    reading = clock.reading()
    return ClockState(
        now=reading.now,
        offset_seconds=reading.offset_seconds,
        judge_mode=settings.judge_mode.enabled,
    )
