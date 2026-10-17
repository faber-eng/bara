from types import SimpleNamespace

from fastapi.testclient import TestClient

import main
from adapters.firestore_repos import VolunteerRepository
from adapters.gemini import ModelGateway
from config import JudgeMode
from contracts import Volunteer
from ratelimit import FailureLimiter
from tests.fakes import (
    FakeClaimsAdmin,
    FakeModels,
    FakeSecretReader,
    FakeVerifier,
    InMemoryCollection,
)

GOOGLE = {"firebase": {"sign_in_provider": "google.com"}}
ANONYMOUS = {"firebase": {"sign_in_provider": "anonymous"}}
GOOGLE_TOKEN = "token-google-secret"
ANON_TOKEN = "token-anon-secret"
CLAIMS = {
    GOOGLE_TOKEN: {"uid": "u-google", **GOOGLE},
    "token-google-2": {"uid": "u-other", **GOOGLE},
    ANON_TOKEN: {"uid": "u-anon", **ANONYMOUS},
    "token-no-provider": {"uid": "u-bare"},
    "token-ops": {"uid": "u-ops", "role": "ops", **GOOGLE},
}
CODE = "bara-secret"

BODY = {
    "invite_code": CODE,
    "name": "Sari",
    "home": {"lat": 0.5, "lon": 101.4},
    "language": "id",
    "whatsapp": "+6281234567890",
}


def bearer(token):
    return {"Authorization": f"Bearer {token}"}


def make_join_app(settings, judge=False, secrets=None, admin=None, limiter=None):
    configured = settings.model_copy(
        update={"judge_mode": JudgeMode(enabled=judge, max_resets_per_hour=20)}
    )
    gateway = ModelGateway(
        configured.models, {"reasoning": FakeModels([]), "fast": FakeModels([])}
    )
    app = main.build_app(configured, gateway, FakeVerifier(CLAIMS))
    collection = InMemoryCollection(Volunteer)
    app.state.adapters = SimpleNamespace(
        volunteers=VolunteerRepository(collection),
        secrets=secrets or FakeSecretReader(CODE),
        claims=admin or FakeClaimsAdmin(),
    )
    if limiter is not None:
        app.state.join_limiter = limiter
    return TestClient(app), collection


def make_limiter(clock):
    return FailureLimiter(max_failures=5, window_seconds=900, clock=clock)
