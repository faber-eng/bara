import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request

from adapters.identity import IdentityUnavailable
from adapters.secrets import SecretUnavailable
from auth import Principal, require_signed_in_user
from config import Settings, full_flow_region
from contracts import JoinRequest, JoinResponse, Volunteer
from domain.join import (
    build_volunteer,
    claims_after_join,
    codes_match,
    holds_staff_role,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")


def reject_when_limited(request: Request, uid: str) -> None:
    wait = request.app.state.join_limiter.retry_after(uid)
    if wait == 0:
        return
    logger.warning("join blocked", extra={"fields": {"uid": uid, "retry_after": wait}})
    raise HTTPException(
        status_code=429,
        detail="too_many_attempts",
        headers={"Retry-After": str(wait)},
    )


def read_expected_code(request: Request, uid: str) -> str:
    try:
        return request.app.state.adapters.secrets.join_code()
    except SecretUnavailable as error:
        logger.error(
            "join code unreadable", extra={"fields": {"uid": uid, "kind": str(error)}}
        )
        raise HTTPException(status_code=503, detail="join_unavailable") from error


def assert_code(request: Request, uid: str, supplied: str) -> None:
    limiter = request.app.state.join_limiter
    if codes_match(supplied, read_expected_code(request, uid)):
        limiter.clear(uid)
        return
    limiter.record_failure(uid)
    logger.warning("join rejected", extra={"fields": {"uid": uid, "reason": "code"}})
    raise HTTPException(status_code=403, detail="invalid_invite_code")


def assert_not_staff(request: Request, uid: str) -> None:
    try:
        current = request.app.state.adapters.claims.get_claims(uid)
    except IdentityUnavailable as error:
        logger.error(
            "join claim failed", extra={"fields": {"uid": uid, "kind": str(error)}}
        )
        raise HTTPException(status_code=502, detail="role_update_failed") from error
    if holds_staff_role(current):
        logger.warning(
            "join rejected", extra={"fields": {"uid": uid, "reason": "has_role"}}
        )
        raise HTTPException(status_code=409, detail="already_has_role")


def assert_claim(request: Request, uid: str) -> None:
    admin = request.app.state.adapters.claims
    try:
        current = admin.get_claims(uid)
        wanted = claims_after_join(current)
        if wanted != current:
            admin.set_claims(uid, wanted)
    except IdentityUnavailable as error:
        logger.error(
            "join claim failed", extra={"fields": {"uid": uid, "kind": str(error)}}
        )
        raise HTTPException(status_code=502, detail="role_update_failed") from error


def move_home(volunteers, volunteer: Volunteer) -> None:
    existing = volunteers.get(volunteer.id)
    if existing is None or existing.example:
        return
    volunteers.set_home(volunteer.id, volunteer.home)


@router.post("/join", response_model=JoinResponse)
def join(
    body: JoinRequest,
    request: Request,
    principal: Annotated[Principal, Depends(require_signed_in_user)],
) -> JoinResponse:
    settings: Settings = request.app.state.settings
    reject_when_limited(request, principal.uid)
    assert_code(request, principal.uid, body.invite_code)
    assert_not_staff(request, principal.uid)
    volunteer = build_volunteer(
        principal.uid, body, full_flow_region(settings.config_dir)
    )
    volunteers = request.app.state.adapters.volunteers
    created = volunteers.create_if_absent(volunteer)
    if not created:
        move_home(volunteers, volunteer)
    assert_claim(request, principal.uid)
    logger.info("join", extra={"fields": {"uid": principal.uid, "created": created}})
    return JoinResponse(volunteer_id=principal.uid, created=created)
