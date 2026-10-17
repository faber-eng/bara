import hashlib
import logging
from datetime import UTC, datetime, timedelta

import pytest

from adapters.firestore_repos import (
    CASES,
    EVIDENCE,
    TASKS,
    CaseRepository,
    CaseworkStore,
    EvidenceRepository,
    TaskRepository,
    UploadRepository,
)
from adapters.storage import EvidenceStorage
from casework.evidence_intake import (
    EvidenceIntake,
    PublishFailed,
    TaskClosed,
    UnknownTask,
    UnknownUpload,
    UploadMissing,
    UploadTooLarge,
)
from contracts import (
    Case,
    ClockSettings,
    CompleteRequest,
    Evidence,
    GeoPoint,
    PendingUpload,
    Task,
    UploadRequest,
)
from domain.clock import Clock
from domain.evidence import UnsupportedMedia
from tests.fakes import (
    InMemoryClockStore,
    InMemoryCollection,
    InMemoryTransactor,
    RecordingBucket,
    fixed_signing_auth,
    make_case,
    make_task,
    make_verdict,
)

REAL_NOW = datetime(2026, 10, 17, 12, 0, tzinfo=UTC)
OFFSET = 3600
SIM_NOW = REAL_NOW + timedelta(seconds=OFFSET)
PHOTO = b"\xff\xd8 broken dam"


class FakeScheduler:
    def __init__(self, error=None):
        self.cancelled = []
        self.error = error

    def cancel(self, name):
        if self.error is not None:
            raise self.error
        self.cancelled.append(name)


class FakePublisher:
    def __init__(self, error=None):
        self.published = []
        self.error = error

    def publish(self, topic, event):
        if self.error is not None:
            raise self.error
        self.published.append((topic, event))
        return "msg-1"


def collection_with(model, items, key):
    collection = InMemoryCollection(model)
    for item in items:
        collection.put(getattr(item, key), item)
    return collection


class World:
    def __init__(self, *, task=None, case=None, scheduler=None, publisher=None):
        self.tasks = collection_with(
            Task,
            [
                task
                or make_task(
                    id="t1",
                    case_id="c1",
                    assignee_id="v1",
                    cloud_task_name="queues/q/tasks/t1-1",
                )
            ],
            "id",
        )
        self.cases = collection_with(
            Case, [case or make_case(id="c1", status="assigned", example=True)], "id"
        )
        self.evidence = InMemoryCollection(Evidence)
        self.uploads = InMemoryCollection(PendingUpload)
        self.bucket = RecordingBucket()
        self.scheduler = scheduler or FakeScheduler()
        self.publisher = publisher or FakePublisher()
        ids = iter(["e1", "event-1", "e2", "event-2"])
        clock = Clock(
            InMemoryClockStore(ClockSettings(offset_seconds=OFFSET, updated_by="t")),
            lambda: REAL_NOW,
        )
        self.intake = EvidenceIntake(
            tasks=TaskRepository(self.tasks),
            cases=CaseRepository(self.cases),
            uploads=UploadRepository(self.uploads),
            evidence=EvidenceRepository(self.evidence),
            casework=CaseworkStore(
                InMemoryTransactor(
                    {TASKS: self.tasks, CASES: self.cases, EVIDENCE: self.evidence}
                )
            ),
            storage=EvidenceStorage(self.bucket, fixed_signing_auth),
            scheduler=self.scheduler,
            publisher=self.publisher,
            clock=clock,
            new_id=lambda: next(ids),
        )

    def request(self, **overrides):
        fields = {
            "task_id": "t1",
            "kind": "photo",
            "content_type": "image/jpeg",
            "size_bytes": len(PHOTO),
            "sample": False,
        }
        return self.intake.request_upload(
            "v1", UploadRequest(**{**fields, **overrides})
        )

    def put(self, data=PHOTO, name="evidence/c1/e1.jpg"):
        self.bucket.objects[name] = data

    def complete(self, volunteer_id="v1", evidence_id="e1"):
        completion = CompleteRequest(
            point=GeoPoint(lat=0.5, lon=101.4), captured_at=REAL_NOW
        )
        return self.intake.complete(volunteer_id, evidence_id, completion)


def test_an_upload_request_signs_a_put_and_keeps_a_pending_upload():
    world = World()

    ticket = world.request(sample=True)

    assert ticket.evidence_id == "e1"
    assert ticket.upload_url.startswith("https://storage.test/evidence/c1/e1.jpg")
    assert ticket.headers == {
        "Content-Type": "image/jpeg",
        "x-goog-content-length-range": "0,26214400",
    }
    pending = world.uploads.get("e1")
    assert pending.task_id == "t1"
    assert pending.case_id == "c1"
    assert pending.object_name == "evidence/c1/e1.jpg"
    assert pending.sample is True
    assert pending.uploaded_by == "v1"
    assert pending.created_at == SIM_NOW
    assert world.evidence.where() == []


def test_a_task_of_another_person_is_unknown_to_them():
    world = World(task=make_task(id="t1", assignee_id="someone-else"))

    with pytest.raises(UnknownTask):
        world.request()

    assert world.uploads.where() == []


@pytest.mark.parametrize("status", ["overdue", "reassigned", "cancelled"])
def test_a_task_no_longer_open_is_refused(status):
    world = World(task=make_task(id="t1", assignee_id="v1", status=status))

    with pytest.raises(TaskClosed):
        world.request()

    assert world.uploads.where() == []


