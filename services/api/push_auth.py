import logging
from collections.abc import Mapping
from typing import Annotated, Protocol

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials
from google.auth.exceptions import GoogleAuthError, TransportError
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token

from auth import (
    InvalidToken,
    VerifierUnavailable,
    bearer_scheme,
    forbidden,
    unauthorized,
    unavailable,
)

logger = logging.getLogger(__name__)


class OidcVerifier(Protocol):
    def verify(self, token: str, audience: str) -> Mapping[str, object]: ...


class GoogleOidcVerifier:
    def __init__(self):
        self._request = google_requests.Request()

    def verify(self, token: str, audience: str) -> Mapping[str, object]:
        try:
            return id_token.verify_oauth2_token(token, self._request, audience)
        except TransportError as error:
            raise VerifierUnavailable(type(error).__name__) from error
        except (ValueError, GoogleAuthError) as error:
            raise InvalidToken(type(error).__name__) from error


def reject(reason: str, error: HTTPException) -> HTTPException:
    logger.warning("push rejected", extra={"fields": {"reason": reason}})
    return error


def read_claims(
    verifier: OidcVerifier, audience: str, credentials: HTTPAuthorizationCredentials
) -> Mapping[str, object]:
    try:
        return verifier.verify(credentials.credentials, audience)
    except InvalidToken as error:
        raise reject("invalid_token", unauthorized()) from error
    except VerifierUnavailable as error:
        raise reject("verifier_unavailable", unavailable()) from error


def require_push_caller(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> str:
    settings = request.app.state.settings
    if settings.api_url is None:
        raise reject("no_audience", unavailable())
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise reject("no_bearer", unauthorized())
    audience = settings.api_url.rstrip("/")
    claims = read_claims(request.app.state.push_verifier, audience, credentials)
    email = claims.get("email")
    if (
        email != settings.tasks_invoker_email
        or claims.get("email_verified") is not True
    ):
        raise reject("wrong_caller", forbidden())
    return email
