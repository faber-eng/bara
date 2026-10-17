import logging
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from google.api_core.exceptions import GoogleAPICallError
from pydantic import BaseModel, ConfigDict

from adapters.pubsub import UnpublishableTopic
from auth import Principal, require_role
from domain.scenario_events import NoRankings
from trigger import JudgeTrigger

logger = logging.getLogger(__name__)

PUBLISH_ERRORS = (GoogleAPICallError, TimeoutError, UnpublishableTopic)

router = APIRouter(prefix="/api/judge")


class TriggerRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event: Literal["drying.ranked"]


class TriggerAccepted(BaseModel):
    event: str
    message_id: str


@router.post("/trigger", status_code=202, response_model=TriggerAccepted)
def trigger_event(
    body: TriggerRequest,
    request: Request,
    principal: Annotated[Principal, Depends(require_role("ops", "judge"))],
) -> TriggerAccepted:
    trigger: JudgeTrigger = request.app.state.trigger
    try:
        message_id = trigger.drying_ranked()
    except NoRankings as error:
        raise HTTPException(status_code=409, detail="no_rankings") from error
    except PUBLISH_ERRORS as error:
        logger.exception(
            "judge trigger failed", extra={"fields": {"uid": principal.uid}}
        )
        raise HTTPException(status_code=502, detail="publish_failed") from error
    return TriggerAccepted(event=body.event, message_id=message_id)
