from collections.abc import Sequence
from dataclasses import dataclass

from contracts import (
    Case,
    Contact,
    Evidence,
    GeoPoint,
    Smoke,
    Task,
    TaskType,
    Verdict,
)

MAX_PACK_PHOTOS = 4
DRYING_LIMIT = 80
REIGNITE_LIMIT = 0.5
REPEAT_ATTEMPT = 2
SMOKE_SEEN: frozenset[Smoke] = frozenset({"wisps", "plume"})
MAPS_SEARCH = "https://www.google.com/maps/search/?api=1&query="


def map_url(point: GeoPoint) -> str:
    return f"{MAPS_SEARCH}{point.lat},{point.lon}"


def photo_order(evidence: Evidence) -> tuple[bool, str]:
    return (evidence.verdict is None, evidence.id)


def pack_photos(evidence: Sequence[Evidence]) -> list[str]:
    photos = sorted(
        (item for item in evidence if item.kind == "photo"), key=photo_order
    )
    return [item.gcs_uri for item in photos[:MAX_PACK_PHOTOS]]


def contact_order(contact: Contact) -> tuple[bool, str]:
    return (contact.example, contact.id)


def may_receive(contact: Contact, example_case: bool) -> bool:
    if example_case:
        return contact.example
    return True


def pick_contact(contacts: Sequence[Contact], example_case: bool) -> Contact | None:
    allowed = [item for item in contacts if may_receive(item, example_case)]
    if not allowed:
        return None
    return min(allowed, key=contact_order)


@dataclass(frozen=True)
class FieldSigns:
    smoke: Smoke
    open_flame: bool
    hot_ground: bool


@dataclass(frozen=True)
class OverdueTask:
    task_type: TaskType
    attempt: int


def shows_smoke(verdict: Verdict) -> bool:
    return verdict.smoke in SMOKE_SEEN


def shows_fire(verdict: Verdict) -> bool:
    return (
        shows_smoke(verdict)
        or verdict.open_flame == "yes"
        or verdict.hot_ground_signs == "clear"
    )


def strongest_smoke(verdicts: Sequence[Verdict]) -> Smoke:
    seen = {verdict.smoke for verdict in verdicts}
    if "plume" in seen:
        return "plume"
    if "wisps" in seen:
        return "wisps"
    return "none"


def smoke_in(signs: FieldSigns | None) -> bool:
    return signs is not None and signs.smoke != "none"


def field_signs(evidence: Sequence[Evidence]) -> FieldSigns | None:
    fire = [
        item.verdict
        for item in evidence
        if item.verdict is not None and shows_fire(item.verdict)
    ]
    if not fire:
        return None
    return FieldSigns(
        smoke=strongest_smoke(fire),
        open_flame=any(verdict.open_flame == "yes" for verdict in fire),
        hot_ground=any(verdict.hot_ground_signs == "clear" for verdict in fire),
    )


def overdue_task(tasks: Sequence[Task]) -> OverdueTask | None:
    overdue = [task for task in tasks if task.status == "overdue"]
    if not overdue:
        return None
    latest = max(overdue, key=lambda task: (task.created_at, task.id))
    return OverdueTask(task_type=latest.type, attempt=latest.attempt)


def photo_count(evidence: Sequence[Evidence]) -> int:
    return len([item for item in evidence if item.kind == "photo"])


def smoke_ever_seen(case: Case, evidence: Sequence[Evidence]) -> bool:
    if case.history_flags.smoke_seen:
        return True
    return any(
        item.verdict is not None and shows_smoke(item.verdict) for item in evidence
    )


def smoke_case_for(case: Case, verdict: Verdict) -> str | None:
    if case.history_flags.smoke_seen or not shows_smoke(verdict):
        return None
    return case.id


def overdue_escalation_reason(
    case: Case, attempt: int, evidence: Sequence[Evidence]
) -> str | None:
    drying = case.risk.drying_score
    if drying is not None and drying >= DRYING_LIMIT:
        return f"Overdue rule: drying_score {drying:g} is {DRYING_LIMIT} or more."
    reignite = case.risk.p_reignite
    if reignite is not None and reignite >= REIGNITE_LIMIT:
        return f"Overdue rule: p_reignite {reignite:g} is {REIGNITE_LIMIT} or more."
    if smoke_ever_seen(case, evidence):
        return "Overdue rule: smoke was seen on this case."
    if attempt >= REPEAT_ATTEMPT:
        return f"Overdue rule: attempt {attempt} is the second overdue task."
    return None
