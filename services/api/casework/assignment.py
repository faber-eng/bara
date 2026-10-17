import logging
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Protocol

from adapters.cells import CellRepository
from adapters.firestore_repos import (
    CaseChanged,
    CaseRepository,
    CaseworkStore,
    DamRepository,
    TaskRepository,
    VolunteerRepository,
)
from casework.messenger import MESSENGER_PROMPT_VERSION, ComposedMessage, TaskBrief
from contracts import Case, CaseStatus, GeoPoint, Message, Task, TaskType, Volunteer
from domain.assignment import (
    InvalidDeadline,
    deadline_hours,
    local_deadline,
    next_attempt,
    real_schedule_time,
    status_after_assign,
    tasks_to_reassign,
)
from domain.case_machine import IllegalTransition
from domain.channels import Channel, OutboundMessage
from domain.clock import Clock

logger = logging.getLogger(__name__)


class AssignmentRejected(Exception):
    pass


class Composer(Protocol):
    async def compose(self, brief: TaskBrief) -> ComposedMessage: ...


class Scheduler(Protocol):
    def schedule(self, task_id: str, deadline_at: datetime) -> str: ...


@dataclass(frozen=True)
class AssignmentRequest:
    case_id: str
    assignee_id: str
    task_type: TaskType
    instructions_hint: str
    deadline_hours: int | None
    target_cell_id: str | None = None


@dataclass(frozen=True)
class Assignment:
    task: Task
    message: Message


def log_fields(event: str, task: Task, **fields: object) -> dict[str, object]:
    return {
        "fields": {
            "event": event,
            "task_id": task.id,
            "case_id": task.case_id,
            **fields,
        }
    }


