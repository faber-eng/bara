import logging

import pytest
from fastapi.testclient import TestClient

import main
from adapters.gemini import ModelGateway
from auth import (
    InvalidRoleHeader,
    RoleResolution,
    resolve_role,
)
from config import JudgeMode
from tests.fakes import FakeModels, FakeVerifier

OPS_TOKEN = "token-ops-secret"
VOLUNTEER_TOKEN = "token-volunteer-secret"
ANON_TOKEN = "token-anonymous-secret"
REPAIR_TOKEN = "token-repair-secret"
CLAIMS = {
    OPS_TOKEN: {"uid": "u-ops", "role": "ops"},
    VOLUNTEER_TOKEN: {"uid": "u-vol", "role": "volunteer"},
    REPAIR_TOKEN: {"uid": "u-repair", "role": "repair_team"},
    ANON_TOKEN: {"uid": "u-anon"},
}


@pytest.mark.parametrize(
    ("claims", "header", "judge", "role", "source"),
    [
        ({"role": "volunteer"}, "ops", True, "ops", "header"),
        ({"role": "brigade"}, None, True, "brigade", "claim"),
        ({"role": "volunteer"}, "ops", False, "volunteer", "claim"),
        ({}, "ops", False, None, None),
        ({}, None, True, None, None),
        ({}, None, False, None, None),
        ({"role": "repair_team"}, None, False, "volunteer", "claim"),
        ({"role": "patrol"}, None, False, "volunteer", "claim"),
        ({}, "judge", True, "judge", "header"),
        ({"role": "root"}, None, False, None, None),
        ({"role": 7}, None, False, None, None),
    ],
)
def test_resolve_role_table(claims, header, judge, role, source):
    assert resolve_role(claims, header, judge) == RoleResolution(role, source)


def test_resolve_role_reports_a_header_decision_as_header():
    resolution = resolve_role({"role": "volunteer"}, "ops", True)

    assert resolution.source == "header"


def test_resolve_role_reports_a_claim_decision_as_claim():
    resolution = resolve_role({"role": "ops"}, "volunteer", False)

    assert resolution.source == "claim"


def test_resolve_role_rejects_an_unknown_header_when_judge_mode_is_on():
    with pytest.raises(InvalidRoleHeader):
        resolve_role({"role": "ops"}, "root", True)


def test_resolve_role_ignores_an_unknown_header_when_judge_mode_is_off():
    assert resolve_role({"role": "ops"}, "root", False) == RoleResolution(
        "ops", "claim"
    )


def make_client(settings, judge):
    judged = settings.model_copy(
        update={"judge_mode": JudgeMode(enabled=judge, max_resets_per_hour=20)}
    )
    gateway = ModelGateway(
        judged.models, {"reasoning": FakeModels([]), "fast": FakeModels([])}
    )
    verifier = FakeVerifier(CLAIMS)
    return TestClient(main.build_app(judged, gateway, verifier)), verifier


def bearer(token):
    return {"Authorization": f"Bearer {token}"}


def test_no_authorization_header_is_401(settings):
    client, _ = make_client(settings, judge=False)

    response = client.get("/api/auth/ops-probe")

    assert response.status_code == 401


def test_a_non_bearer_scheme_is_401(settings):
    client, _ = make_client(settings, judge=False)

    response = client.get(
        "/api/auth/ops-probe", headers={"Authorization": f"Basic {OPS_TOKEN}"}
    )

    assert response.status_code == 401


def test_a_bad_token_is_401(settings):
    client, _ = make_client(settings, judge=False)

    response = client.get("/api/auth/ops-probe", headers=bearer("garbage"))

    assert response.status_code == 401


def test_a_volunteer_on_an_ops_route_is_403(settings):
    client, _ = make_client(settings, judge=False)

    response = client.get("/api/auth/ops-probe", headers=bearer(VOLUNTEER_TOKEN))

    assert response.status_code == 403


def test_a_repair_team_claim_is_a_volunteer_so_403_on_ops(settings):
    client, _ = make_client(settings, judge=False)

    response = client.get("/api/auth/ops-probe", headers=bearer(REPAIR_TOKEN))

    assert response.status_code == 403


def test_an_ops_claim_with_judge_mode_off_is_200(settings):
    client, _ = make_client(settings, judge=False)

    response = client.get("/api/auth/ops-probe", headers=bearer(OPS_TOKEN))

    assert response.status_code == 200
    assert response.json() == {"uid": "u-ops", "role": "ops"}


def test_judge_off_ignores_an_ops_header_on_an_anonymous_token(settings):
    client, _ = make_client(settings, judge=False)

    response = client.get(
        "/api/auth/ops-probe", headers={**bearer(ANON_TOKEN), "X-Bara-Role": "ops"}
    )

    assert response.status_code == 403


def test_judge_on_accepts_an_ops_header_on_an_anonymous_token(settings):
    client, _ = make_client(settings, judge=True)

    response = client.get(
        "/api/auth/ops-probe", headers={**bearer(ANON_TOKEN), "X-Bara-Role": "ops"}
    )

    assert response.status_code == 200
    assert response.json() == {"uid": "u-anon", "role": "ops"}


def test_judge_on_header_wins_over_the_claim(settings):
    client, _ = make_client(settings, judge=True)

    response = client.get(
        "/api/auth/ops-probe",
        headers={**bearer(VOLUNTEER_TOKEN), "X-Bara-Role": "ops"},
    )

    assert response.status_code == 200


def test_judge_on_an_unknown_header_is_403(settings):
    client, _ = make_client(settings, judge=True)

    response = client.get(
        "/api/auth/ops-probe", headers={**bearer(OPS_TOKEN), "X-Bara-Role": "root"}
    )

    assert response.status_code == 403


def test_judge_on_still_verifies_the_token(settings):
    client, _ = make_client(settings, judge=True)

    response = client.get("/api/auth/ops-probe", headers={"X-Bara-Role": "ops"})

    assert response.status_code == 401


def test_judge_on_a_bad_token_with_an_ops_header_is_401(settings):
    client, _ = make_client(settings, judge=True)

    response = client.get(
        "/api/auth/ops-probe", headers={**bearer("garbage"), "X-Bara-Role": "ops"}
    )

    assert response.status_code == 401


def test_health_stays_public(settings):
    client, verifier = make_client(settings, judge=False)

    response = client.get("/api/health")

    assert response.status_code == 200
    assert verifier.seen == []


def test_a_403_body_carries_no_token_or_claims(settings):
    client, _ = make_client(settings, judge=False)

    response = client.get("/api/auth/ops-probe", headers=bearer(VOLUNTEER_TOKEN))

    assert VOLUNTEER_TOKEN not in response.text
    assert "u-vol" not in response.text
    assert "volunteer" not in response.text


def test_tokens_are_never_logged(settings, caplog):
    client, _ = make_client(settings, judge=False)

    with caplog.at_level(logging.DEBUG):
        client.get("/api/auth/ops-probe", headers=bearer("garbage-secret-token"))
        client.get("/api/auth/ops-probe", headers=bearer(VOLUNTEER_TOKEN))

    assert "garbage-secret-token" not in caplog.text
    assert VOLUNTEER_TOKEN not in caplog.text


def test_the_firebase_verifier_turns_a_malformed_token_into_invalid_token():
    import firebase_admin

    from auth import FirebaseTokenVerifier, InvalidToken

    app = firebase_admin.initialize_app(
        options={"projectId": "example-project"}, name="verifier-test"
    )
    try:
        with pytest.raises(InvalidToken):
            FirebaseTokenVerifier(app).verify("not-a-jwt")
    finally:
        firebase_admin.delete_app(app)
