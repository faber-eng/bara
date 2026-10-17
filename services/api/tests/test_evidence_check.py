import asyncio
import io
from datetime import UTC, datetime

import pytest
from PIL import Image

from adapters.firestore_repos import (
    CASES,
    DAMS,
    EVIDENCE,
    CaseRepository,
    CaseworkStore,
    EvidenceRepository,
    TaskRepository,
    VerdictCache,
)
from adapters.storage import EvidenceStorage
from casework.evidence_check import (
    EvidenceChecker,
    EvidenceMissing,
    UnknownEvidence,
    UnsupportedEvidence,
)
from casework.evidence_reader import EVIDENCE_PROMPT_VERSION
from casework.photo import PreparedPhoto
from contracts import (
    Case,
    ClockSettings,
    Dam,
    Evidence,
    GeoPoint,
    Task,
    VerdictCacheEntry,
)
from domain.clock import Clock
from domain.evidence import verdict_cache_key
from tests.fakes import (
    InMemoryClockStore,
    InMemoryCollection,
    InMemoryTransactor,
    RecordingBucket,
    fixed_signing_auth,
    make_case,
    make_dam,
    make_evidence,
    make_task,
    make_verdict,
)

NOW = datetime(2026, 10, 17, 12, 0, tzinfo=UTC)
TARGET = GeoPoint(lat=0.5, lon=101.4)
OBJECT = "evidence/c1/e1.jpg"


def jpeg() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (20, 10), "olive").save(buffer, "JPEG")
    return buffer.getvalue()


PHOTO = jpeg()


class FakeReader:
    def __init__(self, verdict=None, error=None):
        self.verdict = verdict or make_verdict(dam_state="broken")
        self.error = error
        self.calls = []

    async def read(self, photo: PreparedPhoto, task_type):
        self.calls.append((photo, task_type))
        if self.error is not None:
            raise self.error
        return self.verdict


def collection_of(model, *items):
    collection = InMemoryCollection(model)
    for item in items:
        collection.put(item.id, item)
    return collection


class World:
    def __init__(self, *, evidence=None, case=None, reader=None, stored=True):
        self.evidence = collection_of(
            Evidence,
            evidence
            or make_evidence(
                gcs_uri=f"gs://bucket-test/{OBJECT}",
                point=GeoPoint(lat=0.5005, lon=101.4),
            ),
        )
        self.tasks = collection_of(Task, make_task(target=TARGET, status="done"))
        self.cases = collection_of(
            Case, case or make_case(id="c1", status="reviewing", dam_id="d1")
        )
        self.dams = collection_of(Dam, make_dam(id="d1", last_state="unknown"))
        self.cache = InMemoryCollection(VerdictCacheEntry)
        self.bucket = RecordingBucket({OBJECT: PHOTO} if stored else {})
        self.reader = reader or FakeReader()
        clock = Clock(
            InMemoryClockStore(ClockSettings(offset_seconds=0, updated_by="t")),
            lambda: NOW,
        )
        self.checker = EvidenceChecker(
            evidence=EvidenceRepository(self.evidence),
            tasks=TaskRepository(self.tasks),
            cases=CaseRepository(self.cases),
            storage=EvidenceStorage(self.bucket, fixed_signing_auth),
            cache=VerdictCache(self.cache),
            casework=CaseworkStore(
                InMemoryTransactor(
                    {EVIDENCE: self.evidence, CASES: self.cases, DAMS: self.dams}
                )
            ),
            reader=self.reader,
            clock=clock,
            model="gemini-flash",
            human_review_confidence=0.7,
            location_tolerance_m=300,
        )

    def check(self, task_id="t1", evidence_id="e1"):
        return asyncio.run(self.checker.check(task_id, evidence_id))


def test_a_broken_dam_verdict_is_stored_and_the_case_stays_for_the_agent():
    world = World()

    checked = world.check()

    assert checked.verdict.dam_state == "broken"
    assert checked.location_ok is True
    assert checked.stored is True
    assert checked.from_cache is False
    stored = world.evidence.get("e1")
    assert stored.verdict == checked.verdict
    assert stored.location_ok is True
    assert world.cases.get("c1").status == "reviewing"


def test_the_dam_takes_the_state_read_from_the_photo():
    world = World()

    world.check()

    dam = world.dams.get("d1")
    assert dam.last_state == "broken"
    assert dam.last_checked_at == NOW


def test_the_reader_gets_the_prepared_photo_and_the_task_type():
    world = World()

    world.check()

    photo, task_type = world.reader.calls[0]
    assert photo.mime_type == "image/jpeg"
    assert task_type == "dam_check"


def test_a_fresh_verdict_goes_into_the_cache():
    world = World()

    world.check()

    entry = world.cache.get(
        verdict_cache_key("0" * 64, EVIDENCE_PROMPT_VERSION, "dam_check")
    )
    assert entry.verdict.dam_state == "broken"
    assert entry.model == "gemini-flash"
    assert entry.prompt_version == EVIDENCE_PROMPT_VERSION


def test_a_cached_verdict_skips_the_model():
    world = World()
    key = verdict_cache_key("0" * 64, EVIDENCE_PROMPT_VERSION, "dam_check")
    world.cache.put(
        key,
        VerdictCacheEntry(
            id=key,
            verdict=make_verdict(dam_state="intact"),
            model="gemini-flash",
            prompt_version=EVIDENCE_PROMPT_VERSION,
        ),
    )

    checked = world.check()

    assert world.reader.calls == []
    assert checked.verdict.dam_state == "intact"
    assert checked.from_cache is True
    assert checked.stored is True


