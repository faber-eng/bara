import asyncio
import logging
from dataclasses import dataclass
from typing import Protocol

from adapters.firestore_repos import (
    CaseChanged,
    CaseRepository,
    CaseworkStore,
    DamCheck,
    EvidenceRepository,
    StatusChange,
    TaskRepository,
    VerdictCache,
)
from casework.evidence_reader import PROMPT_VERSIONS
from casework.media import PreparedMedia, prepare_audio, prepare_video
from casework.photo import exif_point, prepare_photo
from contracts import (
    Case,
    CaseStatus,
    Evidence,
    EvidenceKind,
    Task,
    TaskType,
    Verdict,
    VerdictCacheEntry,
)
from domain.clock import Clock
from domain.escalation import smoke_case_for
from domain.evidence import (
    case_status_after_verdict,
    final_verdict,
    location_ok,
    location_waived,
    readable_dam_state,
    verdict_cache_key,
)
from logs import log_extra

logger = logging.getLogger(__name__)


class CheckError(Exception):
    pass


class UnknownEvidence(CheckError):
    pass


class EvidenceMissing(CheckError):
    pass


class MediaStorage(Protocol):
    def read_uri(self, uri: str) -> bytes | None: ...


class Reader(Protocol):
    async def read(self, media: PreparedMedia, task_type: TaskType) -> Verdict: ...


async def prepare_media(kind: EvidenceKind, data: bytes) -> PreparedMedia:
    if kind == "audio":
        return await prepare_audio(data)
    if kind == "video":
        return await prepare_video(data)
    return await asyncio.to_thread(prepare_photo, data)


def device_point(evidence: Evidence, data: bytes):
    if evidence.kind != "photo":
        return evidence.point
    return exif_point(data) or evidence.point


@dataclass(frozen=True)
class CheckedEvidence:
    evidence_id: str
    verdict: Verdict
    location_ok: bool | None
    stored: bool
    from_cache: bool
    awaits_agent: bool
    advisory: bool = False


@dataclass(frozen=True)
class LoadedPhoto:
    evidence: Evidence
    task: Task
    data: bytes


@dataclass(frozen=True)
class ModelVerdict:
    verdict: Verdict
    cached: bool


def case_change_for(case: Case, verdict: Verdict) -> StatusChange | None:
    next_status = case_status_after_verdict(case.status, verdict, verdict.needs_human)
    if next_status == case.status:
        return None
    return StatusChange(case.id, case.status, next_status)


def dam_check_for(case: Case, verdict: Verdict, clock: Clock) -> DamCheck | None:
    state = readable_dam_state(verdict)
    if case.dam_id is None or state is None or verdict.needs_human:
        return None
    return DamCheck(case.dam_id, state, clock.now())


