import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request

from auth import Principal, require_role
from contracts import ClockState
from domain.clock import Clock
from scenario_reset import ScenarioResetter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/judge")


def reject_when_limited(request: Request, uid: str) -> None:
    limiter = request.app.state.reset_limiter
    wait = limiter.retry_after(uid)
    if wait == 0:
        limiter.record_failure(uid)
        return
    logger.warning("reset blocked", extra={"fields": {"uid": uid, "retry_after": wait}})
    raise HTTPException(
        status_code=429,
        detail="too_many_resets",
        headers={"Retry-After": str(wait)},
    )


@router.post("/reset", response_model=ClockState)
def reset_scenario(
    request: Request,
    principal: Annotated[Principal, Depends(require_role("judge"))],
) -> ClockState:
    reject_when_limited(request, principal.uid)
    resetter: ScenarioResetter = request.app.state.resetter
    resetter.reset(principal.uid)
    clock: Clock = request.app.state.adapters.clock
    reading = clock.reading()
    return ClockState(
        now=reading.now,
        offset_seconds=reading.offset_seconds,
        judge_mode=request.app.state.settings.judge_mode.enabled,
    )
