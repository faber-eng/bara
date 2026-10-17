from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from statistics import median
from zoneinfo import ZoneInfo

from contracts import (
    Case,
    Dam,
    DataAsOf,
    Escalation,
    Evidence,
    PublicDam,
    PublicSummary,
    RankedCell,
    RankingRun,
    RecordLine,
    Task,
)
from domain.escalation import counts_as_proof
from domain.weeks import iso_week_label

HIGH_RISK_SCORE = 80
BROKEN_STATES = frozenset({"broken", "damaged"})
ESCALATED_STATUSES = frozenset({"escalated", "monitoring"})
SECONDS_PER_DAY = 86400
WEEK_DAYS = 7

OPENED_TEXT = {
    "dam_risk": "Dam flagged at risk in {cell}.",
    "reignition": "Re-ignition risk flagged in {cell}.",
    "hotspot": "Fire hotspot reported in {cell}.",
}
TASK_TEXT = {
    "dam_check": "Dam check due {due} in {cell}.",
    "dam_repair": "Repair due {due} in {cell}.",
    "patrol_recheck": "Patrol recheck due {due} in {cell}.",
}


@dataclass(frozen=True)
class Window:
    start: datetime
    end: datetime

    def contains(self, moment: datetime | None) -> bool:
        return moment is not None and self.start <= moment < self.end


def week_window(week_start: date, zone: ZoneInfo) -> Window:
    start = datetime(week_start.year, week_start.month, week_start.day, tzinfo=zone)
    end_day = week_start + timedelta(days=WEEK_DAYS)
    end = datetime(end_day.year, end_day.month, end_day.day, tzinfo=zone)
    return Window(start.astimezone(UTC), end.astimezone(UTC))


def data_as_of(week_start: date, window: Window, run: RankingRun | None) -> DataAsOf:
    if run is None:
        return DataAsOf(s1_pass_date=week_start, ranking_run_at=window.start)
    return DataAsOf(s1_pass_date=run.s1_pass_date, ranking_run_at=run.ran_at)


def active_in(case: Case, window: Window) -> bool:
    if case.opened_at >= window.end:
        return False
    return case.closed_at is None or case.closed_at >= window.start


def is_open_bucket(case: Case) -> bool:
    return case.status != "closed" and case.status not in ESCALATED_STATUSES


def count_cases(cases: Sequence[Case], window: Window) -> tuple[int, int, int]:
    active = [case for case in cases if active_in(case, window)]
    opened = sum(1 for case in active if is_open_bucket(case))
    escalated = sum(1 for case in active if case.status in ESCALATED_STATUSES)
    closed = sum(1 for case in cases if window.contains(case.closed_at))
    return opened, escalated, closed


def judged(task: Task, now: datetime) -> bool:
    return task.status == "done" or task.deadline_at <= now


def on_time_pct(tasks: Sequence[Task], window: Window, now: datetime) -> float | None:
    due = [
        task
        for task in tasks
        if window.contains(task.deadline_at) and judged(task, now)
    ]
    if not due:
        return None
    on_time = [
        task
        for task in due
        if task.status == "done"
        and task.done_at is not None
        and task.done_at <= task.deadline_at
    ]
    return round(100 * len(on_time) / len(due), 1)


def repaired_intact(task: Task, evidence: Sequence[Evidence]) -> bool:
    if task.type != "dam_repair" or task.done_at is None:
        return False
    return any(
        item.task_id == task.id
        and item.verdict is not None
        and counts_as_proof(item)
        and item.verdict.dam_state == "intact"
        for item in evidence
    )


def repair_days(task: Task, done_at: datetime) -> float:
    return (done_at - task.created_at).total_seconds() / SECONDS_PER_DAY


def median_days_to_repair(
    cases: Sequence[Case],
    tasks: Sequence[Task],
    evidence: Sequence[Evidence],
    window: Window,
) -> float | None:
    closed_ids = {case.id for case in cases if window.contains(case.closed_at)}
    repairs = [
        task
        for task in tasks
        if task.done_at is not None
        and task.case_id in closed_ids
        and repaired_intact(task, evidence)
    ]
    if not repairs:
        return None
    return round(median(repair_days(task, task.done_at) for task in repairs), 1)


