from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import Response

from area_queries import (
    AreaQueries,
    CellsBusy,
    NoRankings,
    UnknownCell,
    needs_explanation,
)
from auth import Principal, require_role
from casework.rank_explanation import RankExplainer
from config import Settings
from contracts import CellFacts, Rankings
from ee_lib.config import UnknownRegion, load_region

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


ALL_CELLS_CACHE_CONTROL = "private, max-age=300"


@router.get("/cells")
async def all_cells(region: str, request: Request, _: OpsReader) -> Response:
    settings: Settings = request.app.state.settings
    try:
        load_region(settings.config_dir, region)
        cells = await run_in_threadpool(queries(request).all_cells, region)
    except (UnknownRegion, NoRankings) as error:
        raise HTTPException(status_code=404, detail="no_rankings") from error
    except CellsBusy as error:
        raise HTTPException(status_code=503, detail="cells_busy") from error
    return Response(
        cells.body,
        media_type="application/json",
        headers={"Cache-Control": ALL_CELLS_CACHE_CONTROL},
    )


def explainer(request: Request) -> RankExplainer:
    return request.app.state.rank_explainer


@router.get("/cells/{cell_id}", response_model=CellFacts)
async def cell_facts(cell_id: str, request: Request, _: OpsReader) -> CellFacts:
    try:
        facts = await run_in_threadpool(queries(request).cell_facts, cell_id)
    except UnknownCell as error:
        raise HTTPException(status_code=404, detail="cell_not_found") from error
    if not needs_explanation(facts, request.app.state.explained_region):
        return facts
    explanation = await explainer(request).explain(cell_id)
    return facts.model_copy(update={"explanation": explanation})
