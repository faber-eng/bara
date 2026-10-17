import logging
from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException, Request

from adapters.area_limit_store import AreaLimitUnavailable
from adapters.earthengine_area import AreaSourceError
from auth import Principal, require_role
from casework.area_ranking import (
    AreaBusy,
    AreaRanker,
    AreaTimeout,
    OutsideRegions,
    RateLimited,
)
from contracts import AreaRanking
from domain.area_polygon import InvalidPolygon, PolygonTooLarge

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")

OpsUser = Annotated[Principal, Depends(require_role("ops", "judge"))]


def ranker(request: Request) -> AreaRanker:
    return request.app.state.area_ranker


@router.post("/areas/rank", response_model=AreaRanking)
async def rank_area(
    request: Request, principal: OpsUser, polygon: Annotated[dict, Body()]
) -> AreaRanking:
    try:
        return await ranker(request).rank_within_deadline(principal.uid, polygon)
    except InvalidPolygon as error:
        raise HTTPException(
            status_code=422, detail=f"invalid_polygon: {error}"
        ) from error
    except PolygonTooLarge as error:
        raise HTTPException(status_code=422, detail="area_too_large") from error
    except OutsideRegions as error:
        raise HTTPException(status_code=422, detail="outside_regions") from error
    except RateLimited as error:
        raise HTTPException(
            status_code=429,
            detail="area_rank_limit",
            headers={"Retry-After": str(error.retry_after)},
        ) from error
    except AreaLimitUnavailable as error:
        logger.error(
            "area limit store failed",
            extra={"fields": {"uid": principal.uid, "error": str(error)}},
        )
        raise HTTPException(status_code=503, detail="area_limit_unavailable") from error
    except AreaBusy as error:
        raise HTTPException(status_code=503, detail="area_busy") from error
    except AreaTimeout as error:
        raise HTTPException(status_code=504, detail="area_timeout") from error
    except AreaSourceError as error:
        logger.error(
            "area ranking failed",
            extra={"fields": {"uid": principal.uid, "error": str(error)}},
        )
        raise HTTPException(status_code=502, detail="area_source_failed") from error
