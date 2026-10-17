from typing import Annotated

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from auth import Principal, get_principal, require_role
from tests.fakes import FakeVerifier


def make_client(settings, claims):
    app = FastAPI()
    app.state.settings = settings
    app.state.verifier = FakeVerifier(claims)

    @app.get("/brigade-only")
    def brigade_only(
        principal: Annotated[Principal, Depends(require_role("brigade", "ops"))],
    ):
        return {"uid": principal.uid}

    @app.get("/me")
    def me(principal: Annotated[Principal, Depends(get_principal)]):
        return {"role": principal.role, "source": principal.role_source}

    return TestClient(app)


def test_require_role_accepts_any_listed_role(settings):
    client = make_client(settings, {"t": {"uid": "u1", "role": "brigade"}})

    response = client.get("/brigade-only", headers={"Authorization": "Bearer t"})

    assert response.status_code == 200
    assert response.json() == {"uid": "u1"}


def test_require_role_rejects_a_role_outside_the_list(settings):
    client = make_client(settings, {"t": {"uid": "u1", "role": "volunteer"}})

    response = client.get("/brigade-only", headers={"Authorization": "Bearer t"})

    assert response.status_code == 403


def test_a_principal_without_a_role_is_403_on_a_guarded_route(settings):
    client = make_client(settings, {"t": {"uid": "u1"}})

    response = client.get("/brigade-only", headers={"Authorization": "Bearer t"})

    assert response.status_code == 403


def test_get_principal_carries_the_role_source(settings):
    client = make_client(settings, {"t": {"uid": "u1", "role": "brigade"}})

    response = client.get("/me", headers={"Authorization": "Bearer t"})

    assert response.json() == {"role": "brigade", "source": "claim"}


def test_get_principal_with_no_role_has_no_source(settings):
    client = make_client(settings, {"t": {"uid": "u1"}})

    response = client.get("/me", headers={"Authorization": "Bearer t"})

    assert response.json() == {"role": None, "source": None}
