import hashlib
from types import MappingProxyType

from contracts import CaseStatus, DamState, EvidenceKind, GeoPoint, Verdict
from domain.case_machine import transition
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
    return (
        verdict.dam_state in ACTION_DAM_STATES
        or verdict.smoke in ("wisps", "plume")
        or verdict.open_flame == "yes"
        or verdict.hot_ground_signs == "clear"
    )


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


def verdict_cache_key(sha256: str, prompt_version: str) -> str:
    return hashlib.sha256(f"{sha256}:{prompt_version}".encode()).hexdigest()


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


def with_mismatch_reason(reasons: list[str]) -> list[str]:
    kept = reasons[: MAX_REASONS - 1]
    return [*kept, LOCATION_MISMATCH]


def final_verdict(read: Verdict, threshold: float, location: bool | None) -> Verdict:
    if location is False:
        return read.model_copy(
            update={"needs_human": True, "reasons": with_mismatch_reason(read.reasons)}
        )
    if needs_human(read, threshold):
        return read.model_copy(update={"needs_human": True})
    return read
