from fastapi import FastAPI
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

import main
from adapters.gemini import ModelGateway
from auth import require_volunteer_owner
from config import JudgeMode
from routes.volunteer import volunteer_router
from tests.fakes import FakeModels, FakeVerifier

TOKENS = {
    "a": {"uid": "A", "role": "volunteer"},
    "repair": {"uid": "A", "role": "repair_team"},
    "patrol": {"uid": "A", "role": "patrol"},
    "ops": {"uid": "A", "role": "ops"},
    "brigade": {"uid": "A", "role": "brigade"},
    "bare": {"uid": "A"},
    "judge-anon": {"uid": "J"},
}


def bearer(token, **headers):
    return {"Authorization": f"Bearer {token}", **headers}


def make_client(settings, judge=False):
    configured = settings.model_copy(
        update={"judge_mode": JudgeMode(enabled=judge, max_resets_per_hour=20)}
    )
    app = FastAPI()
    app.state.settings = configured
    app.state.verifier = FakeVerifier(TOKENS)
    router = volunteer_router()

    @router.get("/inbox")
    def inbox(volunteer_id: str):
        return {"volunteer_id": volunteer_id}

    app.include_router(router)
    return TestClient(app)


def test_a_volunteer_reads_their_own_path(settings):
    response = make_client(settings).get("/api/v/A/inbox", headers=bearer("a"))

    assert response.status_code == 200
    assert response.json() == {"volunteer_id": "A"}


def test_a_volunteer_gets_403_on_another_path(settings):
    response = make_client(settings).get("/api/v/B/inbox", headers=bearer("a"))

    assert response.status_code == 403


def test_repair_team_and_patrol_claims_are_owners_of_their_own_path(settings):
    client = make_client(settings)

    for token in ("repair", "patrol"):
        assert client.get("/api/v/A/inbox", headers=bearer(token)).status_code == 200
        assert client.get("/api/v/B/inbox", headers=bearer(token)).status_code == 403


def test_an_ops_claim_is_403_even_on_its_own_uid(settings):
    client = make_client(settings)

    assert client.get("/api/v/A/inbox", headers=bearer("ops")).status_code == 403
    assert client.get("/api/v/A/inbox", headers=bearer("brigade")).status_code == 403


def test_no_role_is_403(settings):
    assert (
        make_client(settings).get("/api/v/A/inbox", headers=bearer("bare")).status_code
        == 403
    )


def test_no_token_is_401(settings):
    assert make_client(settings).get("/api/v/A/inbox").status_code == 401


def test_judge_on_a_volunteer_header_reaches_any_uid(settings):
    client = make_client(settings, judge=True)

    response = client.get(
        "/api/v/B/inbox", headers=bearer("judge-anon", **{"X-Bara-Role": "volunteer"})
    )

    assert response.status_code == 200


def test_judge_on_an_ops_header_is_403_on_a_volunteer_path(settings):
    client = make_client(settings, judge=True)

    response = client.get(
        "/api/v/B/inbox", headers=bearer("judge-anon", **{"X-Bara-Role": "ops"})
    )

    assert response.status_code == 403


def test_judge_off_a_volunteer_header_does_not_open_another_uid(settings):
    client = make_client(settings, judge=False)

    response = client.get(
        "/api/v/B/inbox", headers=bearer("judge-anon", **{"X-Bara-Role": "volunteer"})
    )

    assert response.status_code == 403


def test_every_volunteer_route_of_the_app_carries_the_guard(settings):
    gateway = ModelGateway(
        settings.models, {"reasoning": FakeModels([]), "fast": FakeModels([])}
    )
    app = main.build_app(settings, gateway, FakeVerifier({}))

    volunteer_routes = [
        route
        for route in app.routes
        if isinstance(route, APIRoute) and route.path.startswith("/api/v/")
    ]

    for route in volunteer_routes:
        guards = [dependency.call for dependency in route.dependant.dependencies]
        assert require_volunteer_owner in guards, route.path
