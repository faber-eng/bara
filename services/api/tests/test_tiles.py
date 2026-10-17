import logging
from datetime import UTC, date, datetime

import pytest
from fastapi.testclient import TestClient

import main
from adapters.earthengine import EarthEngineTiles, TileSourceError
from adapters.gemini import ModelGateway
from contracts import TileLayer
from tests.fakes import FakeModels, FakeVerifier

URL = "https://earthengine.googleapis.com/v1/projects/p/maps/abc/tiles/{z}/{x}/{y}"
SATURDAY_JAKARTA = datetime(2026, 10, 17, 4, 0, tzinfo=UTC)


class FakeTiles:
    def __init__(self, error: Exception | None = None):
        self.error = error
        self.calls: list[tuple[str, date, date]] = []

    def drying_url_template(self, region, week_start, today):
        self.calls.append((region.id, week_start, today))
        if self.error is not None:
            raise self.error
        return URL


def make_client(settings, tiles, now=SATURDAY_JAKARTA):
    gateway = ModelGateway(
        settings.models, {"reasoning": FakeModels([]), "fast": FakeModels([])}
    )
    app = main.build_app(settings, gateway, FakeVerifier({}))
    app.state.tiles = tiles
    app.state.utcnow = lambda: now
    return TestClient(app)


def test_returns_the_tile_layer_for_a_week_without_auth(settings):
    tiles = FakeTiles()
    client = make_client(settings, tiles)

    response = client.get(
        "/api/tiles/drying", params={"region": "riau", "week": "2026-W41"}
    )

    assert response.status_code == 200
    body = TileLayer.model_validate(response.json())
    assert body.layer == "drying"
    assert body.region == "riau"
    assert body.week == "2026-W41"
    assert all(part in body.url_template for part in ("{x}", "{y}", "{z}"))
    assert tiles.calls == [("riau", date(2026, 10, 5), date(2026, 10, 17))]


def test_no_week_means_the_current_week_in_the_region_timezone(settings):
    tiles = FakeTiles()
    client = make_client(
        settings, tiles, now=datetime(2026, 10, 18, 17, 30, tzinfo=UTC)
    )

    response = client.get("/api/tiles/drying", params={"region": "riau"})

    assert response.status_code == 200
    assert response.json()["week"] == "2026-W43"
    assert tiles.calls == [("riau", date(2026, 10, 19), date(2026, 10, 19))]


@pytest.mark.parametrize("region", ["atlantis", "congo_cuvette"])
def test_a_region_without_a_drying_layer_is_404(settings, region):
    tiles = FakeTiles()
    client = make_client(settings, tiles)

    response = client.get("/api/tiles/drying", params={"region": region})

    assert response.status_code == 404
    assert response.json() == {"detail": f"region {region!r} has no drying layer"}
    assert tiles.calls == []


@pytest.mark.parametrize("week", ["2026-42", "W42", "2027-W53", "next"])
def test_a_bad_week_is_422(settings, week):
    tiles = FakeTiles()
    client = make_client(settings, tiles)

    response = client.get("/api/tiles/drying", params={"region": "riau", "week": week})

    assert response.status_code == 422
    assert tiles.calls == []


def test_a_future_week_is_422(settings):
    tiles = FakeTiles()
    client = make_client(settings, tiles)

    response = client.get(
        "/api/tiles/drying", params={"region": "riau", "week": "2026-W43"}
    )

    assert response.status_code == 422
    assert "2026-W43" in response.json()["detail"]
    assert tiles.calls == []


def test_an_earth_engine_error_is_502_and_logged(settings, caplog):
    client = make_client(settings, FakeTiles(TileSourceError("quota exceeded")))

    with caplog.at_level(logging.ERROR):
        response = client.get("/api/tiles/drying", params={"region": "riau"})

    assert response.status_code == 502
    assert "quota exceeded" not in response.text
    record = next(r for r in caplog.records if r.message == "drying tiles failed")
    assert record.fields == {
        "region": "riau",
        "week": "2026-W42",
        "error": "quota exceeded",
    }


def test_create_app_wires_earth_engine_tiles_without_a_network_call(monkeypatch):
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "example-project")
    monkeypatch.delenv("BARA_CONFIG_DIR", raising=False)
    monkeypatch.setattr(main, "configure_logging", lambda: None)
    monkeypatch.setattr(main, "build_token_verifier", lambda settings: FakeVerifier({}))
    monkeypatch.setattr(main, "build_adapters", lambda settings: "adapters")
    monkeypatch.setattr(main, "build_agent_service", lambda settings, adapters: "agent")
    monkeypatch.setattr(main, "build_dispatcher", lambda *args: "dispatcher")
    monkeypatch.setattr(main, "build_trigger", lambda *args: "trigger")
    monkeypatch.setattr(
        main,
        "build_vertex_clients",
        lambda settings: {"reasoning": FakeModels([]), "fast": FakeModels([])},
    )

    app = main.create_app()

    assert isinstance(app.state.tiles, EarthEngineTiles)
    assert app.state.utcnow().tzinfo is not None
