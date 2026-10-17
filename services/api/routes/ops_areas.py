from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from area_queries import AreaQueries, NoRankings, UnknownCell
from auth import Principal, require_role
from contracts import CellFacts, Rankings

router = APIRouter(prefix="/api")

OpsReader = Annotated[Principal, Depends(require_role("ops", "judge"))]
WeekQuery = Annotated[str | None, Query(pattern=r"^\d{4}-W\d{2}$")]


def queries(request: Request) -> AreaQueries:
    return request.app.state.area_queries


@router.get("/rankings/{region}", response_model=Rankings)
def region_rankings(
    region: str, request: Request, _: OpsReader, week: WeekQuery = None
) -> Rankings:
    try:
        return queries(request).rankings(region, week)
    except NoRankings as error:
        raise HTTPException(status_code=404, detail="no_rankings") from error


@router.get("/cells/{cell_id}", response_model=CellFacts)
def cell_facts(cell_id: str, request: Request, _: OpsReader) -> CellFacts:
    try:
        return queries(request).cell_facts(cell_id)
    except UnknownCell as error:
        raise HTTPException(status_code=404, detail="cell_not_found") from error
