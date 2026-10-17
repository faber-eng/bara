from fastapi.testclient import TestClient

import main
from adapters.gemini import ModelGateway
from config import JudgeMode
from tests.fakes import FakeModels, FakeVerifier

TOKENS = {
    "vol": {"uid": "u-vol", "role": "volunteer"},
    "ops": {"uid": "u-ops", "role": "ops"},
    "anon": {"uid": "u-anon"},
}


def make_client(settings, judge):
    configured = settings.model_copy(
        update={"judge_mode": JudgeMode(enabled=judge, max_resets_per_hour=20)}
    )
    gateway = ModelGateway(
        configured.models, {"reasoning": FakeModels([]), "fast": FakeModels([])}
    )
    return TestClient(main.build_app(configured, gateway, FakeVerifier(TOKENS)))


def probe(client, token, role):
    return client.get(
        "/api/auth/ops-probe",
        headers={"Authorization": f"Bearer {token}", "X-Bara-Role": role},
    )


def test_judge_off_an_ops_header_without_an_ops_claim_is_403(settings):
    assert probe(make_client(settings, False), "vol", "ops").status_code == 403
    assert probe(make_client(settings, False), "anon", "ops").status_code == 403


def test_judge_off_a_real_ops_claim_wins_over_a_volunteer_header(settings):
    response = probe(make_client(settings, False), "ops", "volunteer")

    assert response.status_code == 200
    assert response.json() == {"uid": "u-ops", "role": "ops"}


def test_judge_on_the_header_wins_over_the_claim(settings):
    client = make_client(settings, True)

    assert probe(client, "vol", "ops").status_code == 200
    assert probe(client, "ops", "volunteer").status_code == 403
