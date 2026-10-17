import logging
from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException, Request

from events import EventDispatcher, MalformedPush, UnhandledTopic, decode_push
from push_auth import require_push_caller

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")


@router.post("/events/{topic}", dependencies=[Depends(require_push_caller)])
def receive_event(
    topic: str, body: Annotated[dict, Body()], request: Request
) -> dict[str, str]:
    dispatcher: EventDispatcher = request.app.state.dispatcher
    try:
        message = decode_push(body)
        outcome = dispatcher.dispatch(topic, message.message_id, message.event)
    except UnhandledTopic as error:
        raise HTTPException(status_code=404, detail="unhandled_topic") from error
    except MalformedPush as error:
        logger.warning(
            "push malformed",
            extra={
                "fields": {
                    "event": "push_malformed",
                    "topic": topic,
                    "kind": str(error),
                }
            },
        )
        raise HTTPException(status_code=400, detail="malformed_push") from error
    return {"status": outcome}
