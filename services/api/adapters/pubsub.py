import logging
from typing import get_args

from contracts import Event, EventType

logger = logging.getLogger(__name__)

EVENT_TYPES: frozenset[str] = frozenset(get_args(EventType))
PUBLISH_TIMEOUT_SECONDS = 10


class UnpublishableTopic(Exception):
    pass


class EventPublisher:
    def __init__(self, client, project: str):
        self._client = client
        self._project = project

    def publish(self, topic: EventType, event: Event) -> str:
        if topic not in EVENT_TYPES:
            raise UnpublishableTopic(f"{topic!r} is not an event topic")
        if event.type != topic:
            raise UnpublishableTopic(f"event type {event.type} does not match {topic}")
        path = self._client.topic_path(self._project, topic)
        future = self._client.publish(
            path, event.model_dump_json().encode(), type=event.type
        )
        return future.result(timeout=PUBLISH_TIMEOUT_SECONDS)
