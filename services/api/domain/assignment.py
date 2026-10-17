from collections.abc import Mapping, Sequence
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from contracts import CaseStatus, Task, TaskType
from domain.case_machine import transition

MAX_DEADLINE_HOURS = 720


class InvalidDeadline(ValueError):
    pass


def deadline_hours(
    requested: int | None, task_type: TaskType, defaults: Mapping[TaskType, int]
) -> int:
    if requested is None:
        return defaults[task_type]
    if not 1 <= requested <= MAX_DEADLINE_HOURS:
        raise InvalidDeadline(
            f"deadline must be 1 to {MAX_DEADLINE_HOURS} hours, got {requested}"
        )
    return requested


def status_after_assign(status: CaseStatus) -> CaseStatus:
    if status == "assigned":
        return status
    return transition(status, "assigned")


def real_schedule_time(deadline_at: datetime, offset_seconds: int) -> datetime:
    return deadline_at - timedelta(seconds=offset_seconds)


def next_attempt(status: CaseStatus, prior: Sequence[Task]) -> int:
    if status != "overdue" or not prior:
        return 1
    return max(task.attempt for task in prior) + 1


def tasks_to_reassign(status: CaseStatus, prior: Sequence[Task]) -> list[str]:
    if status != "overdue":
        return []
    return [task.id for task in prior if task.status == "overdue"]


def local_deadline(deadline_at: datetime, timezone: str) -> str:
    local = deadline_at.astimezone(ZoneInfo(timezone))
    return f"{local:%A %d %B %Y, %H:%M} {local.tzname()}"
