import logging
from typing import Protocol

from adapters.cells import CellRepository
from adapters.firestore_repos import (
    CaseChanged,
    CaseRepository,
    CaseworkStore,
    StatusChange,
    TaskRepository,
    VolunteerRepository,
)
from casework.assignment import Assignment, AssignmentRejected, AssignmentRequest
from casework.escalation import EscalationRejected
from contracts import Case, Escalation, Message, ReviewRequest, Task
from domain.case_machine import can_transition
from domain.channels import Channel, OutboundMessage
from domain.clock import Clock
from domain.people import ROLE_FOR_TASK, nearest_people

logger = logging.getLogger(__name__)

NOTE_LANGUAGE = "en"
NOTE_RECIPIENT = "ops"


class UnknownReviewCase(Exception):
    pass


class NotInReview(Exception):
    pass


class ReviewRejected(Exception):
    pass


class ReviewEscalator(Protocol):
    async def escalate(self, case_id: str, reason: str) -> Escalation: ...


class ReviewAssigner(Protocol):
    async def assign(self, request: AssignmentRequest) -> Assignment: ...


class ReviewDesk:
    def __init__(
        self,
        *,
        cases: CaseRepository,
        tasks: TaskRepository,
        volunteers: VolunteerRepository,
        cells: CellRepository,
        casework: CaseworkStore,
        assigner: ReviewAssigner,
        escalator: ReviewEscalator,
        channel: Channel,
        clock: Clock,
    ):
        self._cases = cases
        self._tasks = tasks
        self._volunteers = volunteers
        self._cells = cells
        self._casework = casework
        self._assigner = assigner
        self._escalator = escalator
        self._channel = channel
        self._clock = clock

    def request(self, case_id: str, reason: str) -> None:
        case = self._cases.get(case_id)
        if case is None:
            raise ReviewRejected(f"no case {case_id!r}")
        if case.status == "human_review":
            return
        if not can_transition(case.status, "human_review"):
            raise ReviewRejected(f"a {case.status} case cannot go to human review")
        try:
            self._casework.move_case(StatusChange(case_id, case.status, "human_review"))
        except CaseChanged as error:
            raise ReviewRejected(f"case {case_id} changed; read it again") from error
        logger.info(
            "human review requested",
            extra={
                "fields": {
                    "event": "human_review_requested",
                    "case_id": case_id,
                    "reason": reason,
                }
            },
        )

    async def resolve(self, case_id: str, request: ReviewRequest, by: str) -> Case:
        case = self._cases.get(case_id)
        if case is None:
            raise UnknownReviewCase(case_id)
        if case.status != "human_review":
            raise NotInReview(case_id)
        note = self._note(case_id, request.note, by)
        if request.action == "assign":
            await self._assign(case, request.note)
        elif request.action == "escalate":
            await self._escalate(case_id, request.note)
        else:
            self._close(case_id, note, by)
        if request.action != "close":
            self._save_note(note)
        logger.info(
            "review resolved",
            extra={
                "fields": {
                    "event": "review_resolved",
                    "case_id": case_id,
                    "action": request.action,
                    "by": by,
                }
            },
        )
        return self._stored(case_id)

    def _close(self, case_id: str, note: Message, by: str) -> None:
        try:
            self._casework.commit_review(
                case_id=case_id,
                message=note,
                closed_by=by,
                closed_at=self._clock.now(),
            )
        except CaseChanged as error:
            raise NotInReview(case_id) from error

    async def _escalate(self, case_id: str, reason: str) -> None:
        try:
            await self._escalator.escalate(case_id, reason)
        except EscalationRejected:
            if self._stored(case_id).status != "human_review":
                raise NotInReview(case_id) from None
            raise

    async def _assign(self, case: Case, hint: str) -> None:
        last = self._last_task(case.id)
        if last is None:
            raise ReviewRejected(f"case {case.id} has no task to repeat")
        assignee = self._nearest(case, last)
        try:
            await self._assigner.assign(
                AssignmentRequest(
                    case_id=case.id,
                    assignee_id=assignee,
                    task_type=last.type,
                    instructions_hint=hint,
                    deadline_hours=None,
                )
            )
        except AssignmentRejected as error:
            raise ReviewRejected(str(error)) from error

    def _last_task(self, case_id: str) -> Task | None:
        tasks = self._tasks.for_case(case_id)
        if not tasks:
            return None
        return max(tasks, key=lambda task: (task.created_at, task.id))

    def _nearest(self, case: Case, task: Task) -> str:
        centroid = self._cells.centroid(case.cell_id)
        if centroid is None:
            raise ReviewRejected(f"unknown cell {case.cell_id!r}")
        people = self._volunteers.available(ROLE_FOR_TASK[task.type])
        matches = nearest_people(centroid, people, 1, self._tasks.open_assignees())
        if not matches:
            raise ReviewRejected(f"nobody is available for {task.type}")
        return matches[0].volunteer.id

    def _save_note(self, note: Message) -> None:
        try:
            self._casework.save_note(note)
        except Exception:
            logger.exception(
                "review note not saved",
                extra={
                    "fields": {
                        "event": "review_note_failed",
                        "case_id": note.case_id,
                    }
                },
            )

    def _stored(self, case_id: str) -> Case:
        case = self._cases.get(case_id)
        if case is None:
            raise UnknownReviewCase(case_id)
        return case

    def _note(self, case_id: str, text: str, by: str) -> Message:
        return self._channel.build(
            OutboundMessage(
                to_id=NOTE_RECIPIENT,
                thread="ops",
                case_id=case_id,
                lang=NOTE_LANGUAGE,
                text=text,
                text_en=text,
            )
        )
