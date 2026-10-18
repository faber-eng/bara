from dataclasses import dataclass

from contracts import Case, Contact, Dam, Escalation, Evidence, Message, Task, Volunteer
from domain.channels import BARA_RECIPIENT


@dataclass(frozen=True)
class ResetSnapshot:
    volunteers: list[Volunteer]
    contacts: list[Contact]
    dams: list[Dam]
    cases: list[Case]
    tasks: list[Task]
    evidence: list[Evidence]
    messages: list[Message]
    escalations: list[Escalation]


@dataclass(frozen=True)
class ResetScope:
    volunteer_ids: frozenset[str]
    contact_ids: frozenset[str]
    dam_ids: frozenset[str]
    case_ids: frozenset[str]
    task_ids: frozenset[str]
    evidence_ids: frozenset[str]
    message_ids: frozenset[str]
    escalation_ids: frozenset[str]


def ids(items) -> frozenset[str]:
    return frozenset(item.id for item in items)


def plan_reset(snapshot: ResetSnapshot) -> ResetScope:
    volunteers = [item for item in snapshot.volunteers if item.example]
    contacts = [item for item in snapshot.contacts if item.example]
    example_people = ids(volunteers) | ids(contacts) | {BARA_RECIPIENT}
    cases = [
        case
        for case in snapshot.cases
        if case.example and not touches_real_uid(case.id, snapshot, example_people)
    ]
    case_ids = ids(cases)
    return ResetScope(
        volunteer_ids=ids(volunteers),
        contact_ids=ids(contacts),
        dam_ids=ids(item for item in snapshot.dams if item.example),
        case_ids=case_ids,
        task_ids=ids(on_cases(snapshot.tasks, case_ids)),
        evidence_ids=ids(on_cases(snapshot.evidence, case_ids)),
        message_ids=ids(on_cases(snapshot.messages, case_ids)),
        escalation_ids=ids(on_cases(snapshot.escalations, case_ids)),
    )


def on_cases(items, case_ids: frozenset[str]):
    return [item for item in items if item.case_id in case_ids]


def touches_real_uid(
    case_id: str, snapshot: ResetSnapshot, example_people: frozenset[str]
) -> bool:
    referenced = (
        [task.assignee_id for task in on_cases(snapshot.tasks, frozenset({case_id}))]
        + [
            item.uploaded_by
            for item in on_cases(snapshot.evidence, frozenset({case_id}))
        ]
        + [
            item.to_id
            for item in on_cases(snapshot.messages, frozenset({case_id}))
            if item.thread != "ops"
        ]
        + [
            item.contact_id
            for item in on_cases(snapshot.escalations, frozenset({case_id}))
        ]
    )
    return any(uid not in example_people for uid in referenced)
