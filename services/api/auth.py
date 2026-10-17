import logging
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Annotated, Literal, Protocol, get_args

import firebase_admin
from fastapi import Depends, Header, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from firebase_admin import auth as firebase_auth
from firebase_admin.exceptions import FirebaseError

logger = logging.getLogger(__name__)

Role = Literal["ops", "volunteer", "brigade", "judge"]
RoleSource = Literal["claim", "header"]

ROLES: frozenset[str] = frozenset(get_args(Role))
VOLUNTEER_CLAIM_ALIASES = frozenset({"repair_team", "patrol"})
ROLE_HEADER = "X-Bara-Role"
ANONYMOUS_PROVIDER = "anonymous"

bearer_scheme = HTTPBearer(auto_error=False)


class InvalidToken(Exception):
    pass


class VerifierUnavailable(Exception):
    pass


class InvalidRoleHeader(Exception):
    pass


class TokenVerifier(Protocol):
    def verify(self, token: str) -> Mapping[str, object]: ...


class FirebaseTokenVerifier:
    def __init__(self, app: firebase_admin.App | None = None):
        self._app = app

    def verify(self, token: str) -> Mapping[str, object]:
        try:
            return firebase_auth.verify_id_token(token, app=self._app)
        except firebase_auth.CertificateFetchError as error:
            raise VerifierUnavailable(type(error).__name__) from error
        except (ValueError, FirebaseError) as error:
            raise InvalidToken(type(error).__name__) from error


@dataclass(frozen=True)
class RoleResolution:
    role: Role | None
    source: RoleSource | None


@dataclass(frozen=True)
class Principal:
    uid: str
    role: Role | None
    role_source: RoleSource | None
    provider: str | None = None


def role_from_claim(claims: Mapping[str, object]) -> Role | None:
    claimed = claims.get("role")
    if not isinstance(claimed, str):
        return None
    if claimed in VOLUNTEER_CLAIM_ALIASES:
        return "volunteer"
    if claimed in ROLES:
        return claimed
    return None


def role_from_header(header: str) -> Role:
    if header not in ROLES:
        raise InvalidRoleHeader("unknown role header value")
    return header


def provider_from_claims(claims: Mapping[str, object]) -> str | None:
    firebase = claims.get("firebase")
    if not isinstance(firebase, Mapping):
        return None
    provider = firebase.get("sign_in_provider")
    if not isinstance(provider, str):
        return None
    return provider


def resolve_role(
    claims: Mapping[str, object], header: str | None, judge_mode: bool
) -> RoleResolution:
    if judge_mode and header is not None:
        return RoleResolution(role_from_header(header), "header")
    claimed = role_from_claim(claims)
    if claimed is None:
        return RoleResolution(None, None)
    return RoleResolution(claimed, "claim")


def unauthorized() -> HTTPException:
    return HTTPException(
        status_code=401,
        detail="unauthorized",
        headers={"WWW-Authenticate": "Bearer"},
    )


def forbidden() -> HTTPException:
    return HTTPException(status_code=403, detail="forbidden")


def unavailable() -> HTTPException:
    return HTTPException(status_code=503, detail="auth unavailable")


def verify_claims(
    verifier: TokenVerifier, credentials: HTTPAuthorizationCredentials | None
) -> Mapping[str, object]:
    if credentials is None or credentials.scheme.lower() != "bearer":
        logger.warning("auth rejected", extra={"fields": {"reason": "no_bearer"}})
        raise unauthorized()
    try:
        return verifier.verify(credentials.credentials)
    except InvalidToken as error:
        logger.warning(
            "auth rejected",
            extra={"fields": {"reason": "invalid_token", "kind": str(error)}},
        )
        raise unauthorized() from error
    except VerifierUnavailable as error:
        logger.error(
            "auth unavailable",
            extra={"fields": {"reason": "verifier_unavailable", "kind": str(error)}},
        )
        raise unavailable() from error


def get_principal(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    role_header: Annotated[str | None, Header(alias=ROLE_HEADER)] = None,
) -> Principal:
    claims = verify_claims(request.app.state.verifier, credentials)
    uid = claims.get("uid")
    if not isinstance(uid, str):
        logger.warning("auth rejected", extra={"fields": {"reason": "no_uid"}})
        raise unauthorized()
    judge_mode = request.app.state.settings.judge_mode.enabled
    try:
        resolution = resolve_role(claims, role_header, judge_mode)
    except InvalidRoleHeader as error:
        logger.warning("auth rejected", extra={"fields": {"reason": "bad_role_header"}})
        raise forbidden() from error
    return Principal(
        uid, resolution.role, resolution.source, provider_from_claims(claims)
    )


def require_role(*allowed: Role) -> Callable[[Principal], Principal]:
    def check(principal: Annotated[Principal, Depends(get_principal)]) -> Principal:
        if principal.role not in allowed:
            logger.warning(
                "auth rejected", extra={"fields": {"reason": "role_not_allowed"}}
            )
            raise forbidden()
        return principal

    return check


def require_signed_in_user(
    principal: Annotated[Principal, Depends(get_principal)],
) -> Principal:
    if principal.provider is None or principal.provider == ANONYMOUS_PROVIDER:
        logger.warning("auth rejected", extra={"fields": {"reason": "anonymous"}})
        raise HTTPException(status_code=403, detail="anonymous_not_allowed")
    return principal


def require_volunteer_owner(
    volunteer_id: str, principal: Annotated[Principal, Depends(get_principal)]
) -> Principal:
    if principal.role != "volunteer":
        logger.warning(
            "auth rejected", extra={"fields": {"reason": "role_not_allowed"}}
        )
        raise forbidden()
    if principal.role_source == "claim" and principal.uid != volunteer_id:
        logger.warning("auth rejected", extra={"fields": {"reason": "not_owner"}})
        raise forbidden()
    return principal


def require_brigade_owner(
    contact_id: str, principal: Annotated[Principal, Depends(get_principal)]
) -> Principal:
    if principal.role != "brigade":
        logger.warning(
            "auth rejected", extra={"fields": {"reason": "role_not_allowed"}}
        )
        raise forbidden()
    if principal.role_source == "claim" and principal.uid != contact_id:
        logger.warning("auth rejected", extra={"fields": {"reason": "not_owner"}})
        raise forbidden()
    return principal


def claimed_owner(principal: Principal) -> str | None:
    if principal.role_source == "claim":
        return principal.uid
    return None