def test_an_unknown_task_is_refused():
    world = World()

    with pytest.raises(UnknownTask):
        world.request(task_id="nope")


def test_a_file_over_25_mb_is_refused():
    world = World()

    with pytest.raises(UploadTooLarge):
        world.request(size_bytes=26214401)


def test_a_content_type_outside_the_kind_is_refused():
    world = World()

    with pytest.raises(UnsupportedMedia):
        world.request(content_type="image/gif")


def test_completing_a_photo_stores_evidence_closes_the_task_and_publishes():
    world = World()
    world.request()
    world.put()

    evidence = world.complete()

    assert world.evidence.get("e1") == evidence
    assert evidence.sha256 == hashlib.sha256(PHOTO).hexdigest()
    assert evidence.gcs_uri == "gs://bucket-test/evidence/c1/e1.jpg"
    assert evidence.point == GeoPoint(lat=0.5, lon=101.4)
    assert evidence.captured_at == REAL_NOW
    assert evidence.uploaded_by == "v1"
    assert evidence.verdict is None
    task = world.tasks.get("t1")
    assert task.status == "done"
    assert task.done_at == SIM_NOW
    assert world.cases.get("c1").status == "reviewing"
    assert world.scheduler.cancelled == ["queues/q/tasks/t1-1"]
    topic, event = world.publisher.published[0]
    assert topic == "evidence.received"
    assert event.type == "evidence.received"
    assert event.id == "event-1"
    assert event.example is True
    assert event.region == "riau"
    assert event.occurred_at == SIM_NOW
    assert event.payload.evidence_id == "e1"
    assert event.payload.task_id == "t1"
    assert event.payload.case_id == "c1"


def test_a_sample_upload_is_stored_as_sample():
    world = World()
    world.request(sample=True)
    world.put()

    assert world.complete().sample is True


def test_a_repeat_complete_without_a_verdict_returns_the_evidence_and_publishes_again():
    world = World()
    world.request()
    world.put()

    first = world.complete()
    second = world.complete()

    assert second == first
    assert len(world.publisher.published) == 2
    assert world.tasks.get("t1").status == "done"


def test_a_repeat_complete_after_the_verdict_does_not_publish():
    world = World()
    world.request()
    world.put()
    first = world.complete()
    world.evidence.put("e1", first.model_copy(update={"verdict": make_verdict()}))

    world.complete()

    assert len(world.publisher.published) == 1


def test_a_repeat_complete_of_a_voice_note_does_not_publish():
    world = World()
    world.request(kind="audio", content_type="audio/webm")
    world.put(name="evidence/c1/e1.webm")
    world.complete()

    world.complete()

    assert world.publisher.published == []


def test_another_person_cannot_complete_the_upload():
    world = World()
    world.request()
    world.put()

    with pytest.raises(UnknownUpload):
        world.complete(volunteer_id="v2")

    assert world.evidence.where() == []


def test_completing_before_the_put_is_refused():
    world = World()
    world.request()

    with pytest.raises(UploadMissing):
        world.complete()

    assert world.tasks.get("t1").status == "open"


def test_a_second_photo_on_a_done_task_keeps_the_task_and_case_and_publishes():
    world = World(
        task=make_task(id="t1", assignee_id="v1", status="done"),
        case=make_case(id="c1", status="resolved_pending_human"),
    )
    world.request()
    world.put()

    world.complete()

    assert world.tasks.get("t1").status == "done"
    assert world.cases.get("c1").status == "resolved_pending_human"
    assert world.scheduler.cancelled == []
    assert len(world.publisher.published) == 1


def test_a_voice_note_is_stored_without_an_event_or_a_task_change():
    world = World()
    world.request(kind="audio", content_type="audio/webm")
    world.put(name="evidence/c1/e1.webm")

    evidence = world.complete()

    assert evidence.kind == "audio"
    assert world.tasks.get("t1").status == "open"
    assert world.cases.get("c1").status == "assigned"
    assert world.publisher.published == []


def test_a_publish_failure_keeps_the_evidence_and_asks_for_a_retry():
    publisher = FakePublisher(RuntimeError("pubsub down"))
    world = World(publisher=publisher)
    world.request()
    world.put()

    with pytest.raises(PublishFailed):
        world.complete()

    assert world.evidence.get("e1") is not None
    assert world.tasks.get("t1").status == "done"
    publisher.error = None
    world.complete()
    assert len(publisher.published) == 1


def test_a_cancel_failure_keeps_the_evidence_and_logs_a_warning(caplog):
    world = World(scheduler=FakeScheduler(RuntimeError("tasks down")))
    world.request()
    world.put()

    with caplog.at_level(logging.WARNING):
        world.complete()

    assert world.tasks.get("t1").status == "done"
    assert any(
        getattr(r, "fields", {}).get("event") == "deadline_cancel_failed"
        for r in caplog.records
    )


def test_a_photo_on_a_done_task_does_not_move_an_assigned_case():
    world = World(
        task=make_task(id="t1", assignee_id="v1", status="done"),
        case=make_case(id="c1", status="assigned"),
    )
    world.request()
    world.put()

    world.complete()

    assert world.cases.get("c1").status == "assigned"
    assert len(world.publisher.published) == 1


def test_completing_after_the_task_was_reassigned_is_refused():
    world = World()
    world.request()
    world.put()
    world.tasks.update("t1", {"status": "reassigned"})

    with pytest.raises(TaskClosed):
        world.complete()

    assert world.evidence.get("e1") is None
    assert world.cases.get("c1").status == "assigned"
