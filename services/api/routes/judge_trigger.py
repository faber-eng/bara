import logging
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from google.api_core.exceptions import GoogleAPICallError
from pydantic import BaseModel, ConfigDict

from adapters.pubsub import UnpublishableTopic
from auth import Principal, require_role
from domain.scenario_events import NoRankings
from domain.trigger_limit import DAILY_CAP, Refusal
from trigger import JudgeTrigger

logger = logging.getLogger(__name__)

PUBLISH_ERRORS = (GoogleAPICallError, TimeoutError, UnpublishableTopic)

router = APIRouter(prefix="/api/judge")


class TriggerRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event: Literal["drying.ranked", "fire.quiet"]


class TriggerAccepted(BaseModel):
    event: str
    message_id: str


def reject_when_limited(request: Request, uid: str) -> None:
    refusal = request.app.state.trigger_gate.admit()
    if refusal is None:
        return
    logger.warning(
        "trigger blocked",
        extra={"fields": {"uid": uid, "reason": refusal.reason}},
    )
    raise HTTPException(
        status_code=429,
        detail=refusal_message(refusal),
        headers={"Retry-After": str(refusal.retry_after)},
    )


def refusal_message(refusal: Refusal) -> str:
    if refusal.reason == "daily":
        return (
            f"Daily limit of {DAILY_CAP} triggers reached. Try again after 00:00 UTC."
        )
    return f"Wait {refusal.retry_after} s before the next trigger."


def publish(trigger: JudgeTrigger, event: str) -> str:
    if event == "fire.quiet":
        return trigger.fire_quiet()
    return trigger.drying_ranked()


@router.post("/trigger", status_code=202, response_model=TriggerAccepted)
def trigger_event(
    body: TriggerRequest,
    request: Request,
    principal: Annotated[Principal, Depends(require_role("ops", "judge"))],
) -> TriggerAccepted:
    reject_when_limited(request, principal.uid)
    trigger: JudgeTrigger = request.app.state.trigger
    try:
        message_id = publish(trigger, body.event)
    except NoRankings as error:
        raise HTTPException(status_code=409, detail="no_rankings") from error
    except PUBLISH_ERRORS as error:
        logger.exception(
            "judge trigger failed", extra={"fields": {"uid": principal.uid}}
        )
        raise HTTPException(status_code=502, detail="publish_failed") from error
    return TriggerAccepted(event=body.event, message_id=message_id)
