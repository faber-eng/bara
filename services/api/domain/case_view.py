from contracts import (
    AgentRun,
    Case,
    CaseSummary,
    Escalation,
    Evidence,
    Message,
    PastCheck,
    Task,
    TimelineEntry,
)

LISTED_TASK_STATUSES = frozenset({"open", "overdue"})


def summarize_case(case: Case, tasks: list[Task]) -> CaseSummary:
    listed = [task for task in tasks if task.status in LISTED_TASK_STATUSES]
    if not listed:
        return CaseSummary(case=case, next_deadline_at=None, task_status=None)
    next_task = min(listed, key=lambda task: (task.deadline_at, task.id))
    return CaseSummary(
        case=case, next_deadline_at=next_task.deadline_at, task_status=next_task.status
    )


def case_entries(case: Case) -> list[TimelineEntry]:
    where = case.dam_id or case.cell_id
    entries = [
        TimelineEntry(at=case.opened_at, text=f"Case opened: {case.type} at {where}")
    ]
    if case.closed_at is not None:
        closer = case.closed_by or "unknown"
        entries.append(
            TimelineEntry(at=case.closed_at, text=f"Case closed by {closer}")
        )
    return entries


def task_entries(task: Task) -> list[TimelineEntry]:
    entries = [
        TimelineEntry(
            at=task.created_at,
            text=f"Task {task.type} given to {task.assignee_id}, due {task.deadline_at.isoformat()}",
        )
    ]
    if task.done_at is not None:
        entries.append(TimelineEntry(at=task.done_at, text=f"Task {task.type} done"))
    return entries


def evidence_entries(evidence: Evidence) -> list[TimelineEntry]:
    if evidence.captured_at is None:
        return []
    return [TimelineEntry(at=evidence.captured_at, text=describe_evidence(evidence))]


def describe_evidence(evidence: Evidence) -> str:
    if evidence.verdict is None:
        return f"Evidence {evidence.kind} received"
    return (
        f"Evidence {evidence.kind} checked: dam {evidence.verdict.dam_state}, "
        f"smoke {evidence.verdict.smoke}"
    )


def run_entry(run: AgentRun) -> TimelineEntry:
    if run.final_json is None:
        return TimelineEntry(
            at=run.started_at, text=f"Agent run failed ({run.trigger})"
        )
    decision = run.final_json
    return TimelineEntry(
        at=run.started_at, text=f"Agent decided {decision.decision}: {decision.reason}"
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
) -> list[TimelineEntry]:
    entries = case_entries(case)
    for task in tasks:
        entries.extend(task_entries(task))
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
