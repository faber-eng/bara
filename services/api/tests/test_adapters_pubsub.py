import os
from datetime import UTC, datetime

import pytest

from adapters.pubsub import EventPublisher, UnpublishableTopic
from contracts import CaseEscalated, CaseEscalatedEvent, TaskOverdue, TaskOverdueEvent


class StubFuture:
    def __init__(self, message_id):
        self._message_id = message_id

    def result(self, timeout=None):
        return self._message_id


class RecordingPublisherClient:
    def __init__(self):
        self.published = []

    def topic_path(self, project, topic):
        return f"projects/{project}/topics/{topic}"

    def publish(self, topic_path, data, **attributes):
        self.published.append((topic_path, data, attributes))
        return StubFuture("msg-123")


def make_event():
    return CaseEscalatedEvent(
        type="case.escalated",
        id="evt-1",
        occurred_at=datetime(2026, 10, 17, 12, 0, tzinfo=UTC),
        region="riau",
        example=False,
        payload=CaseEscalated(case_id="c1", escalation_id="e1"),
    )


def make_publisher():
    client = RecordingPublisherClient()
    return EventPublisher(client, "p"), client


def test_publish_sends_the_event_json_to_the_topic_and_returns_the_message_id():
    publisher, client = make_publisher()
    event = make_event()

    message_id = publisher.publish("case.escalated", event)

    path, data, attributes = client.published[0]
    assert message_id == "msg-123"
    assert path == "projects/p/topics/case.escalated"
    assert CaseEscalatedEvent.model_validate_json(data) == event
    assert attributes == {"type": "case.escalated"}


@pytest.mark.parametrize("topic", ["bara.dlq", "nope", ""])
def test_publish_rejects_topics_that_are_not_event_types(topic):
    publisher, client = make_publisher()

    with pytest.raises(UnpublishableTopic):
        publisher.publish(topic, make_event())

    assert client.published == []


def test_publish_rejects_an_event_whose_type_differs_from_the_topic():
    publisher, client = make_publisher()

    with pytest.raises(UnpublishableTopic):
        publisher.publish("task.overdue", make_event())

    assert client.published == []


def test_publish_accepts_each_event_type_on_its_own_topic():
    publisher, client = make_publisher()
    event = TaskOverdueEvent(
        type="task.overdue",
        id="evt-2",
        occurred_at=datetime(2026, 10, 17, 12, 0, tzinfo=UTC),
        region="riau",
        example=False,
        payload=TaskOverdue(task_id="t1", case_id="c1", attempt=1),
    )

    publisher.publish("task.overdue", event)

    assert client.published[0][0] == "projects/p/topics/task.overdue"


@pytest.mark.live
def test_live_event_topics_exist():
    from google.cloud import pubsub_v1

    project = os.environ["GOOGLE_CLOUD_PROJECT"]
    client = pubsub_v1.PublisherClient()

    topic = client.get_topic(topic=client.topic_path(project, "hotspot.detected"))

    assert topic.name.endswith("hotspot.detected")
