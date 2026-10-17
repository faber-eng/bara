import asyncio
import logging
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from auth import Principal, require_role
from case_queries import CaseQueries, UnknownCase
from casework.escalation import EscalationRejected
from casework.review import NotInReview, ReviewRejected, UnknownReviewCase
from contracts import Case, CaseDetail, CaseStatus, CaseSummary, ReviewRequest
from domain.case_machine import IllegalTransition
from run_stream import RunStreamer, StreamEvent, render

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")

SSE_HEADERS = {"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"}

OpsReader = Annotated[Principal, Depends(require_role("ops", "judge"))]


def queries(request: Request) -> CaseQueries:
    return request.app.state.case_queries


@router.get("/cases", response_model=list[CaseSummary])
def list_cases(
    request: Request,
    _: OpsReader,
    region: str | None = None,
    status: CaseStatus | None = None,
) -> list[CaseSummary]:
    return queries(request).summaries(region, status)


@router.get("/cases/{case_id}", response_model=CaseDetail)
def case_detail(case_id: str, request: Request, _: OpsReader) -> CaseDetail:
    try:
        return queries(request).detail(case_id)
    except UnknownCase as error:
        raise HTTPException(status_code=404, detail="case_not_found") from error


def streamer(request: Request) -> RunStreamer:
    return request.app.state.run_streamer


async def sse_body(events: AsyncIterator[StreamEvent]) -> AsyncIterator[str]:
    async for event in events:
        yield render(event)


@router.get("/cases/{case_id}/stream")
async def stream_agent_run(
    case_id: str, request: Request, _: OpsReader
) -> StreamingResponse:
    run_streamer = streamer(request)
    try:
        await run_streamer.require_case(case_id)
    except UnknownCase as error:
        raise HTTPException(status_code=404, detail="case_not_found") from error
    return StreamingResponse(
        sse_body(run_streamer.events(case_id)),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )


@router.post("/cases/{case_id}/close", response_model=Case)
def close_case(case_id: str, request: Request, principal: OpsReader) -> Case:
    try:
        return queries(request).close(case_id, principal.uid)
    except UnknownCase as error:
        raise HTTPException(status_code=404, detail="case_not_found") from error
    except IllegalTransition as error:
        logger.warning(
            "close refused",
            extra={"fields": {"case_id": case_id, "from": error.current}},
        )
        raise HTTPException(status_code=409, detail="illegal_transition") from error


@router.post("/cases/{case_id}/review", response_model=Case)
def review_case(
    case_id: str, body: ReviewRequest, request: Request, principal: OpsReader
) -> Case:
    desk = request.app.state.review_desk
    try:
        return asyncio.run(desk.resolve(case_id, body, principal.uid))
    except UnknownReviewCase as error:
        raise HTTPException(status_code=404, detail="case_not_found") from error
    except NotInReview as error:
        raise HTTPException(status_code=409, detail="not_in_review") from error
    except ReviewRejected as error:
        raise HTTPException(status_code=409, detail="review_rejected") from error
    except EscalationRejected as error:
        logger.warning(
            "review escalation refused",
            extra={"fields": {"case_id": case_id, "error": str(error)}},
        )
        raise HTTPException(status_code=409, detail="escalation_rejected") from error
