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
from casework.evidence_reader import EVIDENCE_PROMPT_VERSION
from casework.photo import PreparedPhoto, exif_point, prepare_photo
from contracts import (
    Case,
    CaseStatus,
    Evidence,
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
    readable_dam_state,
    verdict_cache_key,
)
from logs import log_extra

logger = logging.getLogger(__name__)


class CheckError(Exception):
    pass


class UnknownEvidence(CheckError):
    pass


class UnsupportedEvidence(CheckError):
    pass


class EvidenceMissing(CheckError):
    pass


class MediaStorage(Protocol):
    def read_uri(self, uri: str) -> bytes | None: ...


class Reader(Protocol):
    async def read(self, photo: PreparedPhoto, task_type: TaskType) -> Verdict: ...


@dataclass(frozen=True)
class CheckedEvidence:
    evidence_id: str
    verdict: Verdict
    location_ok: bool | None
    stored: bool
    from_cache: bool
    awaits_agent: bool


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
        if evidence.kind != "photo":
            raise UnsupportedEvidence(f"{evidence.kind} evidence is not checked yet")
        task = self._task(task_id)
        data = self._media(evidence)
        read = await self._model_verdict(evidence, data, task.type)
        location = location_ok(
            task.target, exif_point(data) or evidence.point, self._tolerance_m
        )
        verdict = final_verdict(
            read.verdict, self._threshold, location, evidence.sample
        )
        status = self._store(evidence, verdict, location)
        return CheckedEvidence(
            evidence.id,
            verdict,
            location,
            stored=status is not None,
            from_cache=read.cached,
            awaits_agent=status == "reviewing",
        )

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
        key = verdict_cache_key(evidence.sha256, EVIDENCE_PROMPT_VERSION, task_type)
        entry = self._cache.get(key)
        if entry is not None:
            return ModelVerdict(entry.verdict, cached=True)
        verdict = await self._reader.read(prepare_photo(data), task_type)
        self._cache.put(
            VerdictCacheEntry(
                id=key,
                verdict=verdict,
                model=self._model,
                prompt_version=EVIDENCE_PROMPT_VERSION,
            )
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

    def _has_verdict(self, evidence_id: str) -> bool:
        stored = self._evidence.get(evidence_id)
        return stored is not None and stored.verdict is not None
