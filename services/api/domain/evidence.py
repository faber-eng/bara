import hashlib
from types import MappingProxyType

from contracts import CaseStatus, DamState, EvidenceKind, GeoPoint, TaskType, Verdict
from domain.case_machine import transition
from domain.escalation import shows_fire
from domain.geo import haversine_m

EXTENSIONS: MappingProxyType[EvidenceKind, MappingProxyType[str, str]] = (
    MappingProxyType(
        {
            "photo": MappingProxyType({"image/jpeg": ".jpg", "image/png": ".png"}),
            "audio": MappingProxyType(
                {
                    "audio/webm": ".webm",
                    "audio/ogg": ".ogg",
                    "audio/mp4": ".m4a",
                    "audio/mpeg": ".mp3",
                }
            ),
            "video": MappingProxyType({"video/mp4": ".mp4", "video/quicktime": ".mov"}),
        }
    )
)
ACTION_DAM_STATES: frozenset[DamState] = frozenset({"damaged", "broken", "overtopped"})
UNSEEN_DAM_STATES: frozenset[DamState] = frozenset({"unknown", "not_applicable"})
LOCATION_MISMATCH = "location mismatch"
NO_LOCATION = "no location"
MAX_REASONS = 4


class UnsupportedMedia(ValueError):
    pass


def object_name(
    kind: EvidenceKind, content_type: str, case_id: str, evidence_id: str
) -> str:
    extension = EXTENSIONS[kind].get(content_type)
    if extension is None:
        allowed = ", ".join(EXTENSIONS[kind])
        raise UnsupportedMedia(f"a {kind} must be one of {allowed}, got {content_type}")
    return f"evidence/{case_id}/{evidence_id}{extension}"


def needs_human(verdict: Verdict, threshold: float) -> bool:
    return verdict.needs_human or verdict.confidence < threshold


def needs_action(verdict: Verdict) -> bool:
    return verdict.dam_state in ACTION_DAM_STATES or shows_fire(verdict)


def case_status_after_verdict(
    status: CaseStatus, verdict: Verdict, human: bool
) -> CaseStatus:
    if status != "reviewing":
        return status
    if human:
        return transition(status, "human_review")
    if needs_action(verdict):
        return status
    return transition(status, "resolved_pending_human")


def verdict_cache_key(sha256: str, prompt_version: str, task_type: TaskType) -> str:
    key = f"{sha256}:{prompt_version}:{task_type}"
    return hashlib.sha256(key.encode()).hexdigest()


def readable_dam_state(verdict: Verdict) -> DamState | None:
    if verdict.dam_state in UNSEEN_DAM_STATES:
        return None
    return verdict.dam_state


def location_ok(
    target: GeoPoint, point: GeoPoint | None, tolerance_m: float
) -> bool | None:
    if point is None:
        return None
    return haversine_m(target, point) <= tolerance_m


def with_reason(reasons: list[str], reason: str) -> list[str]:
    kept = reasons[: MAX_REASONS - 1]
    return [*kept, reason]


def location_problem(location: bool | None, sample: bool) -> str | None:
    if location is False:
        return LOCATION_MISMATCH
    if location is None and not sample:
        return NO_LOCATION
    return None


def final_verdict(
    read: Verdict, threshold: float, location: bool | None, sample: bool
) -> Verdict:
    problem = location_problem(location, sample)
    if problem is not None:
        return read.model_copy(
            update={"needs_human": True, "reasons": with_reason(read.reasons, problem)}
        )
    if needs_human(read, threshold):
        return read.model_copy(update={"needs_human": True})
    return read
