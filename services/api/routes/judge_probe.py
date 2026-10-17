from typing import Annotated

from fastapi import APIRouter, Depends

from auth import Principal, require_role

router = APIRouter(prefix="/api/auth")


@router.get("/ops-probe")
def ops_probe(principal: Annotated[Principal, Depends(require_role("ops"))]) -> dict:
    return {"uid": principal.uid, "role": principal.role}
