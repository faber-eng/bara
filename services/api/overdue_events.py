import asyncio
import logging
from collections.abc import Mapping
from typing import Protocol

from adapters.firestore_repos import CaseRepository, EvidenceRepository, TaskRepository
from casework.escalation import EscalationRejected
from contracts import Case, Escalation, Event, Task, TaskOverdue, TaskOverdueEvent
from domain.escalation import overdue_escalation_reason
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


class OverdueEscalator(Protocol):
    async def escalate(self, case_id: str, reason: str) -> Escalation: ...


class TaskOverdueHandler:
    def __init__(
        self,
        *,
        cases: CaseRepository,
        tasks: TaskRepository,
        evidence: EvidenceRepository,
        agent: OverdueAgent,
        escalator: OverdueEscalator,
    ):
        self._cases = cases
        self._tasks = tasks
        self._evidence = evidence
        self._agent = agent
        self._escalator = escalator

    def handle(self, message_id: str, event: Event) -> None:
        if not isinstance(event, TaskOverdueEvent):
            raise MalformedPush("not a task.overdue event")
        payload = event.payload
        found = self._overdue(payload)
        if found is None:
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
        case, task = found
        asyncio.run(self._act(message_id, payload, case, task))

    async def _act(
        self, message_id: str, payload: TaskOverdue, case: Case, task: Task
    ) -> None:
        reason = overdue_escalation_reason(
            case, payload.attempt, self._evidence.for_cases([case.id])
        )
        if reason is not None:
            escalated = await self._escalate(message_id, case.id, reason)
            if escalated:
                return
            if self._overdue(payload) is None:
                return
        await self._agent.run_case(
            TRIGGER,
            payload.case_id,
            f"{message_id}-{payload.case_id}",
            run_event(payload, task),
        )

    async def _escalate(self, message_id: str, case_id: str, reason: str) -> bool:
        try:
            await self._escalator.escalate(case_id, reason)
        except EscalationRejected as error:
            logger.error(
                "overdue escalation rejected",
                extra=log_extra(
                    "overdue_escalation_rejected",
                    message_id=message_id,
                    case_id=case_id,
                    error=str(error),
                ),
            )
            return False
        return True

    def _overdue(self, payload: TaskOverdue) -> tuple[Case, Task] | None:
        case = self._cases.get(payload.case_id)
        if case is None or case.status != "overdue":
            return None
        task = self._tasks.get(payload.task_id)
        if task is None or task.status != "overdue":
            return None
        return case, task
