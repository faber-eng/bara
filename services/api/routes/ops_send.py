import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from auth import Principal, require_role
from routes.judge_trigger import PUBLISH_ERRORS, refusal_message
from trigger import AreaHasCase, AreaRequest, UnknownCell

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ops")


class SendAccepted(BaseModel):
    cell_id: str
    message_id: str


def reject_when_limited(request: Request, uid: str) -> None:
    refusal = request.app.state.send_gate.admit()
    if refusal is None:
        return
    logger.warning(
        "send blocked", extra={"fields": {"uid": uid, "reason": refusal.reason}}
    )
    raise HTTPException(
        status_code=429,
        detail=refusal_message(refusal),
        headers={"Retry-After": str(refusal.retry_after)},
    )


@router.post("/cells/{cell_id}/send", status_code=202, response_model=SendAccepted)
def send_someone(
    cell_id: str,
    request: Request,
    principal: Annotated[Principal, Depends(require_role("ops", "judge"))],
) -> SendAccepted:
    area_request: AreaRequest = request.app.state.area_request
    reject_when_limited(request, principal.uid)
    try:
        message_id = area_request.send_someone(cell_id)
    except UnknownCell as error:
        raise HTTPException(status_code=404, detail="unknown_cell") from error
    except AreaHasCase as error:
        raise HTTPException(status_code=409, detail="case_open") from error
    except PUBLISH_ERRORS as error:
        logger.exception(
            "send someone failed", extra={"fields": {"uid": principal.uid}}
        )
        raise HTTPException(status_code=502, detail="publish_failed") from error
    return SendAccepted(cell_id=cell_id, message_id=message_id)
