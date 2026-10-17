import logging
from dataclasses import dataclass

from adapters.firestore_repos import ResetRepository
from domain.clock import Clock
from domain.reset_scope import ResetScope, plan_reset
from domain.scenario import Scenario

logger = logging.getLogger(__name__)

RESET_ACTOR = "reset"


@dataclass(frozen=True)
class ResetSummary:
    deleted: dict[str, int]
    seeded: dict[str, int]


def count_deleted(scope: ResetScope) -> dict[str, int]:
    return {
        "volunteers": len(scope.volunteer_ids),
        "contacts": len(scope.contact_ids),
        "dams": len(scope.dam_ids),
        "cases": len(scope.case_ids),
        "tasks": len(scope.task_ids),
        "evidence": len(scope.evidence_ids),
        "messages": len(scope.message_ids),
        "escalations": len(scope.escalation_ids),
    }


def count_seeded(scenario: Scenario) -> dict[str, int]:
    return {
        "volunteers": len(scenario.spec.volunteers),
        "contacts": len(scenario.spec.contacts),
        "dams": len(scenario.dams),
    }


class ScenarioResetter:
    def __init__(
        self, *, repository: ResetRepository, clock: Clock, scenario: Scenario
    ):
        self._repository = repository
        self._clock = clock
        self._scenario = scenario

    def plan(self) -> ResetSummary:
        scope = plan_reset(self._repository.snapshot())
        return ResetSummary(count_deleted(scope), count_seeded(self._scenario))

    def reset(self, updated_by: str = RESET_ACTOR) -> ResetSummary:
        scope = plan_reset(self._repository.snapshot())
        self._repository.delete(scope)
        self._repository.seed(self._scenario)
        self._clock.reset(RESET_ACTOR)
        summary = ResetSummary(count_deleted(scope), count_seeded(self._scenario))
        logger.info(
            "scenario reset",
            extra={
                "fields": {
                    "event": "scenario_reset",
                    "by": updated_by,
                    "deleted": summary.deleted,
                }
            },
        )
        return summary
