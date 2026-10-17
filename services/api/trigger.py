import logging
from collections.abc import Callable

from adapters.firestore_repos import RankedDamRepository, RankingRepository
from adapters.pubsub import EventPublisher
from domain.clock import Clock
from domain.scenario import Scenario
from domain.scenario_events import (
    TOP_REFS,
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
