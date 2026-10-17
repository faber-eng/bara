import csv
import io

import pytest

from contracts import (
    Bulletin,
    PublicBulletin,
    PublicCells,
    PublicDam,
    PublicSummary,
    RecordLine,
)
from tests.fakes import InMemoryCollection
from tests.public_world import PublicWorld

CACHE = "public, max-age=300"


@pytest.fixture
def client(settings):
    return PublicWorld().client(settings)


def test_the_six_routes_answer_without_a_token(client):
    for route in ["summary", "cells", "dams", "record", "bulletin", "export.csv"]:
        response = client.get(f"/api/public/riau/{route}")
        assert response.status_code == 200, route
        assert response.headers["cache-control"] == CACHE, route
    assert client.get("/api/public/riau/export.geojson").status_code == 200


def test_the_bodies_match_the_contracts(client):
    PublicSummary.model_validate(client.get("/api/public/riau/summary").json())
    PublicCells.model_validate(client.get("/api/public/riau/cells").json())
    for item in client.get("/api/public/riau/dams").json():
        PublicDam.model_validate(item)
    for item in client.get("/api/public/riau/record").json():
        RecordLine.model_validate(item)
    PublicBulletin.model_validate(client.get("/api/public/riau/bulletin").json())


def test_the_bulletin_is_empty_when_none_is_stored(settings):
    world = PublicWorld()
    world.bulletins = InMemoryCollection(Bulletin)
    body = world.client(settings).get("/api/public/riau/bulletin").json()

    assert body["text_id"] is None
    assert body["cited"] == []


def test_an_unknown_region_is_404_on_every_route(client):
    for route in ["summary", "cells", "dams", "record", "bulletin", "export.csv"]:
        assert client.get(f"/api/public/nowhere/{route}").status_code == 404, route


def test_a_bad_or_future_week_is_422(client):
    assert client.get("/api/public/riau/summary?week=nope").status_code == 422
    assert client.get("/api/public/riau/summary?week=2027-W01").status_code == 422


def test_a_week_with_no_rankings_is_404_and_uncached(client):
    response = client.get("/api/public/riau/summary?week=2026-W20")

    assert response.status_code == 404
    assert "cache-control" not in response.headers


def test_the_cells_limit_is_bounded(client):
    assert client.get("/api/public/riau/cells?limit=0").status_code == 422
    assert client.get("/api/public/riau/cells?limit=201").status_code == 422
    assert len(client.get("/api/public/riau/cells?limit=2").json()["cells"]) == 2


def test_the_csv_export_names_the_license_and_the_credits(client):
    response = client.get("/api/public/riau/export.csv")

    assert response.headers["x-license"] == "CC BY-NC-SA 4.0"
    assert response.headers["content-type"].startswith("text/csv")
    assert "attachment" in response.headers["content-disposition"]
    assert response.text.startswith("# region: riau week: 2026-W42\n")
    assert "# license: CC BY-NC-SA 4.0" in response.text
    assert "Greifswald Mire Centre" in response.text
    body = [line for line in response.text.splitlines() if not line.startswith("#")]
    rows = list(csv.DictReader(io.StringIO("\n".join(body))))
    assert len(rows) == 5
    assert rows[0]["cell_id"] == "riau-1-1"


def test_the_geojson_export_carries_the_license_and_the_cells(client):
    response = client.get("/api/public/riau/export.geojson")
    body = response.json()

    assert response.headers["x-license"] == "CC BY-NC-SA 4.0"
    assert response.headers["content-type"].startswith("application/geo+json")
    assert body["type"] == "FeatureCollection"
    assert body["license"] == "CC BY-NC-SA 4.0"
    assert any("Greifswald" in credit for credit in body["credits"])
    assert len(body["features"]) == 5
    assert body["features"][0]["properties"]["license"] == "CC BY-NC-SA 4.0"
    assert body["features"][0]["geometry"]["type"] == "Point"


def test_the_sixty_first_request_in_a_minute_is_429(client):
    for _ in range(60):
        assert client.get("/api/public/riau/dams").status_code == 200

    blocked = client.get("/api/public/riau/dams")

    assert blocked.status_code == 429
    assert int(blocked.headers["retry-after"]) >= 1
    assert "cache-control" not in blocked.headers


def test_the_limit_is_per_ip(client):
    for _ in range(60):
        client.get("/api/public/riau/dams", headers={"x-forwarded-for": "1.1.1.1"})

    other = client.get("/api/public/riau/dams", headers={"x-forwarded-for": "2.2.2.2"})

    assert other.status_code == 200


def test_a_spoofed_first_forwarded_entry_does_not_dodge_the_limit(client):
    for index in range(60):
        client.get(
            "/api/public/riau/dams",
            headers={"x-forwarded-for": f"9.9.9.{index}, 5.5.5.5, 10.0.0.1"},
        )

    blocked = client.get(
        "/api/public/riau/dams",
        headers={"x-forwarded-for": "9.9.9.200, 5.5.5.5, 10.0.0.1"},
    )

    assert blocked.status_code == 429


def test_errors_carry_no_public_cache_header(client):
    for path in [
        "/api/public/nowhere/dams",
        "/api/public/riau/summary?week=nope",
        "/api/public/riau/cells?limit=0",
    ]:
        assert "cache-control" not in client.get(path).headers, path
