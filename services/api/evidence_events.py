import asyncio
import logging
from collections.abc import Mapping
from typing import Protocol

from casework.evidence_check import CheckedEvidence, CheckError
from casework.evidence_reader import ReaderFailed
from casework.photo import UnreadablePhoto
from contracts import Event, EvidenceReceivedEvent
from events import MalformedPush

logger = logging.getLogger(__name__)

TRIGGER = "evidence.received"


class Checker(Protocol):
    async def check(self, task_id: str, evidence_id: str) -> CheckedEvidence: ...


class EvidenceAgent(Protocol):
    async def run_case(
        self,
        trigger: str,
        case_id: str,
        run_id: str,
        event: Mapping[str, object] | None = None,
    ): ...


def log_fields(event: str, message_id: str, case_id: str, **fields: object):
    return {
        "fields": {
            "event": event,
            "message_id": message_id,
            "case_id": case_id,
            **fields,
        }
    }


class EvidenceReceivedHandler:
    def __init__(self, *, checker: Checker, agent: EvidenceAgent):
        self._checker = checker
        self._agent = agent

    def handle(self, message_id: str, event: Event) -> None:
        if not isinstance(event, EvidenceReceivedEvent):
            raise MalformedPush("not an evidence.received event")
        asyncio.run(self._handle(message_id, event))

    async def _handle(self, message_id: str, event: EvidenceReceivedEvent) -> None:
        payload = event.payload
        await self._check(message_id, event)
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
                extra=log_fields("event_case_run_failed", message_id, payload.case_id),
            )

    async def _check(self, message_id: str, event: EvidenceReceivedEvent) -> None:
        payload = event.payload
        try:
            await self._checker.check(payload.task_id, payload.evidence_id)
        except (CheckError, ReaderFailed, UnreadablePhoto) as error:
            logger.error(
                "evidence check failed",
                extra=log_fields(
                    "evidence_check_failed",
                    message_id,
                    payload.case_id,
                    evidence_id=payload.evidence_id,
                    error=str(error),
                ),
            )
