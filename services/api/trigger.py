import logging
from collections.abc import Callable

from adapters.firestore_repos import (
    CaseRepository,
    RankedDamRepository,
    RankingRepository,
)
from adapters.pubsub import EventPublisher
from contracts import RankedCell
from domain.clock import Clock
from domain.scenario import Scenario
from domain.scenario_events import (
    TOP_REFS,
    build_area_requested_event,
    build_drying_ranked_event,
    build_fire_quiet_event,
)

logger = logging.getLogger(__name__)


class JudgeTrigger:
    def __init__(
        self,
        *,
        rankings: RankingRepository,
        ranked_dams: RankedDamRepository,
        publisher: EventPublisher,
        clock: Clock,
        new_id: Callable[[], str],
        region: str,
        scenario: Scenario,
    ):
        self._scenario = scenario
        self._rankings = rankings
        self._ranked_dams = ranked_dams
        self._publisher = publisher
        self._clock = clock
        self._new_id = new_id
        self._region = region

    def drying_ranked(self) -> str:
        event = build_drying_ranked_event(
            region=self._region,
            cells=self._rankings.top(self._region, TOP_REFS),
            dams=self._ranked_dams.top(self._region, TOP_REFS),
            event_id=self._new_id(),
            occurred_at=self._clock.now(),
        )
        return self._published("drying.ranked", event)

    def fire_quiet(self) -> str:
        event = build_fire_quiet_event(
            scenario=self._scenario,
            event_id=self._new_id(),
            occurred_at=self._clock.now(),
        )
        return self._published("fire.quiet", event)

    def _published(self, topic, event) -> str:
        message_id = self._publisher.publish(topic, event)
        logger.info(
            "judge trigger published",
            extra={
                "fields": {
                    "event": "judge_trigger_published",
                    "topic": topic,
                    "message_id": message_id,
                }
            },
        )
        return message_id


class UnknownCell(Exception):
    pass


class AreaHasCase(Exception):
    pass


class AreaRequest:
    def __init__(
        self,
        *,
        rankings: RankingRepository,
        cases: CaseRepository,
        publisher: EventPublisher,
        clock: Clock,
        new_id: Callable[[], str],
        region: str,
        example: bool,
    ):
        self._rankings = rankings
        self._cases = cases
        self._publisher = publisher
        self._clock = clock
        self._new_id = new_id
        self._region = region
        self._example = example

    def check(self, cell_id: str) -> RankedCell:
        cell = self._rankings.cell(self._region, cell_id)
        if cell is None:
            raise UnknownCell(cell_id)
        if self._cases.live_in_cell(cell_id) is not None:
            raise AreaHasCase(cell_id)
        return cell

    def send_someone(self, cell: RankedCell) -> str:
        cell_id = cell.cell_id
        event = build_area_requested_event(
            region=self._region,
            cell=cell,
            event_id=self._new_id(),
            occurred_at=self._clock.now(),
            example=self._example,
        )
        message_id = self._publisher.publish("drying.ranked", event)
        logger.info(
            "area requested",
            extra={
                "fields": {
                    "event": "area_requested",
                    "cell_id": cell_id,
                    "message_id": message_id,
                }
            },
        )
        return message_id
