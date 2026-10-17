from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request

from auth import Principal, claimed_owner, require_brigade_owner, require_role
from casework.escalation import (
    Acknowledger,
    BrigadeInbox,
    EscalationRejected,
    NotYourEscalation,
    UnknownEscalation,
)
from contracts import Escalation

ACK_ERRORS: dict[type[Exception], tuple[int, str]] = {
    UnknownEscalation: (404, "escalation_not_found"),
    NotYourEscalation: (403, "forbidden"),
    EscalationRejected: (409, "escalation_changed"),
}

router = APIRouter(prefix="/api/brigade")


def brigade_inbox(request: Request) -> BrigadeInbox:
    return request.app.state.brigade_inbox


def acknowledger(request: Request) -> Acknowledger:
    return request.app.state.acknowledger


@router.get(
    "/{contact_id}/inbox",
    response_model=list[Escalation],
    dependencies=[Depends(require_brigade_owner)],
)
def read_inbox(contact_id: str, request: Request) -> list[Escalation]:
    return brigade_inbox(request).read(contact_id)


@router.post("/escalations/{escalation_id}/ack", response_model=Escalation)
def acknowledge(
    escalation_id: str,
    request: Request,
    principal: Annotated[Principal, Depends(require_role("brigade"))],
) -> Escalation:
    try:
        acked = acknowledger(request).ack(escalation_id, claimed_owner(principal))
    except (UnknownEscalation, NotYourEscalation, EscalationRejected) as error:
        status, detail = ACK_ERRORS[type(error)]
        raise HTTPException(status_code=status, detail=detail) from error
    return brigade_inbox(request).signed(acked)
