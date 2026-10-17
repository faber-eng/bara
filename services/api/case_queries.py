import logging
from collections import defaultdict

from adapters.firestore_repos import (
    AgentRunRepository,
    CaseRepository,
    EvidenceRepository,
    TaskRepository,
)
from adapters.store import DocumentNotFound
from contracts import Case, CaseDetail, CaseSummary, Task
from domain.case_machine import transition
from domain.case_view import build_timeline, summarize_case
from domain.clock import Clock

logger = logging.getLogger(__name__)


class UnknownCase(Exception):
    pass


class CaseQueries:
    def __init__(
        self,
        *,
        cases: CaseRepository,
        tasks: TaskRepository,
        evidence: EvidenceRepository,
        runs: AgentRunRepository,
        clock: Clock,
    ):
        self._cases = cases
        self._tasks = tasks
        self._evidence = evidence
        self._runs = runs
        self._clock = clock

    def summaries(self, region: str | None, status: str | None) -> list[CaseSummary]:
        cases = self._cases.search(region, status)
        tasks = self._tasks.for_cases([case.id for case in cases])
        by_case: dict[str, list[Task]] = defaultdict(list)
        for task in tasks:
            by_case[task.case_id].append(task)
        return [summarize_case(case, by_case[case.id]) for case in cases]

    def detail(self, case_id: str) -> CaseDetail:
        case = self._cases.get(case_id)
        if case is None:
            raise UnknownCase(case_id)
        tasks = sorted(
            self._tasks.for_cases([case_id]),
            key=lambda task: (task.created_at, task.id),
        )
        evidence = sorted(self._evidence.for_cases([case_id]), key=lambda item: item.id)
        runs = self._runs.for_case(case_id)
        return CaseDetail(
            case=case,
            tasks=tasks,
            evidence=evidence,
            agent_runs=runs,
            timeline=build_timeline(case, tasks, evidence, runs),
        )

    def close(self, case_id: str, closed_by: str) -> Case:
        case = self._cases.get(case_id)
        if case is None:
            raise UnknownCase(case_id)
        transition(case.status, "closed")
        closed_at = self._clock.now()
        try:
            self._cases.mark_closed(case_id, closed_by, closed_at)
        except DocumentNotFound as error:
            raise UnknownCase(case_id) from error
        logger.info(
            "case closed",
            extra={
                "fields": {
                    "event": "case_closed",
                    "case_id": case_id,
                    "closed_by": closed_by,
                    "from": case.status,
                }
            },
        )
        return case.model_copy(
            update={"status": "closed", "closed_by": closed_by, "closed_at": closed_at}
        )
