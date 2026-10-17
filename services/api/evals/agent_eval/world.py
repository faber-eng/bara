from collections.abc import Mapping, Sequence
from datetime import timedelta

from adapters.cells import CENTROID_SQL, CellRepository
from adapters.firestore_repos import (
    DamRepository,
    RankingRepository,
    VolunteerRepository,
)
from bara_agent.agent import AgentTool, build_tools
from casework.assignment import Assignment, AssignmentRequest
from casework.evidence_check import CheckedEvidence, UnknownEvidence
from contracts import Dam, Escalation, GeoPoint, RankedCell, Volunteer
from evals.agent_eval.scenarios import NOW, Scenario
from tests.fakes import InMemoryCollection, make_escalation, make_message, make_task

DEFAULT_DEADLINE_HOURS = 48


class CentroidWarehouse:
    def __init__(self, centroids: Mapping[str, GeoPoint]):
        self._centroids = dict(centroids)

    def query(self, sql: str, params: Mapping[str, object]) -> list[dict]:
        if sql != CENTROID_SQL:
            return []
        point = self._centroids.get(str(params["cell_id"]))
        if point is None:
            return []
        return [{"lat": point.lat, "lon": point.lon}]


class FixedChecker:
    def __init__(self, checked: Mapping[tuple[str, str], CheckedEvidence]):
        self._checked = dict(checked)

    async def check(self, task_id: str, evidence_id: str) -> CheckedEvidence:
        found = self._checked.get((task_id, evidence_id))
        if found is None:
            raise UnknownEvidence(f"no evidence {evidence_id!r} on task {task_id!r}")
        return found


class AcceptingAssigner:
    async def assign(self, request: AssignmentRequest) -> Assignment:
        hours = request.deadline_hours or DEFAULT_DEADLINE_HOURS
        task = make_task(
            id=f"task-new-{request.case_id}",
            case_id=request.case_id,
            type=request.task_type,
            assignee_id=request.assignee_id,
            deadline_at=NOW + timedelta(hours=hours),
            created_at=NOW,
        )
        message = make_message(
            id=f"msg-{task.id}",
            to_id=request.assignee_id,
            case_id=request.case_id,
            text=request.instructions_hint,
            text_en=request.instructions_hint,
            created_at=NOW,
        )
        return Assignment(task=task, message=message)


class AcceptingEscalator:
    async def escalate(self, case_id: str, reason: str) -> Escalation:
        return make_escalation(
            id=f"esc-{case_id}", case_id=case_id, brief_en=reason, created_at=NOW
        )


class AcceptingReviewer:
    def request(self, case_id: str, reason: str) -> None:
        return None


def collection_of[T: (Dam, Volunteer)](
    model: type[T], items: Sequence[T]
) -> InMemoryCollection[T]:
    collection = InMemoryCollection(model)
    for item in items:
        collection.put(item.id, item)
    return collection


def checked_evidence(scenario: Scenario) -> dict[tuple[str, str], CheckedEvidence]:
    if scenario.verdict is None:
        return {}
    task_id = str(scenario.event["task_id"])
    evidence_id = str(scenario.event["evidence_id"])
    checked = CheckedEvidence(
        evidence_id=evidence_id,
        verdict=scenario.verdict,
        location_ok=scenario.location_ok,
        stored=True,
        from_cache=False,
        awaits_agent=True,
    )
    return {(task_id, evidence_id): checked}


def build_world_tools(
    scenarios: Sequence[Scenario], radius_m: float
) -> list[AgentTool]:
    cells = CellRepository(
        CentroidWarehouse({item.case.cell_id: item.centroid for item in scenarios})
    )
    dams = [item.dam for item in scenarios if item.dam is not None]
    people = [member for item in scenarios for member in item.people]
    checked = {
        key: value
        for item in scenarios
        for key, value in checked_evidence(item).items()
    }
    rankings = InMemoryCollection(RankedCell)
    return build_tools(
        rankings=RankingRepository(lambda region: rankings),
        cells=cells,
        dams=DamRepository(collection_of(Dam, dams)),
        volunteers=VolunteerRepository(collection_of(Volunteer, people)),
        assigner=AcceptingAssigner(),
        checker=FixedChecker(checked),
        escalator=AcceptingEscalator(),
        reviewer=AcceptingReviewer(),
        radius_m=radius_m,
    )
