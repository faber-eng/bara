import asyncio
import logging
from collections.abc import Mapping
from typing import Protocol

from adapters.firestore_repos import CaseRepository, TaskRepository
from contracts import Event, TaskOverdue, TaskOverdueEvent
from events import MalformedPush
from logs import log_extra

logger = logging.getLogger(__name__)

TRIGGER = "task.overdue"


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
        if not self._case_is_overdue(payload.case_id):
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
                self._run_event(payload),
            )
        )

    def _case_is_overdue(self, case_id: str) -> bool:
        case = self._cases.get(case_id)
        return case is not None and case.status == "overdue"

    def _run_event(self, payload: TaskOverdue) -> dict[str, object]:
        event: dict[str, object] = payload.model_dump(mode="json")
        task = self._tasks.get(payload.task_id)
        if task is None:
            return event
        event["task_type"] = task.type
        event["assignee_id"] = task.assignee_id
        return event
