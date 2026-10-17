from typing import Annotated

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from auth import InvalidToken, VerifierUnavailable
from push_auth import GoogleOidcVerifier, require_push_caller

API_URL = "https://api.example.test"


class FakeOidc:
    def __init__(self, claims=None, error: Exception | None = None):
        self._claims = claims
        self._error = error
        self.calls: list[tuple[str, str]] = []

    def verify(self, token, audience):
        self.calls.append((token, audience))
        if self._error:
            raise self._error
        return self._claims


def make_client(settings, verifier, api_url=API_URL):
    app = FastAPI()
    app.state.settings = settings.model_copy(update={"api_url": api_url})
    app.state.push_verifier = verifier

    @app.post("/guarded")
    def guarded(email: Annotated[str, Depends(require_push_caller)]):
        return {"email": email}

    return TestClient(app)


def good_claims(settings, **overrides):
    return {
        "email": settings.tasks_invoker_email,
        "email_verified": True,
        **overrides,
    }


def post(client, token="t"):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    return client.post("/guarded", headers=headers)


def test_the_invoker_with_a_valid_token_passes_and_audience_is_the_api_url(settings):
    verifier = FakeOidc(good_claims(settings))

    response = post(make_client(settings, verifier))

    assert response.status_code == 200
    assert response.json() == {"email": settings.tasks_invoker_email}
    assert verifier.calls == [("t", API_URL)]


def test_no_bearer_is_401(settings):
    assert (
        post(make_client(settings, FakeOidc(good_claims(settings))), None).status_code
        == 401
    )


def test_a_token_that_fails_verification_is_401(settings):
    client = make_client(settings, FakeOidc(error=InvalidToken("bad")))

    assert post(client).status_code == 401


def test_another_service_account_is_403(settings):
    claims = good_claims(settings, email="someone@example.iam.gserviceaccount.com")

    assert post(make_client(settings, FakeOidc(claims))).status_code == 403


def test_an_unverified_email_is_403(settings):
    claims = good_claims(settings, email_verified=False)

    assert post(make_client(settings, FakeOidc(claims))).status_code == 403


def test_a_token_without_an_email_is_403(settings):
    assert post(make_client(settings, FakeOidc({}))).status_code == 403


def test_certificate_fetch_failure_is_503(settings):
    client = make_client(settings, FakeOidc(error=VerifierUnavailable("net")))

    assert post(client).status_code == 503


def test_with_no_api_url_the_route_fails_closed(settings):
    client = make_client(settings, FakeOidc(good_claims(settings)), api_url=None)

    assert post(client).status_code == 503


def test_the_google_verifier_turns_a_bad_token_into_invalid_token():
    with pytest.raises(InvalidToken):
        GoogleOidcVerifier().verify("not-a-jwt", API_URL)


def test_a_trailing_slash_on_the_api_url_does_not_change_the_audience(settings):
    verifier = FakeOidc(good_claims(settings))

    post(make_client(settings, verifier, api_url=API_URL + "/"))

    assert verifier.calls == [("t", API_URL)]


def test_any_other_google_auth_error_becomes_invalid_token(monkeypatch):
    from google.auth.exceptions import GoogleAuthError

    def wrong_issuer(token, request, audience):
        raise GoogleAuthError("issuer")

    monkeypatch.setattr("push_auth.id_token.verify_oauth2_token", wrong_issuer)

    with pytest.raises(InvalidToken):
        GoogleOidcVerifier().verify("t", API_URL)
