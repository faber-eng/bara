import logging
from collections.abc import Callable

from adapters.firestore_repos import RankedDamRepository, RankingRepository
from adapters.pubsub import EventPublisher
from domain.clock import Clock
from domain.scenario_events import TOP_REFS, build_drying_ranked_event

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
    ):
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
        message_id = self._publisher.publish("drying.ranked", event)
        logger.info(
            "judge trigger published",
            extra={
                "fields": {
                    "event": "judge_trigger_published",
                    "topic": "drying.ranked",
                    "message_id": message_id,
                }
            },
        )
        return message_id
