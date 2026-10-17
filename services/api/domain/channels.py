from dataclasses import dataclass
from typing import Protocol

from contracts import Message, MessageThread


@dataclass(frozen=True)
class OutboundMessage:
    to_id: str
    thread: MessageThread
    case_id: str | None
    lang: str
    text: str
    text_en: str


class Channel(Protocol):
    def build(self, message: OutboundMessage) -> Message: ...
