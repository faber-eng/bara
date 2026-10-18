from adapters.firestore_repos import (
    CaseRepository,
    EvidenceRepository,
    MessageRepository,
    TaskRepository,
    VolunteerRepository,
)
from contracts import Inbox


class InboxReader:
    def __init__(
        self,
        *,
        cases: CaseRepository,
        tasks: TaskRepository,
        messages: MessageRepository,
        evidence: EvidenceRepository,
        volunteers: VolunteerRepository,
    ):
        self._cases = cases
        self._tasks = tasks
        self._messages = messages
        self._evidence = evidence
        self._volunteers = volunteers

    def _area_case_ids(self, tasks) -> list[str]:
        case_ids = sorted({task.case_id for task in tasks})
        found = (self._cases.get(case_id) for case_id in case_ids)
        return [case.id for case in found if case is not None and case.dam_id is None]

    def read(self, volunteer_id: str) -> Inbox:
        tasks = self._tasks.for_assignee(volunteer_id)
        messages = self._messages.to(volunteer_id)
        volunteer = self._volunteers.get(volunteer_id)
        return Inbox(
            tasks=sorted(tasks, key=lambda task: task.created_at, reverse=True),
            messages=sorted(messages, key=lambda message: message.created_at),
            evidence=self._evidence.for_uploader(volunteer_id),
            area_case_ids=self._area_case_ids(tasks),
            home=volunteer.home if volunteer else None,
            name=volunteer.name if volunteer else None,
            role=volunteer.role if volunteer else None,
        )
