from datetime import UTC, datetime, timedelta

from adapters.firestore_repos import (
    EvidenceRepository,
    MessageRepository,
    TaskRepository,
)
from casework.inbox import InboxReader
from contracts import Evidence, Message, Task
from tests.fakes import InMemoryCollection, make_evidence, make_message, make_task

NOW = datetime(2026, 10, 17, 12, 0, tzinfo=UTC)


def reader_with(tasks=(), messages=(), evidence=()):
    task_store = InMemoryCollection(Task)
    for task in tasks:
        task_store.put(task.id, task)
    message_store = InMemoryCollection(Message)
    for message in messages:
        message_store.put(message.id, message)
    evidence_store = InMemoryCollection(Evidence)
    for item in evidence:
        evidence_store.put(item.id, item)
    return InboxReader(
        tasks=TaskRepository(task_store),
        messages=MessageRepository(message_store),
        evidence=EvidenceRepository(evidence_store),
    )


def test_the_inbox_holds_only_the_volunteers_own_tasks_messages_and_evidence():
    reader = reader_with(
        tasks=[
            make_task(id="t1", assignee_id="v1"),
            make_task(id="t2", assignee_id="v2"),
        ],
        messages=[make_message(id="m1", to_id="v1"), make_message(id="m2", to_id="v2")],
        evidence=[
            make_evidence(id="e1", uploaded_by="v1"),
            make_evidence(id="e2", uploaded_by="v2"),
        ],
    )

    inbox = reader.read("v1")

    assert [task.id for task in inbox.tasks] == ["t1"]
    assert [message.id for message in inbox.messages] == ["m1"]
    assert [item.id for item in inbox.evidence] == ["e1"]


def test_tasks_come_newest_first_and_messages_oldest_first():
    reader = reader_with(
        tasks=[
            make_task(id="old", assignee_id="v1", created_at=NOW - timedelta(hours=2)),
            make_task(id="new", assignee_id="v1", created_at=NOW),
        ],
        messages=[
            make_message(id="late", to_id="v1", created_at=NOW),
            make_message(id="early", to_id="v1", created_at=NOW - timedelta(hours=1)),
        ],
    )

    inbox = reader.read("v1")

    assert [task.id for task in inbox.tasks] == ["new", "old"]
    assert [message.id for message in inbox.messages] == ["early", "late"]


def test_an_unknown_volunteer_gets_an_empty_inbox():
    inbox = reader_with().read("nobody")

    assert inbox.tasks == []
    assert inbox.messages == []
    assert inbox.evidence == []
