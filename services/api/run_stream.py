import asyncio
import json
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime

from adapters.firestore_repos import AgentRunRepository, CaseRepository
from case_queries import UnknownCase
from contracts import AgentRun

POLL_SECONDS = 0.5
MAX_WAIT_SECONDS = 120.0
KEEPALIVE_EVERY_POLLS = 20


@dataclass(frozen=True)
class StreamEvent:
    name: str
    data: dict[str, object]


def tool_event(run: AgentRun, index: int, seen_at: datetime) -> StreamEvent:
    return StreamEvent(
        "tool",
        {
            "run_id": run.id,
            "index": index,
            "call": run.tool_calls[index].model_dump(mode="json"),
            "seen_at": seen_at.isoformat(),
        },
    )


def final_event(run: AgentRun) -> StreamEvent:
    return StreamEvent(
        "final",
        {
            "run_id": run.id,
            "status": run.status,
            "final_json": run.final_json.model_dump(mode="json")
            if run.final_json is not None
            else None,
            "model": run.model,
            "ms": run.ms,
        },
    )


def render(event: StreamEvent) -> str:
    if event.name == "keepalive":
        return ": keepalive\n\n"
    return f"event: {event.name}\ndata: {json.dumps(event.data)}\n\n"


def latest_run(runs: list[AgentRun]) -> AgentRun | None:
    if not runs:
        return None
    return runs[-1]


def run_with_id(runs: list[AgentRun], run_id: str) -> AgentRun | None:
    return next((run for run in runs if run.id == run_id), None)


class RunStreamer:
    def __init__(
        self,
        *,
        cases: CaseRepository,
        runs: AgentRunRepository,
        now: Callable[[], datetime],
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        poll_seconds: float = POLL_SECONDS,
        max_wait_seconds: float = MAX_WAIT_SECONDS,
    ):
        self._cases = cases
        self._runs = runs
        self._now = now
        self._sleep = sleep
        self._poll_seconds = poll_seconds
        self._max_polls = int(max_wait_seconds / poll_seconds)

    async def require_case(self, case_id: str) -> None:
        case = await asyncio.to_thread(self._cases.get, case_id)
        if case is None:
            raise UnknownCase(case_id)

    async def events(self, case_id: str) -> AsyncIterator[StreamEvent]:
        yield StreamEvent("open", {"case_id": case_id})
        run_id: str | None = None
        sent = 0
        for poll in range(self._max_polls):
            runs = await asyncio.to_thread(self._runs.for_case, case_id)
            run = latest_run(runs) if run_id is None else run_with_id(runs, run_id)
            if run is not None:
                run_id = run.id
                for index in range(sent, len(run.tool_calls)):
                    yield tool_event(run, index, self._now())
                sent = len(run.tool_calls)
                if run.status != "running":
                    yield final_event(run)
                    return
            if poll % KEEPALIVE_EVERY_POLLS == KEEPALIVE_EVERY_POLLS - 1:
                yield StreamEvent("keepalive", {})
            await self._sleep(self._poll_seconds)
        yield StreamEvent("timeout", {"case_id": case_id})
