from datetime import UTC, datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from casework.evidence_intake import (
    PublishFailed,
    TaskClosed,
    UnknownTask,
    UnknownUpload,
    UploadMissing,
    UploadTooLarge,
)
from config import JudgeMode
from contracts import Inbox, UploadTicket
from domain.evidence import UnsupportedMedia
from routes import volunteer
from tests.fakes import FakeVerifier, make_evidence, make_message, make_task

TOKENS = {
    "v1": {"uid": "v1", "role": "volunteer"},
    "judge-anon": {"uid": "J"},
}
TICKET = UploadTicket(
    evidence_id="e1",
    upload_url="https://storage.googleapis.com/put",
    headers={"Content-Type": "image/jpeg", "x-goog-content-length-range": "0,26214400"},
)
UPLOAD_BODY = {
    "task_id": "t1",
    "kind": "photo",
    "content_type": "image/jpeg",
    "size_bytes": 1000,
    "sample": True,
}
COMPLETE_BODY = {
    "point": {"lat": 0.5, "lon": 101.4},
    "captured_at": datetime(2026, 10, 17, 12, 0, tzinfo=UTC).isoformat(),
}


class StubIntake:
    def __init__(self, error=None):
        self.error = error
        self.calls = []

    def request_upload(self, volunteer_id, request):
        self.calls.append(("upload", volunteer_id, request))
        if self.error is not None:
            raise self.error
        return TICKET

    def complete(self, volunteer_id, evidence_id, completion):
        self.calls.append(("complete", volunteer_id, evidence_id, completion))
        if self.error is not None:
            raise self.error
        return make_evidence(id=evidence_id, uploaded_by=volunteer_id, sample=True)


class StubInbox:
    def __init__(self):
        self.read_for = []

    def read(self, volunteer_id):
        self.read_for.append(volunteer_id)
        return Inbox(
            tasks=[make_task(id="t1", assignee_id=volunteer_id)],
            messages=[make_message(id="m1", to_id=volunteer_id)],
            evidence=[make_evidence(id="e1", uploaded_by=volunteer_id)],
        )


def make_client(settings, intake=None, inbox=None, judge=False):
    app = FastAPI()
    app.state.settings = settings.model_copy(
        update={"judge_mode": JudgeMode(enabled=judge, max_resets_per_hour=20)}
    )
    app.state.verifier = FakeVerifier(TOKENS)
    app.state.evidence_intake = intake or StubIntake()
    app.state.inbox_reader = inbox or StubInbox()
    app.include_router(volunteer.router)
    return TestClient(app)


def bearer(token, **headers):
    return {"Authorization": f"Bearer {token}", **headers}


def test_the_owner_reads_their_inbox_of_tasks_messages_and_evidence(settings):
    inbox = StubInbox()

    response = make_client(settings, inbox=inbox).get(
        "/api/v/v1/inbox", headers=bearer("v1")
    )

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"tasks", "messages", "evidence"}
    assert body["tasks"][0]["id"] == "t1"
    assert body["messages"][0]["id"] == "m1"
    assert body["evidence"][0]["id"] == "e1"
    assert inbox.read_for == ["v1"]


@pytest.mark.parametrize(
    ("method", "path", "body"),
    [
        ("get", "/api/v/v2/inbox", None),
        ("post", "/api/v/v2/uploads", UPLOAD_BODY),
        ("post", "/api/v/v2/evidence/e1/complete", COMPLETE_BODY),
    ],
)
def test_another_uid_is_403_on_every_volunteer_route(settings, method, path, body):
    intake = StubIntake()
    client = make_client(settings, intake=intake)

    response = client.request(method, path, json=body, headers=bearer("v1"))

    assert response.status_code == 403
    assert intake.calls == []


def test_a_judge_volunteer_header_acts_for_any_uid(settings):
    intake = StubIntake()
    client = make_client(settings, intake=intake, judge=True)

    response = client.post(
        "/api/v/vol-ari/uploads",
        json=UPLOAD_BODY,
        headers=bearer("judge-anon", **{"X-Bara-Role": "volunteer"}),
    )

    assert response.status_code == 200
    assert intake.calls[0][1] == "vol-ari"


def test_an_upload_returns_the_ticket_with_its_signed_headers(settings):
    intake = StubIntake()

    response = make_client(settings, intake=intake).post(
        "/api/v/v1/uploads", json=UPLOAD_BODY, headers=bearer("v1")
    )

    assert response.status_code == 200
    assert response.json() == {
        "evidence_id": "e1",
        "upload_url": "https://storage.googleapis.com/put",
        "headers": {
            "Content-Type": "image/jpeg",
            "x-goog-content-length-range": "0,26214400",
        },
    }
    _, volunteer_id, request = intake.calls[0]
    assert volunteer_id == "v1"
    assert request.sample is True


def test_complete_returns_the_stored_evidence(settings):
    intake = StubIntake()

    response = make_client(settings, intake=intake).post(
        "/api/v/v1/evidence/e7/complete", json=COMPLETE_BODY, headers=bearer("v1")
    )

    assert response.status_code == 200
    assert response.json()["id"] == "e7"
    assert response.json()["sample"] is True
    _, volunteer_id, evidence_id, completion = intake.calls[0]
    assert (volunteer_id, evidence_id) == ("v1", "e7")
    assert completion.point.lat == 0.5


def test_complete_accepts_a_null_point(settings):
    response = make_client(settings).post(
        "/api/v/v1/evidence/e1/complete",
        json={**COMPLETE_BODY, "point": None},
        headers=bearer("v1"),
    )

    assert response.status_code == 200


def test_an_upload_body_with_a_bad_size_is_422(settings):
    response = make_client(settings).post(
        "/api/v/v1/uploads", json={**UPLOAD_BODY, "size_bytes": 0}, headers=bearer("v1")
    )

    assert response.status_code == 422


@pytest.mark.parametrize(
    ("error", "status", "detail"),
    [
        (UnknownTask("x"), 404, "task_not_found"),
        (TaskClosed("x"), 409, "task_closed"),
        (UploadTooLarge("x"), 413, "upload_too_large"),
        (UnsupportedMedia("x"), 422, "unsupported_media"),
    ],
)
def test_upload_errors_map_to_status_codes(settings, error, status, detail):
    response = make_client(settings, intake=StubIntake(error)).post(
        "/api/v/v1/uploads", json=UPLOAD_BODY, headers=bearer("v1")
    )

    assert response.status_code == status
    assert response.json() == {"detail": detail}


@pytest.mark.parametrize(
    ("error", "status", "detail"),
    [
        (UnknownUpload("x"), 404, "upload_not_found"),
        (UnknownTask("x"), 404, "task_not_found"),
        (TaskClosed("x"), 409, "task_closed"),
        (UploadMissing("x"), 409, "upload_missing"),
        (UploadTooLarge("x"), 413, "upload_too_large"),
        (PublishFailed("x"), 503, "publish_failed"),
    ],
)
def test_complete_errors_map_to_status_codes(settings, error, status, detail):
    response = make_client(settings, intake=StubIntake(error)).post(
        "/api/v/v1/evidence/e1/complete", json=COMPLETE_BODY, headers=bearer("v1")
    )

    assert response.status_code == status
    assert response.json() == {"detail": detail}
