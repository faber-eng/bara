import re
from collections.abc import Mapping
from datetime import datetime, timedelta, timezone
from typing import NamedTuple
from zoneinfo import ZoneInfo

from contracts import (
    AgentRun,
    Case,
    CaseSummary,
    CaseType,
    Escalation,
    Evidence,
    EvidenceKind,
    Language,
    Message,
    PastCheck,
    Task,
    TimelineEntry,
)
from domain.chat_wording import TASK_PHRASES

LISTED_TASK_STATUSES = frozenset({"open", "overdue"})
WIB = timezone(timedelta(hours=7))
VOLUNTEER_PREFIX = "vol-"
DAM_ID = re.compile(r"^dam-[a-z]+-(\d+)$")
TOKEN_JOINERS = re.compile(r"[_.]")
CASE_WORDS: dict[CaseType, str] = {
    "dam_risk": "dam at risk",
    "reignition": "fire may restart",
    "hotspot": "hotspot",
}
EVIDENCE_WORDS: dict[EvidenceKind, str] = {
    "photo": "Photo",
    "video": "Video",
    "audio": "Voice note",
}


class StampLocale(NamedTuple):
    weekdays: tuple[str, ...]
    months: tuple[str, ...]
    clock: str


STAMP_LOCALES: dict[Language, StampLocale] = {
    "en": StampLocale(
        ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"),
        ("Jan", "Feb", "Mar", "Apr", "May", "Jun")
        + ("Jul", "Aug", "Sep", "Oct", "Nov", "Dec"),
        "{hour:02d}:{minute:02d}",
    ),
    "id": StampLocale(
        ("Sen", "Sel", "Rab", "Kam", "Jum", "Sab", "Min"),
        ("Jan", "Feb", "Mar", "Apr", "Mei", "Jun")
        + ("Jul", "Agu", "Sep", "Okt", "Nov", "Des"),
        "{hour:02d}.{minute:02d}",
    ),
    "ms": StampLocale(
        ("Isn", "Sel", "Rab", "Kha", "Jum", "Sab", "Ahd"),
        ("Jan", "Feb", "Mac", "Apr", "Mei", "Jun")
        + ("Jul", "Ogo", "Sep", "Okt", "Nov", "Dis"),
        "{hour:02d}:{minute:02d}",
    ),
    "fr": StampLocale(
        ("lun.", "mar.", "mer.", "jeu.", "ven.", "sam.", "dim."),
        ("janv.", "févr.", "mars", "avr.", "mai", "juin")
        + ("juil.", "août", "sept.", "oct.", "nov.", "déc."),
        "{hour} h {minute:02d}",
    ),
}


def format_stamp(local: datetime, zone_label: str, language: Language = "en") -> str:
    locale = STAMP_LOCALES[language]
    weekday = locale.weekdays[local.weekday()]
    month = locale.months[local.month - 1]
    clock = locale.clock.format(hour=local.hour, minute=local.minute)
    return f"{weekday} {local.day} {month}, {clock} {zone_label}"


def format_wib(moment: datetime) -> str:
    return format_stamp(moment.astimezone(WIB), "WIB")


def format_local(
    moment: datetime, timezone_name: str, language: Language = "en"
) -> str:
    local = moment.astimezone(ZoneInfo(timezone_name))
    return format_stamp(local, local.tzname() or timezone_name, language)


def summarize_case(case: Case, tasks: list[Task]) -> CaseSummary:
    listed = [task for task in tasks if task.status in LISTED_TASK_STATUSES]
    if not listed:
        return CaseSummary(case=case, next_deadline_at=None, task_status=None)
    next_task = min(listed, key=lambda task: (task.deadline_at, task.id))
    return CaseSummary(
        case=case, next_deadline_at=next_task.deadline_at, task_status=next_task.status
    )


def plain_token(token: str) -> str:
    return TOKEN_JOINERS.sub(" ", token)


def without_underscores(text: str) -> str:
    return text.replace("_", " ")


def dam_label(dam_id: str) -> str:
    match = DAM_ID.match(dam_id)
    if match is None:
        return f"canal dam {dam_id}"
    return f"canal dam {match.group(1)}"


