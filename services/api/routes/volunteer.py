from fastapi import APIRouter, Depends, HTTPException, Request

from auth import require_volunteer_owner
from casework.evidence_intake import (
    EvidenceIntake,
    IntakeError,
    PublishFailed,
    TaskClosed,
    UnknownTask,
    UnknownUpload,
    UploadMissing,
    UploadTooLarge,
)
from casework.inbox import InboxReader
from contracts import CompleteRequest, Evidence, Inbox, UploadRequest, UploadTicket
from domain.evidence import UnsupportedMedia

INTAKE_ERRORS: dict[type[Exception], tuple[int, str]] = {
    UnknownUpload: (404, "upload_not_found"),
    UnknownTask: (404, "task_not_found"),
    TaskClosed: (409, "task_closed"),
    UploadMissing: (409, "upload_missing"),
    UploadTooLarge: (413, "upload_too_large"),
    UnsupportedMedia: (422, "unsupported_media"),
    PublishFailed: (503, "publish_failed"),
}


def volunteer_router() -> APIRouter:
    return APIRouter(
        prefix="/api/v/{volunteer_id}", dependencies=[Depends(require_volunteer_owner)]
    )


router = volunteer_router()


def intake(request: Request) -> EvidenceIntake:
    return request.app.state.evidence_intake


def inbox_reader(request: Request) -> InboxReader:
    return request.app.state.inbox_reader


def http_error(error: Exception) -> HTTPException:
    status, detail = INTAKE_ERRORS[type(error)]
    return HTTPException(status_code=status, detail=detail)


@router.get("/inbox", response_model=Inbox)
def read_inbox(volunteer_id: str, request: Request) -> Inbox:
    return inbox_reader(request).read(volunteer_id)


@router.post("/uploads", response_model=UploadTicket)
def request_upload(
    volunteer_id: str, body: UploadRequest, request: Request
) -> UploadTicket:
    try:
        return intake(request).request_upload(volunteer_id, body)
    except (IntakeError, UnsupportedMedia) as error:
        raise http_error(error) from error


@router.post("/evidence/{evidence_id}/complete", response_model=Evidence)
def complete_upload(
    volunteer_id: str, evidence_id: str, body: CompleteRequest, request: Request
) -> Evidence:
    try:
        return intake(request).complete(volunteer_id, evidence_id, body)
    except (IntakeError, UnsupportedMedia) as error:
        raise http_error(error) from error
