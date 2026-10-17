import asyncio
import logging
from collections.abc import Mapping
from typing import Protocol

from casework.evidence_check import CheckedEvidence, CheckError
from casework.evidence_reader import ReaderFailed
from casework.photo import UnreadablePhoto
from contracts import Event, EvidenceReceived, EvidenceReceivedEvent
from events import MalformedPush
from logs import log_extra

logger = logging.getLogger(__name__)

TRIGGER = "evidence.received"


class Checker(Protocol):
    async def check(self, task_id: str, evidence_id: str) -> CheckedEvidence: ...

    def flag_for_person(self, case_id: str) -> None: ...


class EvidenceAgent(Protocol):
    async def run_case(
        self,
        trigger: str,
        case_id: str,
        run_id: str,
        event: Mapping[str, object] | None = None,
    ): ...


class EvidenceReceivedHandler:
    def __init__(self, *, checker: Checker, agent: EvidenceAgent):
        self._checker = checker
        self._agent = agent

    def handle(self, message_id: str, event: Event) -> None:
        if not isinstance(event, EvidenceReceivedEvent):
            raise MalformedPush("not an evidence.received event")
        asyncio.run(self._handle(message_id, event.payload))

    async def _handle(self, message_id: str, payload: EvidenceReceived) -> None:
        checked = await self._check(message_id, payload)
        if checked is None:
            self._checker.flag_for_person(payload.case_id)
            return
        if not checked.stored:
            logger.info(
                "evidence already checked",
                extra=log_extra(
                    "evidence_already_checked",
                    message_id=message_id,
                    evidence_id=payload.evidence_id,
                ),
            )
            return
        if checked.awaits_agent:
            await self._run_agent(message_id, payload)
        self._checker.flag_for_person(payload.case_id)

    async def _check(
        self, message_id: str, payload: EvidenceReceived
    ) -> CheckedEvidence | None:
        try:
            return await self._checker.check(payload.task_id, payload.evidence_id)
        except (CheckError, ReaderFailed, UnreadablePhoto) as error:
            logger.error(
                "evidence check failed",
                extra=log_extra(
                    "evidence_check_failed",
                    message_id=message_id,
                    case_id=payload.case_id,
                    evidence_id=payload.evidence_id,
                    error=str(error),
                ),
            )
            return None

    async def _run_agent(self, message_id: str, payload: EvidenceReceived) -> None:
        try:
            await self._agent.run_case(
                TRIGGER,
                payload.case_id,
                f"{message_id}-{payload.case_id}",
                payload.model_dump(mode="json"),
            )
        except Exception:
            logger.exception(
                "case run failed",
                extra=log_extra(
                    "event_case_run_failed",
                    message_id=message_id,
                    case_id=payload.case_id,
                ),
            )