def case_place(case: Case) -> str:
    if case.dam_id is not None:
        return dam_label(case.dam_id)
    return f"cell {case.cell_id}"


def assignee_ids(tasks: list[Task]) -> list[str]:
    return sorted({task.assignee_id for task in tasks})


def person_name(person_id: str, names: Mapping[str, str]) -> str:
    if person_id in names:
        return names[person_id]
    bare = person_id.removeprefix(VOLUNTEER_PREFIX)
    return bare.replace("-", " ").replace("_", " ").title()


def case_entries(case: Case) -> list[TimelineEntry]:
    opened = f"Case opened: {CASE_WORDS[case.type]}, {case_place(case)}"
    entries = [TimelineEntry(at=case.opened_at, text=opened)]
    if case.closed_at is not None:
        closer = case.closed_by or "unknown"
        entries.append(
            TimelineEntry(at=case.closed_at, text=f"Case closed by {closer}")
        )
    return entries


def task_entries(task: Task, names: Mapping[str, str]) -> list[TimelineEntry]:
    phrase = TASK_PHRASES["en"][task.type]
    person = person_name(task.assignee_id, names)
    entries = [
        TimelineEntry(
            at=task.created_at,
            text=(
                f"Task given to {person}: {phrase}, due {format_wib(task.deadline_at)}"
            ),
        )
    ]
    if task.done_at is not None:
        entries.append(TimelineEntry(at=task.done_at, text=f"Task done: {phrase}"))
    return entries


def evidence_entries(evidence: Evidence) -> list[TimelineEntry]:
    if evidence.captured_at is None:
        return []
    return [TimelineEntry(at=evidence.captured_at, text=describe_evidence(evidence))]


def describe_evidence(evidence: Evidence) -> str:
    kind = EVIDENCE_WORDS[evidence.kind]
    if evidence.verdict is None:
        return f"{kind} received"
    return (
        f"{kind} checked: dam {plain_token(evidence.verdict.dam_state)}, "
        f"smoke {evidence.verdict.smoke}"
    )


def lower_first(text: str) -> str:
    return text[:1].lower() + text[1:]


def decision_text(decision: str, reason: str) -> str:
    action = lower_first(without_underscores(decision).strip().rstrip("."))
    return f"Agent decision: {action}. {without_underscores(reason)}"


def run_entry(run: AgentRun) -> TimelineEntry:
    if run.final_json is None:
        return TimelineEntry(
            at=run.started_at,
            text=f"Agent run failed ({plain_token(run.trigger)})",
        )
    decision = run.final_json
    return TimelineEntry(
        at=run.started_at, text=decision_text(decision.decision, decision.reason)
    )


def note_entry(note: Message) -> TimelineEntry:
    return TimelineEntry(at=note.created_at, text=f"Review note: {note.text}")


def escalation_entries(escalation: Escalation) -> list[TimelineEntry]:
    contact = escalation.contact_id
    entries = [
        TimelineEntry(at=escalation.created_at, text=f"Escalated to brigade {contact}")
    ]
    if escalation.acknowledged_at is not None:
        entries.append(
            TimelineEntry(
                at=escalation.acknowledged_at,
                text=f"Brigade {contact} acknowledged",
            )
        )
    return entries


def build_timeline(
    case: Case,
    tasks: list[Task],
    evidence: list[Evidence],
    runs: list[AgentRun],
    escalations: list[Escalation],
    notes: list[Message],
    names: Mapping[str, str],
) -> list[TimelineEntry]:
    entries = case_entries(case)
    for task in tasks:
        entries.extend(task_entries(task, names))
    for item in evidence:
        entries.extend(evidence_entries(item))
    entries.extend(run_entry(run) for run in runs)
    for escalation in escalations:
        entries.extend(escalation_entries(escalation))
    entries.extend(note_entry(note) for note in notes)
    return sorted(entries, key=lambda entry: entry.at)


def past_checks(evidence: list[Evidence]) -> list[PastCheck]:
    checks = [
        PastCheck(
            task_id=item.task_id,
            checked_at=item.captured_at,
            dam_state=item.verdict.dam_state,
            smoke=item.verdict.smoke,
        )
        for item in evidence
        if item.verdict is not None and item.captured_at is not None
    ]
    return sorted(checks, key=lambda check: check.checked_at)
