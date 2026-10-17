import pytest
from fastapi.testclient import TestClient

import main
from adapters.earthengine_area import AreaSourceError
from adapters.gemini import ModelGateway
from contracts import AreaRanking
from domain.area_rank import AreaMeasure
from tests.area_support import (
    FAR_SQUARE,
    RIAU_SQUARE,
    FakeAreaSource,
    make_ranker,
    square,
)
from tests.fakes import FakeModels, FakeVerifier

OPS = {"Authorization": "Bearer ops", "X-Bara-Role": "ops"}


def make_client(settings, ranker):
    gateway = ModelGateway(
        settings.models, {"reasoning": FakeModels([]), "fast": FakeModels([])}
    )
    judge = settings.model_copy(
        update={"judge_mode": settings.judge_mode.model_copy(update={"enabled": True})}
    )
    app = main.build_app(judge, gateway, FakeVerifier({"ops": {"uid": "u1"}}))
    app.state.area_ranker = ranker
    return TestClient(app)


def test_posting_a_polygon_returns_ranked_cells(settings):
    client = make_client(settings, make_ranker(settings))

    response = client.post("/api/areas/rank", json=RIAU_SQUARE, headers=OPS)

    assert response.status_code == 200
    body = AreaRanking.model_validate(response.json())
    assert body.status == "ranked"
    assert body.cells[0].rank == 1


def test_no_mapped_peat_is_a_200_with_status_no_peat(settings):
    ranker = make_ranker(settings, FakeAreaSource(AreaMeasure(0, [], None)))
    client = make_client(settings, ranker)

    response = client.post("/api/areas/rank", json=RIAU_SQUARE, headers=OPS)

    assert response.status_code == 200
    assert response.json()["status"] == "no_peat"


def test_without_a_token_it_is_unauthorized(settings):
    client = make_client(settings, make_ranker(settings))

    assert client.post("/api/areas/rank", json=RIAU_SQUARE).status_code == 401


def test_a_volunteer_is_forbidden(settings):
    client = make_client(settings, make_ranker(settings))
    headers = {"Authorization": "Bearer ops", "X-Bara-Role": "volunteer"}

    assert (
        client.post("/api/areas/rank", json=RIAU_SQUARE, headers=headers).status_code
        == 403
    )


@pytest.mark.parametrize(
    ("body", "detail"),
    [
        ({"type": "Point", "coordinates": [1, 2]}, "invalid_polygon"),
        (square(102.0, 0.0, 0.6), "area_too_large"),
        (FAR_SQUARE, "outside_regions"),
    ],
)
def test_a_refused_polygon_is_422_with_a_reason(settings, body, detail):
    client = make_client(settings, make_ranker(settings))

    response = client.post("/api/areas/rank", json=body, headers=OPS)

    assert response.status_code == 422
    assert response.json()["detail"].startswith(detail)


def test_the_eleventh_run_is_429_with_retry_after(settings):
    client = make_client(settings, make_ranker(settings))
    for step in range(10):
        body = square(102.0 + step * 0.01, 0.5, 0.05)
        assert client.post("/api/areas/rank", json=body, headers=OPS).status_code == 200

    response = client.post(
        "/api/areas/rank", json=square(102.3, 0.5, 0.05), headers=OPS
    )

    assert response.status_code == 429
    assert int(response.headers["Retry-After"]) > 0


def test_an_earth_engine_failure_is_502(settings):
    ranker = make_ranker(settings, FakeAreaSource(error=AreaSourceError("boom")))
    client = make_client(settings, ranker)

    response = client.post("/api/areas/rank", json=RIAU_SQUARE, headers=OPS)

    assert response.status_code == 502
    assert response.json()["detail"] == "area_source_failed"


def test_a_limit_store_failure_is_503(settings):
    from adapters.area_limit_store import AreaLimitUnavailable

    class Broken:
        def update(self, uid, apply):
            raise AreaLimitUnavailable("down")

    client = make_client(settings, make_ranker(settings, limits=Broken()))

    response = client.post("/api/areas/rank", json=RIAU_SQUARE, headers=OPS)

    assert response.status_code == 503
    assert response.json()["detail"] == "area_limit_unavailable"
