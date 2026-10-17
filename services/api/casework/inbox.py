from adapters.firestore_repos import (
    EvidenceRepository,
    MessageRepository,
    TaskRepository,
)
from contracts import Inbox


class InboxReader:
    def __init__(
        self,
        *,
        tasks: TaskRepository,
        messages: MessageRepository,
        evidence: EvidenceRepository,
    ):
        self._tasks = tasks
        self._messages = messages
        self._evidence = evidence

    def read(self, volunteer_id: str) -> Inbox:
        tasks = self._tasks.for_assignee(volunteer_id)
        messages = self._messages.to(volunteer_id)
        return Inbox(
            tasks=sorted(tasks, key=lambda task: task.created_at, reverse=True),
            messages=sorted(messages, key=lambda message: message.created_at),
            evidence=self._evidence.for_uploader(volunteer_id),
        )
