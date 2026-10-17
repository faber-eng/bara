import asyncio
import base64
import binascii
import logging
from collections.abc import Mapping
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, ValidationError

from adapters.firestore_repos import CaseRepository, EventLog, RankedDamRepository
from contracts import (
    Case,
    CaseRisk,
    DryingRankedEvent,
    Event,
    EventAdapter,
    HistoryFlags,
    RankedDam,
)
from domain.clock import Clock

logger = logging.getLogger(__name__)

MAX_CONCURRENT_RUNS = 3
FILL_HARD_LIMIT_SECONDS = 480
EXECUTOR_THREADS = 16

DispatchOutcome = Literal["processed", "duplicate"]


class MalformedPush(Exception):
    pass


class UnhandledTopic(Exception):
    pass


class PushMessageBody(BaseModel):
    model_config = ConfigDict(extra="ignore")

    data: str
    messageId: str


class PushBody(BaseModel):
    model_config = ConfigDict(extra="ignore")

    message: PushMessageBody


@dataclass(frozen=True)
class PushMessage:
    message_id: str
    event: Event


def decode_event(data: str) -> Event:
    try:
        raw = base64.b64decode(data, validate=True)
        return EventAdapter.validate_json(raw)
    except (binascii.Error, ValidationError) as error:
        raise MalformedPush(type(error).__name__) from error


def decode_push(body: object) -> PushMessage:
    try:
        parsed = PushBody.model_validate(body)
    except ValidationError as error:
        raise MalformedPush("push body") from error
    if parsed.message.messageId == "":
        raise MalformedPush("empty message id")
    return PushMessage(parsed.message.messageId, decode_event(parsed.message.data))


class AgentRunner(Protocol):
    async def run_case(self, trigger: str, case_id: str, run_id: str): ...


class EventHandler(Protocol):
    def handle(self, message_id: str, event: Event) -> None: ...


class EventDispatcher:
    def __init__(self, events: EventLog, handlers: Mapping[str, EventHandler]):
        self._events = events
        self._handlers = handlers

    def dispatch(self, topic: str, message_id: str, event: Event) -> DispatchOutcome:
        handler = self._handlers.get(topic)
        if handler is None:
            raise UnhandledTopic(topic)
        if event.type != topic:
            raise MalformedPush(f"event type {event.type} on topic {topic}")
        if not self._events.claim(message_id, event.type):
            logger.info(
                "event duplicate",
                extra={
                    "fields": {"event": "event_duplicate", "message_id": message_id}
                },
            )
            return "duplicate"
        try:
            handler.handle(message_id, event)
        except Exception:
            self._events.release(message_id)
            raise
        return "processed"


def case_id_for(message_id: str, dam_id: str) -> str:
    return f"case-{message_id}-{dam_id}"


def build_dam_case(
    event: DryingRankedEvent, dam: RankedDam, message_id: str, clock: Clock
) -> Case:
    return Case(
        id=case_id_for(message_id, dam.dam_id),
        type="dam_risk",
        region=event.region,
        cell_id=dam.cell_id,
        dam_id=dam.dam_id,
        event_id=event.id,
        status="open",
        risk=CaseRisk(drying_score=dam.drying_score, p_reignite=None),
        opened_at=clock.now(),
        closed_by=None,
        closed_at=None,
        history_flags=HistoryFlags(smoke_seen=False),
        example=event.example or dam.example,
    )


class ExplanationFiller(Protocol):
    async def run(self, region: str) -> object: ...


class DryingRankedHandler:
    def __init__(
        self,
        *,
        cases: CaseRepository,
        ranked_dams: RankedDamRepository,
        agent: AgentRunner,
        explanations: ExplanationFiller,
        clock: Clock,
        max_cases: int,
    ):
        self._cases = cases
        self._ranked_dams = ranked_dams
        self._agent = agent
        self._explanations = explanations
        self._clock = clock
        self._max_cases = max_cases

    def handle(self, message_id: str, event: Event) -> None:
        if not isinstance(event, DryingRankedEvent):
            raise MalformedPush("not a drying.ranked event")
        opened = self._open_cases(message_id, event)
        asyncio.run(self._run_everything(message_id, event, opened))

    async def _run_everything(
        self, message_id: str, event: DryingRankedEvent, cases: list[Case]
    ) -> None:
        loop = asyncio.get_running_loop()
        loop.set_default_executor(ThreadPoolExecutor(max_workers=EXECUTOR_THREADS))
        await asyncio.gather(
            self._run_all(message_id, event, cases),
            self._fill_explanations(event.region),
        )

    async def _fill_explanations(self, region: str) -> None:
        try:
            await asyncio.wait_for(
                self._explanations.run(region), FILL_HARD_LIMIT_SECONDS
            )
        except Exception:
            logger.exception(
                "explanations precompute failed",
                extra={
                    "fields": {
                        "event": "explanations_precompute_failed",
                        "region": region,
                    }
                },
            )

    def _open_cases(self, message_id: str, event: DryingRankedEvent) -> list[Case]:
        dams = self._ranked_dams.top(event.region, self._max_cases)
        needing_case = [
            dam for dam in dams if self._cases.open_for_dam(dam.dam_id) is None
        ]
        opened = []
        for dam in needing_case:
            case = build_dam_case(event, dam, message_id, self._clock)
            if self._cases.create(case) and self._keep_if_first(case):
                opened.append(case)
        return opened

    def _keep_if_first(self, case: Case) -> bool:
        first = self._cases.open_for_dam(case.dam_id)
        if first is None or first.id == case.id:
            return True
        self._cases.delete(case.id)
        logger.info(
            "case withdrawn",
            extra={
                "fields": {
                    "event": "event_case_withdrawn",
                    "case_id": case.id,
                    "kept": first.id,
                }
            },
        )
        return False

    async def _run_all(
        self, message_id: str, event: DryingRankedEvent, cases: list[Case]
    ) -> None:
        limit = asyncio.Semaphore(MAX_CONCURRENT_RUNS)

        async def bounded(case: Case) -> None:
            async with limit:
                await self._run_one(message_id, event, case)

        await asyncio.gather(*(bounded(case) for case in cases))

    async def _run_one(
        self, message_id: str, event: DryingRankedEvent, case: Case
    ) -> None:
        try:
            await self._agent.run_case(event.type, case.id, f"{message_id}-{case.id}")
        except Exception:
            logger.exception(
                "case run failed",
                extra={
                    "fields": {
                        "event": "event_case_run_failed",
                        "message_id": message_id,
                        "case_id": case.id,
                    }
                },
            )
