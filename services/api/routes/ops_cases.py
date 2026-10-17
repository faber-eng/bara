import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request

from auth import Principal, require_role
from case_queries import CaseQueries, UnknownCase
from contracts import Case, CaseDetail, CaseStatus, CaseSummary
from domain.case_machine import IllegalTransition

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")

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
