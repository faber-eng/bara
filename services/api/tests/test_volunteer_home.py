from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from adapters.firestore_repos import VolunteerRepository
from config import JudgeMode
from contracts import GeoPoint, Volunteer
from routes import volunteer
from tests.fakes import FakeVerifier, InMemoryCollection, make_volunteer

TOKENS = {
    "v1": {"uid": "v1", "role": "volunteer"},
    "ex1": {"uid": "ex1", "role": "volunteer"},
}
NEW_HOME = {"lat": 0.7999, "lon": 102.47081}


def make_client(settings):
    collection = InMemoryCollection(Volunteer)
    collection.put("v1", make_volunteer(id="v1", name="Budi"))
    collection.put("ex1", make_volunteer(id="ex1", example=True))
    app = FastAPI()
    app.state.settings = settings.model_copy(
        update={"judge_mode": JudgeMode(enabled=False, max_resets_per_hour=20)}
    )
    app.state.verifier = FakeVerifier(TOKENS)
    app.state.adapters = SimpleNamespace(volunteers=VolunteerRepository(collection))
    app.include_router(volunteer.router)
    return TestClient(app), collection


def bearer(token):
    return {"Authorization": f"Bearer {token}"}


def test_set_home_changes_only_the_home():
    collection = InMemoryCollection(Volunteer)
    collection.put("v1", make_volunteer(id="v1", name="Budi"))

    VolunteerRepository(collection).set_home("v1", GeoPoint(lat=1.5, lon=100.5))

    stored = collection.get("v1")
    assert stored.home == GeoPoint(lat=1.5, lon=100.5)
    assert stored.name == "Budi"


def test_the_owner_changes_their_home_and_gets_it_back(settings):
    client, collection = make_client(settings)

    response = client.put("/api/v/v1/home", json=NEW_HOME, headers=bearer("v1"))

    assert response.status_code == 200
    assert response.json() == NEW_HOME
    assert collection.get("v1").home == GeoPoint(**NEW_HOME)
    assert collection.get("v1").name == "Budi"


def test_another_uid_cannot_change_the_home(settings):
    client, collection = make_client(settings)

    response = client.put("/api/v/ex1/home", json=NEW_HOME, headers=bearer("v1"))

    assert response.status_code == 403
    assert collection.get("ex1").home == GeoPoint(lat=0.5, lon=101.4)


def test_an_example_volunteer_is_protected(settings):
    client, collection = make_client(settings)

    response = client.put("/api/v/ex1/home", json=NEW_HOME, headers=bearer("ex1"))

    assert response.status_code == 403
    assert response.json() == {"detail": "example_volunteer"}
    assert collection.get("ex1").home == GeoPoint(lat=0.5, lon=101.4)


@pytest.mark.parametrize(
    "body",
    [
        {"lat": 91, "lon": 100},
        {"lat": -91, "lon": 100},
        {"lat": 0, "lon": 181},
        {"lat": 0, "lon": -181},
        {"lat": 0},
    ],
)
def test_a_bad_point_is_422_and_changes_nothing(settings, body):
    client, collection = make_client(settings)

    response = client.put("/api/v/v1/home", json=body, headers=bearer("v1"))

    assert response.status_code == 422
    assert collection.get("v1").home == GeoPoint(lat=0.5, lon=101.4)


def test_an_unknown_volunteer_is_404(settings):
    client, collection = make_client(settings)
    collection.delete_many(["v1"])

    response = client.put("/api/v/v1/home", json=NEW_HOME, headers=bearer("v1"))

    assert response.status_code == 404
    assert response.json() == {"detail": "volunteer_not_found"}
