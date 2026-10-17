import hashlib
import logging
from collections.abc import Callable
from datetime import datetime
from typing import Protocol

from adapters.firestore_repos import (
    CaseChanged,
    CaseRepository,
    CaseworkStore,
    EvidenceRepository,
    StatusChange,
    TaskRepository,
    UploadRepository,
)
from adapters.storage import MAX_UPLOAD_BYTES, SignedUpload
from contracts import (
    Case,
    CompleteRequest,
    Event,
    EventType,
    Evidence,
    EvidenceReceived,
    EvidenceReceivedEvent,
    PendingUpload,
    Task,
    TaskStatus,
    UploadRequest,
    UploadTicket,
)
from domain.case_machine import can_transition
from domain.clock import Clock
from domain.evidence import object_name

logger = logging.getLogger(__name__)

UPLOADABLE_TASK_STATUSES: frozenset[TaskStatus] = frozenset({"open", "done"})


class IntakeError(Exception):
    pass


class UnknownTask(IntakeError):
    pass


class TaskClosed(IntakeError):
    pass


class UploadTooLarge(IntakeError):
    pass


class UnknownUpload(IntakeError):
    pass


class UploadMissing(IntakeError):
    pass


class PublishFailed(IntakeError):
    pass


class Storage(Protocol):
    def signed_put_url(self, object_name: str, content_type: str) -> SignedUpload: ...

    def read(self, object_name: str) -> bytes | None: ...

    def gcs_uri(self, object_name: str) -> str: ...


class Canceller(Protocol):
    def cancel(self, cloud_task_name: str | None) -> None: ...


class Publisher(Protocol):
    def publish(self, topic: EventType, event: Event) -> str: ...


def log_fields(event: str, evidence_id: str, **fields: object) -> dict[str, object]:
    return {"fields": {"event": event, "evidence_id": evidence_id, **fields}}


def case_change_for(case: Case, is_photo: bool) -> StatusChange | None:
    if not is_photo or not can_transition(case.status, "reviewing"):
        return None
    return StatusChange(case.id, case.status, "reviewing")


