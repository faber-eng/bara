from collections.abc import Callable, Coroutine, Mapping
from typing import Any, Protocol, get_args

from google.adk.tools.tool_context import ToolContext

from bara_agent.tools.result import ToolResult, tool_error
from casework.assignment import Assignment, AssignmentRejected, AssignmentRequest
from casework.messenger import MessengerFailed
from contracts import TaskType

TASK_TYPES = get_args(TaskType)
ASSIGNED_KEY = "task_assigned"


class Assigner(Protocol):
    async def assign(self, request: AssignmentRequest) -> Assignment: ...


class AssignTask:
    def __init__(self, assigner: Assigner):
        self._assigner = assigner

    @property
    def function(self) -> Callable[..., Coroutine[Any, Any, ToolResult]]:
        return self.assign_task

    async def assign_task(
        self,
        case_id: str,
        assignee_id: str,
        task_type: TaskType,
        instructions_hint: str,
        tool_context: ToolContext,
        deadline_hours: int | None = None,
    ) -> ToolResult:
        """Assigns a task on the case to one person, sends them the task message
        in their language and sets the deadline.

        Args:
            case_id: Case id from the run input.
            assignee_id: Person id from find_people.
            task_type: dam_check, dam_repair or patrol_recheck.
            instructions_hint: One English sentence on what the person should
                look at, for the message writer.
            deadline_hours: Hours from now until the deadline, 1 to 720. Leave
                it out to use the default for the task type.
        """
        if task_type not in TASK_TYPES:
            return tool_error(
                f"task_type must be one of {', '.join(TASK_TYPES)}, got {task_type!r}"
            )
        if tool_context.state.get(ASSIGNED_KEY, False):
            return tool_error("a task is already assigned in this run")
        tool_context.state[ASSIGNED_KEY] = True
        request = AssignmentRequest(
            case_id=case_id,
            assignee_id=assignee_id,
            task_type=task_type,
            instructions_hint=instructions_hint,
            deadline_hours=deadline_hours,
        )
        try:
            assignment = await self._assigner.assign(request)
        except (AssignmentRejected, MessengerFailed) as error:
            tool_context.state[ASSIGNED_KEY] = False
            return tool_error(str(error))
        return {
            "task_id": assignment.task.id,
            "deadline_at": assignment.task.deadline_at.isoformat(),
            "deadline_local": assignment.deadline_local,
            "assignee_name": assignment.assignee_name,
            "message": assignment.message.text,
        }

    @staticmethod
    def summarize(result: Mapping[str, object]) -> str:
        return f"task {result['task_id']} due {result['deadline_at']}"
