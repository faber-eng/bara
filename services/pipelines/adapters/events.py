PUBLISH_TIMEOUT_SECONDS = 10
TOPICS = frozenset(
    {
        "hotspot.detected",
        "fire.quiet",
        "drying.ranked",
        "evidence.received",
        "task.overdue",
        "case.escalated",
    }
)


class UnpublishableTopic(Exception):
    pass


class EventPublisher:
    def __init__(self, client, project: str):
        self._client = client
        self._project = project

    def publish(self, event) -> str:
        if event.type not in TOPICS:
            raise UnpublishableTopic(f"{event.type!r} is not an event topic")
        path = self._client.topic_path(self._project, event.type)
        future = self._client.publish(
            path, event.model_dump_json().encode(), type=event.type
        )
        return future.result(timeout=PUBLISH_TIMEOUT_SECONDS)
