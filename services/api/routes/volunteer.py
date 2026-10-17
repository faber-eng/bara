from fastapi import APIRouter, Depends

from auth import require_volunteer_owner


def volunteer_router() -> APIRouter:
    return APIRouter(
        prefix="/api/v/{volunteer_id}", dependencies=[Depends(require_volunteer_owner)]
    )
