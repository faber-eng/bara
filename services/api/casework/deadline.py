import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal, Protocol

from adapters.firestore_repos import (
    CaseChanged,
    CaseworkStore,
    StatusChange,
    TaskRepository,
)
from contracts import Case, Event, EventType, Task, TaskOverdue, TaskOverdueEvent
from domain.case_machine import can_transition
from domain.clock import Clock, is_due
from logs import log_extra

logger = logging.getLogger(__name__)

DeadlineOutcome = Literal["skipped", "not_due", "task_overdue", "case_overdue"]


class OverduePublishFailed(Exception):
    pass


class CaseReader(Protocol):
    def get(self, case_id: str) -> Case | None: ...


class Publisher(Protocol):
    def publish(self, topic: EventType, event: Event) -> str: ...


@dataclass(frozen=True)
class SweptTask:
    task_id: str
    outcome: DeadlineOutcome | None


def overdue_case_change(case: Case | None) -> StatusChange | None:
    if case is None or not can_transition(case.status, "overdue"):
        return None
    return StatusChange(case.id, case.status, "overdue")


def awaits_republish(task: Task, case: Case) -> bool:
    return task.status == "overdue" and case.status == "overdue"


class DeadlineHandler:
    def __init__(
        self,
        *,
        tasks: TaskRepository,
        cases: CaseReader,
        casework: CaseworkStore,
        publisher: Publisher,
        clock: Clock,
        new_id: Callable[[], str],
    ):
        self._tasks = tasks
        self._cases = cases
        self._casework = casework
        self._publisher = publisher
        self._clock = clock
        self._new_id = new_id

    def handle_deadline(self, task_id: str) -> DeadlineOutcome:
        task = self._tasks.get(task_id)
        if task is None:
            return "skipped"
        case = self._cases.get(task.case_id)
        if case is not None and awaits_republish(task, case):
            self._publish(task, case)
            return "case_overdue"
        if task.status != "open":
            return "skipped"
        if not is_due(task.deadline_at, self._clock.now()):
            return "not_due"
        return self._mark_overdue(task, case)

    def sweep_due(self) -> list[SweptTask]:
        return [
            SweptTask(task.id, self._handle_safely(task.id))
            for task in self._tasks.due(self._clock.now())
        ]

    def _handle_safely(self, task_id: str) -> DeadlineOutcome | None:
        try:
            return self.handle_deadline(task_id)
        except Exception:
            logger.exception(
                "deadline sweep failed",
                extra=log_extra("deadline_sweep_failed", task_id=task_id),
            )
            return None

    def _mark_overdue(self, task: Task, case: Case | None) -> DeadlineOutcome:
        change = overdue_case_change(case)
        try:
            self._casework.commit_overdue(task_id=task.id, case_change=change)
        except CaseChanged:
            logger.info(
                "deadline skipped",
                extra=log_extra("deadline_race_lost", task_id=task.id),
            )
            return "skipped"
        logger.info(
            "task overdue",
            extra=log_extra(
                "task_overdue",
                task_id=task.id,
                case_id=task.case_id,
                case_moved=change is not None,
            ),
        )
        if change is None or case is None:
            return "task_overdue"
        self._publish(task, case)
        return "case_overdue"

    def _publish(self, task: Task, case: Case) -> None:
        event = TaskOverdueEvent(
            id=self._new_id(),
            type="task.overdue",
            occurred_at=self._clock.now(),
            region=case.region,
            example=case.example,
            payload=TaskOverdue(task_id=task.id, case_id=case.id, attempt=task.attempt),
        )
        try:
            self._publisher.publish("task.overdue", event)
        except Exception as error:
            logger.exception(
                "overdue publish failed",
                extra=log_extra(
                    "overdue_publish_failed",
                    task_id=task.id,
                    case_id=case.id,
                    kind=type(error).__name__,
                ),
            )
            raise OverduePublishFailed(
                f"task.overdue for {task.id} was not published"
            ) from error
