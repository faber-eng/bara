from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import JSONResponse

from contracts import (
    PublicBulletin,
    PublicCells,
    PublicDam,
    PublicSummary,
    RecordLine,
)
from ee_lib.weeks import FutureWeek, InvalidWeek, resolve_week
from public.export import LICENSE, csv_export, geojson_export
from public_queries import (
    CELL_LIMIT,
    RECORD_LIMIT,
    NoRankings,
    PublicQueries,
    UnknownRegion,
)
from ratelimit import RequestLimiter

CACHE_CONTROL = "public, max-age=300"
TRUSTED_PROXY_HOPS = 1
RANKED_LIMIT_MAX = 200
RECORD_LIMIT_MAX = 200


def client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    hops = [hop.strip() for hop in forwarded.split(",") if hop.strip()]
    if len(hops) > TRUSTED_PROXY_HOPS:
        return hops[-1 - TRUSTED_PROXY_HOPS]
    if hops:
        return hops[-1]
    return request.client.host if request.client else "unknown"


def throttle(request: Request) -> None:
    limiter: RequestLimiter = request.app.state.public_limiter
    retry_after = limiter.hit(client_ip(request))
    if retry_after:
        raise HTTPException(
            status_code=429,
            detail="rate_limited",
            headers={"Retry-After": str(retry_after)},
        )


def cacheable(response: Response) -> None:
    response.headers["Cache-Control"] = CACHE_CONTROL


router = APIRouter(
    prefix="/api/public/{region}", dependencies=[Depends(throttle), Depends(cacheable)]
)


def queries(request: Request) -> PublicQueries:
    return request.app.state.public_queries


def region_zone(request: Request, region: str) -> ZoneInfo:
    try:
        return queries(request).zone(region)
    except UnknownRegion as error:
        raise HTTPException(status_code=404, detail="region_not_found") from error


def checked_week(request: Request, region: str, week: str | None) -> str | None:
    zone = region_zone(request, region)
    if week is None:
        return None
    try:
        resolve_week(week, request.app.state.utcnow(), zone)
    except (InvalidWeek, FutureWeek) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return week


@router.get("/summary", response_model=PublicSummary)
def summary(request: Request, region: str, week: str | None = None) -> PublicSummary:
    label = checked_week(request, region, week)
    try:
        return queries(request).summary(region, label, request.app.state.utcnow())
    except NoRankings as error:
        raise HTTPException(status_code=404, detail="no_rankings") from error


@router.get("/cells", response_model=PublicCells)
def cells(
    request: Request,
    region: str,
    week: str | None = None,
    limit: Annotated[int, Query(ge=1, le=RANKED_LIMIT_MAX)] = CELL_LIMIT,
) -> PublicCells:
    label = checked_week(request, region, week)
    try:
        return queries(request).cells(region, label, limit)
    except NoRankings as error:
        raise HTTPException(status_code=404, detail="no_rankings") from error


@router.get("/dams", response_model=list[PublicDam])
def dams(request: Request, region: str) -> list[PublicDam]:
    region_zone(request, region)
    return queries(request).dams(region)


@router.get("/record", response_model=list[RecordLine])
def record(
    request: Request,
    region: str,
    limit: Annotated[int, Query(ge=1, le=RECORD_LIMIT_MAX)] = RECORD_LIMIT,
) -> list[RecordLine]:
    region_zone(request, region)
    return queries(request).record(region, limit)


@router.get("/bulletin", response_model=PublicBulletin)
def bulletin(request: Request, region: str, week: str | None = None) -> PublicBulletin:
    label = checked_week(request, region, week)
    try:
        return queries(request).bulletin(region, label)
    except NoRankings as error:
        raise HTTPException(status_code=404, detail="no_rankings") from error


def export_cells(request: Request, region: str, week: str | None):
    label = checked_week(request, region, week)
    try:
        return queries(request).cells(region, label, RANKED_LIMIT_MAX)
    except NoRankings as error:
        raise HTTPException(status_code=404, detail="no_rankings") from error


def export_headers(region: str, week: str, extension: str) -> dict[str, str]:
    return {
        "Cache-Control": CACHE_CONTROL,
        "Content-Disposition": f'attachment; filename="bara-{region}-{week}.{extension}"',
        "X-License": LICENSE,
    }


@router.get("/export.csv")
def export_csv(request: Request, region: str, week: str | None = None) -> Response:
    result = export_cells(request, region, week)
    return Response(
        csv_export(region, result.week, result.cells),
        media_type="text/csv; charset=utf-8",
        headers=export_headers(region, result.week, "csv"),
    )


@router.get("/export.geojson")
def export_geojson(request: Request, region: str, week: str | None = None) -> Response:
    result = export_cells(request, region, week)
    body = geojson_export(region, result.week, result.cells)
    return JSONResponse(
        body,
        media_type="application/geo+json",
        headers=export_headers(region, result.week, "geojson"),
    )
