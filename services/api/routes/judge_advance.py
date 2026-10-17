import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from auth import Principal, require_role
from casework.deadline import DeadlineHandler
from contracts import ClockState
from domain.clock import MAX_ADVANCE_HOURS, Clock
from logs import log_extra
from routes.clock import read_clock_state

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/judge")


class AdvanceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    hours: Annotated[float, Field(gt=0, le=MAX_ADVANCE_HOURS, allow_inf_nan=False)]


def require_judge_mode(request: Request) -> None:
    if not request.app.state.settings.judge_mode.enabled:
        raise HTTPException(status_code=403, detail="judge_mode_off")


@router.post(
    "/advance",
    response_model=ClockState,
    dependencies=[Depends(require_judge_mode)],
)
def advance_clock(
    body: AdvanceRequest,
    request: Request,
    principal: Annotated[Principal, Depends(require_role("judge"))],
) -> ClockState:
    clock: Clock = request.app.state.adapters.clock
    try:
        clock.advance(body.hours, principal.uid)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    deadlines: DeadlineHandler = request.app.state.deadlines
    swept = deadlines.sweep_due()
    logger.info(
        "clock advanced",
        extra=log_extra(
            "clock_advanced",
            uid=principal.uid,
            hours=body.hours,
            swept={item.task_id: item.outcome for item in swept},
        ),
    )
    return read_clock_state(request.app.state)