class EvidenceIntake:
    def __init__(
        self,
        *,
        tasks: TaskRepository,
        cases: CaseRepository,
        uploads: UploadRepository,
        evidence: EvidenceRepository,
        casework: CaseworkStore,
        storage: Storage,
        scheduler: Canceller | None,
        publisher: Publisher,
        clock: Clock,
        new_id: Callable[[], str],
    ):
        self._tasks = tasks
        self._cases = cases
        self._uploads = uploads
        self._evidence = evidence
        self._casework = casework
        self._storage = storage
        self._scheduler = scheduler
        self._publisher = publisher
        self._clock = clock
        self._new_id = new_id

    def request_upload(self, volunteer_id: str, request: UploadRequest) -> UploadTicket:
        task = self._owned_task(volunteer_id, request.task_id)
        if task.status not in UPLOADABLE_TASK_STATUSES:
            raise TaskClosed(f"task {task.id} is {task.status}")
        if request.size_bytes > MAX_UPLOAD_BYTES:
            raise UploadTooLarge(f"a file must be at most {MAX_UPLOAD_BYTES} bytes")
        evidence_id = self._new_id()
        name = object_name(
            request.kind, request.content_type, task.case_id, evidence_id
        )
        signed = self._storage.signed_put_url(name, request.content_type)
        self._uploads.save(
            PendingUpload(
                id=evidence_id,
                task_id=task.id,
                case_id=task.case_id,
                kind=request.kind,
                content_type=request.content_type,
                object_name=name,
                sample=request.sample,
                uploaded_by=volunteer_id,
                created_at=self._clock.now(),
            )
        )
        return UploadTicket(
            evidence_id=evidence_id, upload_url=signed.url, headers=signed.headers
        )

    def complete(
        self, volunteer_id: str, evidence_id: str, completion: CompleteRequest
    ) -> Evidence:
        upload = self._owned_upload(volunteer_id, evidence_id)
        stored = self._evidence.get(evidence_id)
        if stored is not None:
            return self._republish_if_unread(stored)
        task = self._owned_task(volunteer_id, upload.task_id)
        case = self._case(upload.case_id)
        evidence = self._evidence_from(upload, completion)
        is_photo = upload.kind == "photo"
        now = self._clock.now()
        done_at = now if is_photo and task.status == "open" else None
        try:
            self._casework.commit_evidence(
                evidence=evidence,
                done_at=done_at,
                case_change=case_change_for(case, is_photo),
            )
        except CaseChanged:
            return self._stored_after_race(evidence_id)
        if done_at is not None:
            self._cancel_deadline(task, evidence_id)
        if is_photo:
            self._publish(evidence, case, now)
        return evidence

    def _republish_if_unread(self, stored: Evidence) -> Evidence:
        if stored.kind == "photo" and stored.verdict is None:
            self._publish(stored, self._case(stored.case_id), self._clock.now())
        return stored

    def _owned_task(self, volunteer_id: str, task_id: str) -> Task:
        task = self._tasks.get(task_id)
        if task is None or task.assignee_id != volunteer_id:
            raise UnknownTask(f"no task {task_id!r} for this person")
        return task

    def _owned_upload(self, volunteer_id: str, evidence_id: str) -> PendingUpload:
        upload = self._uploads.get(evidence_id)
        if upload is None or upload.uploaded_by != volunteer_id:
            raise UnknownUpload(f"no upload {evidence_id!r} for this person")
        return upload

    def _case(self, case_id: str) -> Case:
        case = self._cases.get(case_id)
        if case is None:
            raise UnknownTask(f"the case {case_id!r} of this task is gone")
        return case

    def _evidence_from(
        self, upload: PendingUpload, completion: CompleteRequest
    ) -> Evidence:
        data = self._storage.read(upload.object_name)
        if data is None:
            raise UploadMissing(f"no uploaded file for {upload.id!r}")
        if len(data) > MAX_UPLOAD_BYTES:
            raise UploadTooLarge(f"a file must be at most {MAX_UPLOAD_BYTES} bytes")
        return Evidence(
            id=upload.id,
            task_id=upload.task_id,
            case_id=upload.case_id,
            kind=upload.kind,
            gcs_uri=self._storage.gcs_uri(upload.object_name),
            sha256=hashlib.sha256(data).hexdigest(),
            point=completion.point,
            captured_at=completion.captured_at,
            verdict=None,
            location_ok=None,
            uploaded_by=upload.uploaded_by,
            sample=upload.sample,
        )

    def _stored_after_race(self, evidence_id: str) -> Evidence:
        stored = self._evidence.get(evidence_id)
        if stored is None:
            raise TaskClosed(f"the task or case of {evidence_id!r} changed; try again")
        return stored

    def _cancel_deadline(self, task: Task, evidence_id: str) -> None:
        if self._scheduler is None:
            return
        try:
            self._scheduler.cancel(task.cloud_task_name)
        except Exception as error:
            logger.warning(
                "deadline cancel failed",
                exc_info=True,
                extra=log_fields(
                    "deadline_cancel_failed",
                    evidence_id,
                    task_id=task.id,
                    kind=type(error).__name__,
                ),
            )

    def _publish(self, evidence: Evidence, case: Case, now: datetime) -> None:
        event = EvidenceReceivedEvent(
            id=self._new_id(),
            type="evidence.received",
            occurred_at=now,
            region=case.region,
            example=case.example,
            payload=EvidenceReceived(
                evidence_id=evidence.id, task_id=evidence.task_id, case_id=case.id
            ),
        )
        try:
            self._publisher.publish("evidence.received", event)
        except Exception as error:
            logger.error(
                "evidence publish failed",
                extra=log_fields(
                    "evidence_publish_failed",
                    evidence.id,
                    case_id=case.id,
                    kind=type(error).__name__,
                ),
            )
            raise PublishFailed(
                "the evidence is stored; send complete again"
            ) from error