class EvidenceChecker:
    def __init__(
        self,
        *,
        evidence: EvidenceRepository,
        tasks: TaskRepository,
        cases: CaseRepository,
        storage: MediaStorage,
        cache: VerdictCache,
        casework: CaseworkStore,
        reader: Reader,
        clock: Clock,
        model: str,
        human_review_confidence: float,
        location_tolerance_m: float,
    ):
        self._evidence = evidence
        self._tasks = tasks
        self._cases = cases
        self._storage = storage
        self._cache = cache
        self._casework = casework
        self._reader = reader
        self._clock = clock
        self._model = model
        self._threshold = human_review_confidence
        self._tolerance_m = location_tolerance_m

    async def check(self, task_id: str, evidence_id: str) -> CheckedEvidence:
        loaded = await asyncio.to_thread(self._load, task_id, evidence_id)
        if isinstance(loaded, CheckedEvidence):
            return loaded
        read = await self._model_verdict(loaded.evidence, loaded.data, loaded.task.type)
        return await asyncio.to_thread(self._finish, loaded, read)

    def _load(self, task_id: str, evidence_id: str) -> CheckedEvidence | LoadedPhoto:
        evidence = self._evidence_of(task_id, evidence_id)
        if evidence.verdict is not None:
            return CheckedEvidence(
                evidence.id,
                evidence.verdict,
                evidence.location_ok,
                stored=False,
                from_cache=False,
                awaits_agent=False,
            )
        task = self._task(task_id)
        return LoadedPhoto(evidence, task, self._media(evidence))

    def _finish(self, loaded: LoadedPhoto, read: ModelVerdict) -> CheckedEvidence:
        evidence, task, data = loaded.evidence, loaded.task, loaded.data
        location = location_ok(
            task.target, device_point(evidence, data), self._tolerance_m
        )
        verdict = final_verdict(
            read.verdict,
            self._threshold,
            location,
            location_waived(evidence.kind, evidence.sample),
        )
        advisory = evidence.kind == "audio"
        status = self._store(evidence, verdict, location)
        return CheckedEvidence(
            evidence.id,
            verdict,
            location,
            stored=status is not None,
            from_cache=read.cached,
            awaits_agent=not advisory and status == "reviewing",
            advisory=advisory,
        )

    def flag_unread(self, case_id: str, evidence_id: str) -> None:
        evidence = self._evidence.get(evidence_id)
        if evidence is not None and evidence.kind == "audio":
            return
        self.flag_for_person(case_id)

    def flag_for_person(self, case_id: str) -> None:
        case = self._cases.get(case_id)
        if case is None or case.status != "reviewing":
            return
        try:
            self._casework.move_case(StatusChange(case_id, "reviewing", "human_review"))
        except CaseChanged:
            return
        logger.info(
            "case sent to a person",
            extra=log_extra("case_flagged_for_person", case_id=case_id),
        )

    def _evidence_of(self, task_id: str, evidence_id: str) -> Evidence:
        evidence = self._evidence.get(evidence_id)
        if evidence is None or evidence.task_id != task_id:
            raise UnknownEvidence(f"no evidence {evidence_id!r} on task {task_id!r}")
        return evidence

    def _task(self, task_id: str) -> Task:
        task = self._tasks.get(task_id)
        if task is None:
            raise UnknownEvidence(f"the task {task_id!r} is gone")
        return task

    def _case(self, case_id: str) -> Case:
        case = self._cases.get(case_id)
        if case is None:
            raise UnknownEvidence(f"the case {case_id!r} is gone")
        return case

    def _media(self, evidence: Evidence) -> bytes:
        data = self._storage.read_uri(evidence.gcs_uri)
        if data is None:
            raise EvidenceMissing(f"no file for evidence {evidence.id!r}")
        return data

    async def _model_verdict(
        self, evidence: Evidence, data: bytes, task_type: TaskType
    ) -> ModelVerdict:
        version = PROMPT_VERSIONS[evidence.kind]
        key = verdict_cache_key(evidence.sha256, version, task_type)
        entry = await asyncio.to_thread(self._cache.get, key)
        if entry is not None:
            return ModelVerdict(entry.verdict, cached=True)
        media = await prepare_media(evidence.kind, data)
        verdict = await self._reader.read(media, task_type)
        await asyncio.to_thread(
            self._cache.put,
            VerdictCacheEntry(
                id=key,
                verdict=verdict,
                model=self._model,
                prompt_version=version,
            ),
        )
        return ModelVerdict(verdict, cached=False)

    def _store(
        self, evidence: Evidence, verdict: Verdict, location: bool | None
    ) -> CaseStatus | None:
        try:
            return self._commit(evidence, verdict, location)
        except CaseChanged:
            if self._has_verdict(evidence.id):
                return None
            return self._commit(evidence, verdict, location)

    def _commit(
        self, evidence: Evidence, verdict: Verdict, location: bool | None
    ) -> CaseStatus:
        case = self._case(evidence.case_id)
        if evidence.kind == "audio":
            return self._commit_advisory(case, evidence, verdict, location)
        change = case_change_for(case, verdict)
        self._casework.commit_verdict(
            evidence_id=evidence.id,
            verdict=verdict,
            location_ok=location,
            case_change=change,
            dam_check=dam_check_for(case, verdict, self._clock),
            smoke_case_id=smoke_case_for(case, verdict),
        )
        if change is None:
            return case.status
        return change.next

    def _commit_advisory(
        self, case: Case, evidence: Evidence, verdict: Verdict, location: bool | None
    ) -> CaseStatus:
        self._casework.commit_verdict(
            evidence_id=evidence.id,
            verdict=verdict,
            location_ok=location,
            case_change=None,
            dam_check=None,
            smoke_case_id=None,
        )
        return case.status

    def _has_verdict(self, evidence_id: str) -> bool:
        stored = self._evidence.get(evidence_id)
        return stored is not None and stored.verdict is not None