def test_an_intact_dam_resolves_the_case_pending_a_person():
    world = World(reader=FakeReader(make_verdict(dam_state="intact")))

    world.check()

    assert world.cases.get("c1").status == "resolved_pending_human"
    assert world.dams.get("d1").last_state == "intact"


def test_a_low_confidence_verdict_sends_the_case_to_human_review():
    world = World(reader=FakeReader(make_verdict(confidence=0.4)))

    checked = world.check()

    assert checked.verdict.needs_human is True
    assert world.cases.get("c1").status == "human_review"
    assert world.dams.get("d1").last_state == "unknown"


def test_a_photo_far_from_the_task_point_is_a_location_mismatch():
    far = make_evidence(
        gcs_uri=f"gs://bucket-test/{OBJECT}", point=GeoPoint(lat=0.6, lon=101.4)
    )
    world = World(evidence=far)

    checked = world.check()

    assert checked.location_ok is False
    assert checked.verdict.needs_human is True
    assert "location mismatch" in checked.verdict.reasons
    assert world.cases.get("c1").status == "human_review"


def test_a_photo_without_any_point_is_judged_without_a_location_check():
    sample = make_evidence(
        gcs_uri=f"gs://bucket-test/{OBJECT}", point=None, sample=True
    )
    world = World(evidence=sample)

    checked = world.check()

    assert checked.location_ok is None
    assert checked.verdict.needs_human is False


def test_a_stored_verdict_is_returned_without_a_model_call():
    done = make_evidence(
        gcs_uri=f"gs://bucket-test/{OBJECT}", verdict=make_verdict(), location_ok=True
    )
    world = World(evidence=done)

    checked = world.check()

    assert checked.verdict == make_verdict()
    assert checked.stored is False
    assert world.reader.calls == []


def test_evidence_of_another_task_is_unknown():
    world = World()

    with pytest.raises(UnknownEvidence):
        world.check(task_id="t2")


def test_a_voice_note_is_not_checked_yet():
    voice = make_evidence(kind="audio", gcs_uri="gs://bucket-test/evidence/c1/e1.webm")
    world = World(evidence=voice)

    with pytest.raises(UnsupportedEvidence):
        world.check()


def test_a_missing_file_is_reported():
    world = World(stored=False)

    with pytest.raises(EvidenceMissing):
        world.check()


def test_a_case_no_longer_reviewing_keeps_its_status():
    world = World(case=make_case(id="c1", status="closed", dam_id="d1"))

    world.check()

    assert world.cases.get("c1").status == "closed"
    assert world.evidence.get("e1").verdict is not None


def test_a_real_photo_without_any_point_needs_a_person():
    blind = make_evidence(gcs_uri=f"gs://bucket-test/{OBJECT}", point=None)
    world = World(evidence=blind)

    checked = world.check()

    assert checked.verdict.needs_human is True
    assert "no location" in checked.verdict.reasons
    assert world.cases.get("c1").status == "human_review"


def test_a_cached_verdict_of_another_task_type_is_not_used():
    world = World()
    key = verdict_cache_key("0" * 64, EVIDENCE_PROMPT_VERSION, "patrol_recheck")
    world.cache.put(
        key,
        VerdictCacheEntry(
            id=key,
            verdict=make_verdict(dam_state="intact"),
            model="gemini-flash",
            prompt_version=EVIDENCE_PROMPT_VERSION,
        ),
    )

    checked = world.check()

    assert len(world.reader.calls) == 1
    assert checked.verdict.dam_state == "broken"


def test_an_unresolved_reviewing_case_goes_to_a_person():
    world = World()

    world.checker.flag_for_person("c1")

    assert world.cases.get("c1").status == "human_review"


def test_a_case_that_moved_on_is_not_flagged():
    world = World(case=make_case(id="c1", status="assigned", dam_id="d1"))

    world.checker.flag_for_person("c1")

    assert world.cases.get("c1").status == "assigned"


def test_a_broken_dam_on_a_reviewing_case_awaits_the_agent():
    assert World().check().awaits_agent is True


def test_a_resolved_verdict_does_not_await_the_agent():
    world = World(reader=FakeReader(make_verdict(dam_state="intact")))

    assert world.check().awaits_agent is False


def test_a_broken_dam_on_a_case_already_assigned_does_not_await_the_agent():
    world = World(case=make_case(id="c1", status="assigned", dam_id="d1"))

    checked = world.check()

    assert checked.stored is True
    assert checked.awaits_agent is False


def test_a_stored_verdict_does_not_await_the_agent():
    done = make_evidence(gcs_uri=f"gs://bucket-test/{OBJECT}", verdict=make_verdict())

    assert World(evidence=done).check().awaits_agent is False


def test_a_smoke_verdict_marks_the_case_smoke_seen():
    world = World(reader=FakeReader(make_verdict(smoke="wisps")))

    world.check()

    assert world.cases.get("c1").history_flags.smoke_seen is True


def test_a_verdict_without_smoke_leaves_the_flag_off():
    world = World(reader=FakeReader(make_verdict(smoke="none")))

    world.check()

    assert world.cases.get("c1").history_flags.smoke_seen is False