class TaskAssigner:
    def __init__(
        self,
        *,
        cases: CaseRepository,
        volunteers: VolunteerRepository,
        dams: DamRepository,
        cells: CellRepository,
        tasks: TaskRepository,
        casework: CaseworkStore,
        channel: Channel,
        messenger: Composer,
        scheduler: Scheduler | None,
        clock: Clock,
        default_deadline_hours: Mapping[TaskType, int],
        timezones: Mapping[str, str],
        new_id: Callable[[], str],
    ):
        self._cases = cases
        self._volunteers = volunteers
        self._dams = dams
        self._cells = cells
        self._tasks = tasks
        self._casework = casework
        self._channel = channel
        self._messenger = messenger
        self._scheduler = scheduler
        self._clock = clock
        self._default_deadline_hours = default_deadline_hours
        self._timezones = timezones
        self._new_id = new_id

    async def assign(self, request: AssignmentRequest) -> Assignment:
        case = self._case(request.case_id)
        next_status = self._status_after_assign(case)
        volunteer = self._assignee(request.assignee_id)
        hours = self._hours(request)
        target = self._target(case, request)
        reading = self._clock.reading()
        deadline_at = reading.now + timedelta(hours=hours)
        composed = await self._messenger.compose(
            self._brief(case, volunteer, request, target, deadline_at)
        )
        prior = self._tasks.for_case(case.id)
        task = self._new_task(
            case,
            request,
            target,
            deadline_at,
            reading.now,
            next_attempt(case.status, prior),
        )
        message = self._message(case, volunteer, composed)
        self._commit(
            case, next_status, task, message, tasks_to_reassign(case.status, prior)
        )
        task = self._schedule(task, reading.offset_seconds)
        logger.info(
            "task assigned",
            extra=log_fields(
                "task_assigned",
                task,
                assignee_id=volunteer.id,
                hours=hours,
                attempt=task.attempt,
                messenger_prompt_version=MESSENGER_PROMPT_VERSION,
            ),
        )
        return Assignment(task=task, message=message)

    def _message(
        self, case: Case, volunteer: Volunteer, composed: ComposedMessage
    ) -> Message:
        return self._channel.build(
            OutboundMessage(
                to_id=volunteer.id,
                thread="volunteer",
                case_id=case.id,
                lang=composed.lang,
                text=composed.text,
                text_en=composed.text_en,
            )
        )

    def _commit(
        self,
        case: Case,
        next_status: CaseStatus,
        task: Task,
        message: Message,
        reassigned_task_ids: list[str],
    ) -> None:
        try:
            self._casework.commit_assignment(
                expected_status=case.status,
                next_status=next_status,
                task=task,
                message=message,
                reassigned_task_ids=reassigned_task_ids,
            )
        except CaseChanged as error:
            raise AssignmentRejected(str(error)) from error

    def _case(self, case_id: str) -> Case:
        case = self._cases.get(case_id)
        if case is None:
            raise AssignmentRejected(f"unknown case {case_id!r}")
        return case

    @staticmethod
    def _status_after_assign(case: Case) -> CaseStatus:
        try:
            return status_after_assign(case.status)
        except IllegalTransition as error:
            raise AssignmentRejected(
                f"case {case.id} is {case.status}; a task cannot be assigned"
            ) from error

    def _assignee(self, assignee_id: str) -> Volunteer:
        volunteer = self._volunteers.get(assignee_id)
        if volunteer is None:
            raise AssignmentRejected(f"unknown person {assignee_id!r}")
        if not volunteer.available:
            raise AssignmentRejected(f"person {assignee_id!r} is not available")
        return volunteer

    def _hours(self, request: AssignmentRequest) -> int:
        try:
            return deadline_hours(
                request.deadline_hours,
                request.task_type,
                self._default_deadline_hours,
            )
        except InvalidDeadline as error:
            raise AssignmentRejected(str(error)) from error

    def _target(self, case: Case, request: AssignmentRequest) -> GeoPoint:
        if request.target_cell_id is not None:
            return self._centroid(request.target_cell_id)
        if case.dam_id is not None:
            dam = self._dams.get(case.dam_id)
            if dam is None:
                raise AssignmentRejected(f"unknown dam {case.dam_id!r}")
            return dam.point
        return self._centroid(case.cell_id)

    def _centroid(self, cell_id: str) -> GeoPoint:
        centroid = self._cells.centroid(cell_id)
        if centroid is None:
            raise AssignmentRejected(f"unknown cell {cell_id!r}")
        return centroid

    def _brief(
        self,
        case: Case,
        volunteer: Volunteer,
        request: AssignmentRequest,
        target: GeoPoint,
        deadline_at: datetime,
    ) -> TaskBrief:
        timezone = self._timezones.get(case.region)
        if timezone is None:
            raise AssignmentRejected(f"region {case.region!r} has no timezone")
        return TaskBrief(
            language=volunteer.language,
            task_type=request.task_type,
            place=case.dam_id,
            target=target,
            deadline_local=local_deadline(deadline_at, timezone),
            hint=request.instructions_hint,
        )

    def _new_task(
        self,
        case: Case,
        request: AssignmentRequest,
        target: GeoPoint,
        deadline_at: datetime,
        now: datetime,
        attempt: int,
    ) -> Task:
        return Task(
            id=self._new_id(),
            case_id=case.id,
            type=request.task_type,
            assignee_id=request.assignee_id,
            target=target,
            deadline_at=deadline_at,
            status="open",
            cloud_task_name=None,
            attempt=attempt,
            created_at=now,
            done_at=None,
        )

    def _schedule(self, task: Task, offset_seconds: int) -> Task:
        if self._scheduler is None:
            logger.warning(
                "deadline not scheduled",
                extra=log_fields("deadline_not_scheduled", task, reason="no scheduler"),
            )
            return task
        at = real_schedule_time(task.deadline_at, offset_seconds)
        try:
            name = self._scheduler.schedule(task.id, at)
        except Exception as error:
            logger.exception(
                "deadline schedule failed",
                extra=log_fields(
                    "deadline_schedule_failed", task, kind=type(error).__name__
                ),
            )
            return task
        self._tasks.set_cloud_task_name(task.id, name)
        return task.model_copy(update={"cloud_task_name": name})
