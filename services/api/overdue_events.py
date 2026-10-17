import asyncio
import logging
from collections.abc import Mapping
from typing import Protocol

from adapters.firestore_repos import CaseRepository, TaskRepository
from contracts import Event, Task, TaskOverdue, TaskOverdueEvent
from events import MalformedPush
from logs import log_extra

logger = logging.getLogger(__name__)

TRIGGER = "task.overdue"


def run_event(payload: TaskOverdue, task: Task) -> dict[str, object]:
    return {
        **payload.model_dump(mode="json"),
        "task_type": task.type,
        "assignee_id": task.assignee_id,
    }


class OverdueAgent(Protocol):
    async def run_case(
        self,
        trigger: str,
        case_id: str,
        run_id: str,
        event: Mapping[str, object] | None = None,
    ): ...


class TaskOverdueHandler:
    def __init__(
        self, *, cases: CaseRepository, tasks: TaskRepository, agent: OverdueAgent
    ):
        self._cases = cases
        self._tasks = tasks
        self._agent = agent

    def handle(self, message_id: str, event: Event) -> None:
        if not isinstance(event, TaskOverdueEvent):
            raise MalformedPush("not a task.overdue event")
        payload = event.payload
        task = self._overdue_task(payload)
        if task is None:
            logger.info(
                "overdue event skipped",
                extra=log_extra(
                    "overdue_event_skipped",
                    message_id=message_id,
                    case_id=payload.case_id,
                    task_id=payload.task_id,
                ),
            )
            return
        asyncio.run(
            self._agent.run_case(
                TRIGGER,
                payload.case_id,
                f"{message_id}-{payload.case_id}",
                run_event(payload, task),
            )
        )

    def _overdue_task(self, payload: TaskOverdue) -> Task | None:
        case = self._cases.get(payload.case_id)
        if case is None or case.status != "overdue":
            return None
        task = self._tasks.get(payload.task_id)
        if task is None or task.status != "overdue":
            return None
        return task
