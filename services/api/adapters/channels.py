from collections.abc import Callable

from contracts import Message
from domain.channels import OutboundMessage
from domain.clock import Clock


class WebChannel:
    def __init__(self, clock: Clock, new_id: Callable[[], str]):
        self._clock = clock
        self._new_id = new_id

    def build(self, message: OutboundMessage) -> Message:
        return Message(
            id=self._new_id(),
            thread=message.thread,
            to_id=message.to_id,
            case_id=message.case_id,
            lang=message.lang,
            text=message.text,
            text_en=message.text_en,
            channel="web",
            created_at=self._clock.now(),
            delivered=True,
        )