def build_summary(
    *,
    region: str,
    week_start: date,
    window: Window,
    now: datetime,
    cells: Sequence[RankedCell],
    dams: Sequence[Dam],
    cases: Sequence[Case],
    tasks: Sequence[Task],
    evidence: Sequence[Evidence],
    run: RankingRun | None = None,
) -> PublicSummary:
    opened, escalated, closed = count_cases(cases, window)
    return PublicSummary(
        region=region,
        week=iso_week_label(week_start),
        high_risk_cells=sum(1 for c in cells if c.drying_score >= HIGH_RISK_SCORE),
        dams_broken=sum(1 for dam in dams if dam.last_state in BROKEN_STATES),
        cases_open=opened,
        cases_escalated=escalated,
        cases_closed=closed,
        median_days_to_repair=median_days_to_repair(cases, tasks, evidence, window),
        tasks_on_time_pct=on_time_pct(tasks, window, now),
        data_as_of=data_as_of(week_start, window, run),
    )


def repair_due_by_dam(
    cases: Sequence[Case], tasks: Sequence[Task]
) -> dict[str, datetime]:
    dam_of_open_case = {
        case.id: case.dam_id
        for case in cases
        if case.status != "closed" and case.dam_id is not None
    }
    due: dict[str, datetime] = {}
    for task in tasks:
        dam_id = dam_of_open_case.get(task.case_id)
        if (
            dam_id is None
            or task.type != "dam_repair"
            or task.status not in ("open", "overdue")
        ):
            continue
        if dam_id not in due or task.deadline_at < due[dam_id]:
            due[dam_id] = task.deadline_at
    return due


def public_dams(
    dams: Sequence[Dam], cases: Sequence[Case], tasks: Sequence[Task]
) -> list[PublicDam]:
    due = repair_due_by_dam(cases, tasks)
    return [
        PublicDam(
            id=dam.id,
            point=dam.point,
            last_state=dam.last_state,
            last_checked_at=dam.last_checked_at,
            repair_due_at=due.get(dam.id),
        )
        for dam in sorted(dams, key=lambda dam: dam.id)
    ]


def short_date(moment: datetime, zone: ZoneInfo) -> str:
    local = moment.astimezone(zone)
    return f"{local.day} {local:%b}"


def case_lines(
    case: Case,
    tasks: Sequence[Task],
    escalations: Sequence[Escalation],
    zone: ZoneInfo,
) -> list[RecordLine]:
    cell = case.cell_id
    lines = [
        RecordLine(
            at=case.opened_at,
            cell_id=cell,
            kind="opened",
            text=OPENED_TEXT[case.type].format(cell=cell),
        )
    ]
    for task in tasks:
        if task.status in ("reassigned", "cancelled"):
            continue
        due = short_date(task.deadline_at, zone)
        lines.append(
            RecordLine(
                at=task.created_at,
                cell_id=cell,
                kind="task",
                text=TASK_TEXT[task.type].format(due=due, cell=cell),
            )
        )
        if task.status == "overdue":
            lines.append(
                RecordLine(
                    at=task.deadline_at,
                    cell_id=cell,
                    kind="overdue",
                    text=f"A task in {cell} is overdue.",
                )
            )
    for escalation in escalations:
        lines.append(
            RecordLine(
                at=escalation.created_at,
                cell_id=cell,
                kind="escalated",
                text=f"Sent to the fire brigade for {cell}.",
            )
        )
    if case.closed_at is not None:
        lines.append(
            RecordLine(
                at=case.closed_at,
                cell_id=cell,
                kind="closed",
                text=f"Case closed in {cell}.",
            )
        )
    return lines


def response_record(
    cases: Sequence[Case],
    tasks: Sequence[Task],
    escalations_by_case: dict[str, list[Escalation]],
    zone: ZoneInfo,
    limit: int,
) -> list[RecordLine]:
    tasks_by_case: dict[str, list[Task]] = {}
    for task in tasks:
        tasks_by_case.setdefault(task.case_id, []).append(task)
    lines: list[RecordLine] = []
    for case in cases:
        lines.extend(
            case_lines(
                case,
                tasks_by_case.get(case.id, []),
                escalations_by_case.get(case.id, []),
                zone,
            )
        )
    lines.sort(key=lambda line: (line.at, line.cell_id, line.text), reverse=True)
    return lines[:limit]
