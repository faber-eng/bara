import asyncio
import hashlib
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest
from google.cloud import storage

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
from adapters.gemini import ModelGateway, build_vertex_clients
from adapters.storage import AdcSigningAuth, EvidenceStorage
from casework.evidence_check import EvidenceChecker
from casework.evidence_reader import EvidenceReader
from config import load_settings
from contracts import Case, ClockSettings, Dam, Evidence, Task, VerdictCacheEntry
from domain.clock import Clock
from tests.fakes import (
    InMemoryClockStore,
    InMemoryCollection,
    InMemoryTransactor,
    make_case,
    make_dam,
    make_evidence,
    make_task,
)

SAMPLE = Path(__file__).resolve().parents[3] / "data/samples/photo/broken-dam-1.jpg"
VERDICT_BUDGET_S = 10


def collection_of(model, item):
    collection = InMemoryCollection(model)
    collection.put(item.id, item)
    return collection


@pytest.mark.live
def test_the_broken_dam_sample_reads_as_broken_in_under_10_s():
    settings = load_settings()
    bucket = storage.Client(project=settings.project).bucket(settings.evidence_bucket)
    media = EvidenceStorage(bucket, AdcSigningAuth)
    data = SAMPLE.read_bytes()
    name = f"live/broken-dam-{uuid.uuid4().hex[:8]}.jpg"
    bucket.blob(name).upload_from_string(data, content_type="image/jpeg")
    evidence = collection_of(
        Evidence,
        make_evidence(
            gcs_uri=media.gcs_uri(name),
            sha256=hashlib.sha256(data).hexdigest(),
            sample=True,
        ),
    )
    cases = collection_of(Case, make_case(id="c1", status="reviewing", dam_id="d1"))
    dams = collection_of(Dam, make_dam(id="d1"))
    gateway = ModelGateway(settings.models, build_vertex_clients(settings))
    checker = EvidenceChecker(
        evidence=EvidenceRepository(evidence),
        tasks=TaskRepository(collection_of(Task, make_task(status="done"))),
        cases=CaseRepository(cases),
        storage=media,
        cache=VerdictCache(InMemoryCollection(VerdictCacheEntry)),
        casework=CaseworkStore(
            InMemoryTransactor({EVIDENCE: evidence, CASES: cases, DAMS: dams})
        ),
        reader=EvidenceReader(gateway),
        clock=Clock(
            InMemoryClockStore(ClockSettings(offset_seconds=0, updated_by="live")),
            lambda: datetime.now(UTC),
        ),
        model=settings.models.fast.model,
        human_review_confidence=settings.tasks.human_review_confidence,
        location_tolerance_m=settings.tasks.location_tolerance_m,
    )

    started = time.perf_counter()
    try:
        checked = asyncio.run(checker.check("t1", "e1"))
    finally:
        bucket.blob(name).delete()
    elapsed = time.perf_counter() - started

    assert checked.verdict.dam_state == "broken", checked.verdict
    assert checked.cached is False
    assert elapsed < VERDICT_BUDGET_S, elapsed
    assert evidence.get("e1").verdict == checked.verdict
