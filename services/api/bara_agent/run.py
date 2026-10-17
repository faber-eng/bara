import asyncio
import logging
import time
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime

from google.adk.agents.run_config import RunConfig
from google.adk.apps import App
from google.adk.events import Event
from google.adk.models import BaseLlm
from google.adk.runners import InMemoryRunner
from google.genai import types
from pydantic import ValidationError

from adapters.firestore_repos import AgentRunRepository, CaseRepository, DamRepository
from bara_agent.agent import AgentTool, build_coordinator, summarizers
from bara_agent.output import AgentOutput
from bara_agent.prompts import PROMPT_VERSION, RunInput, render_run_input
from bara_agent.recorder import RunRecorder, elapsed_ms
from contracts import AgentDecision, AgentRun, AgentRunStatus, Case, Dam
from domain.clock import Clock

logger = logging.getLogger(__name__)

APP_NAME = "bara"
USER_ID = "bara-system"


class CaseNotFound(Exception):
    pass


class AgentOutputInvalid(Exception):
    pass


def final_text(event: Event) -> str | None:
    if event.content is None or not event.content.parts:
        return None
    return "".join(
        part.text for part in event.content.parts if part.text and not part.thought
    )


def describe_errors(error: ValidationError) -> str:
    return "; ".join(
        f"{detail['type']} at {'.'.join(str(part) for part in detail['loc'])}"
        for detail in error.errors(include_input=False)
    )


def parse_output(text: str | None) -> AgentOutput:
    if text is None:
        raise AgentOutputInvalid("the run ended without a final output")
    try:
        return AgentOutput.model_validate_json(text)
    except ValidationError as error:
        raise AgentOutputInvalid(describe_errors(error)) from None


@dataclass(frozen=True)
class RunContext:
    trigger: str
    case_id: str
    run_id: str
    started_at: datetime
    started: float
    recorder: RunRecorder

    def log_fields(self, event: str, **fields: object) -> dict[str, dict[str, object]]:
        return {
            "fields": {
                "event": event,
                "case_id": self.case_id,
                "run_id": self.run_id,
                "trigger": self.trigger,
                **fields,
            }
        }


class AgentService:
    def __init__(
        self,
        *,
        model: BaseLlm,
        tools: Sequence[AgentTool],
        cases: CaseRepository,
        dams: DamRepository,
        runs: AgentRunRepository,
        clock: Clock,
        max_llm_calls: int,
    ):
        self._agent = build_coordinator(model, tools)
        self._default_model = model.model
        self._summarizers = summarizers(tools)
        self._cases = cases
        self._dams = dams
        self._runs = runs
        self._clock = clock
        self._max_llm_calls = max_llm_calls

    async def run_case(
        self,
        trigger: str,
        case_id: str,
        run_id: str,
        event: Mapping[str, object] | None = None,
    ) -> AgentRun:
        case = await asyncio.to_thread(self._cases.get, case_id)
        if case is None:
            raise CaseNotFound(case_id)
        dam = await asyncio.to_thread(self._dam_for, case)
        recorder = RunRecorder(self._summarizers)
        started_at = self._clock.now()
        started = time.perf_counter()
        message = render_run_input(RunInput(trigger, case, dam, event, started_at))
        context = RunContext(trigger, case_id, run_id, started_at, started, recorder)
        save_progress = self._progress_saver(context)
        recorder.on_call_finished(save_progress)
        await save_progress()
        try:
            text = await self._execute(recorder, message)
        except Exception:
            logger.exception(
                "agent run failed", extra=context.log_fields("agent_run_failed")
            )
            await asyncio.to_thread(self._store_failed_run, context)
            raise
        try:
            output = parse_output(text)
        except AgentOutputInvalid as error:
            logger.error(
                "agent output invalid",
                extra=context.log_fields("agent_output_invalid", error=str(error)),
            )
            await asyncio.to_thread(self._store_failed_run, context)
            raise
        self._warn_on_evidence_mismatch(context, output)
        return await asyncio.to_thread(self._save, context, output.to_decision())

    def _progress_saver(self, context: RunContext) -> Callable[[], Awaitable[None]]:
        gate = asyncio.Lock()

        async def save() -> None:
            async with gate:
                await asyncio.to_thread(self._save_progress, context)

        return save

    def _dam_for(self, case: Case) -> Dam | None:
        if case.dam_id is None:
            return None
        return self._dams.get(case.dam_id)

    async def _execute(self, recorder: RunRecorder, message: str) -> str | None:
        app = App(name=APP_NAME, root_agent=self._agent, plugins=[recorder])
        runner = InMemoryRunner(app=app)
        try:
            session = await runner.session_service.create_session(
                app_name=APP_NAME, user_id=USER_ID
            )
            content = types.Content(role="user", parts=[types.Part(text=message)])
            text = None
            async for event in runner.run_async(
                user_id=USER_ID,
                session_id=session.id,
                new_message=content,
                run_config=RunConfig(max_llm_calls=self._max_llm_calls),
            ):
                if event.is_final_response():
                    text = final_text(event)
            return text
        finally:
            await runner.close()

    def _warn_on_evidence_mismatch(
        self, context: RunContext, output: AgentOutput
    ) -> None:
        called = context.recorder.called_tools()
        uncalled = sorted(set(output.evidence) - called)
        if not uncalled:
            return
        logger.warning(
            "agent evidence names tools it did not call",
            extra=context.log_fields(
                "agent_evidence_mismatch", uncalled=uncalled, called=sorted(called)
            ),
        )

    def _store_failed_run(self, context: RunContext) -> None:
        self._try_save(context, None, "failed")

    def _save_progress(self, context: RunContext) -> None:
        self._try_save(context, None, "running")

    def _try_save(
        self,
        context: RunContext,
        decision: AgentDecision | None,
        status: AgentRunStatus,
    ) -> None:
        try:
            self._save(context, decision, status)
        except Exception:
            logger.exception(
                "agent run store failed",
                extra=context.log_fields("agent_run_store_failed", status=status),
            )

    def _save(
        self,
        context: RunContext,
        decision: AgentDecision | None,
        status: AgentRunStatus = "done",
    ) -> AgentRun:
        run = AgentRun(
            id=context.run_id,
            trigger=context.trigger,
            tool_calls=context.recorder.tool_calls,
            final_json=decision,
            model=context.recorder.model_version or self._default_model,
            prompt_version=PROMPT_VERSION,
            started_at=context.started_at,
            ms=elapsed_ms(context.started),
            status=status,
        )
        self._runs.save(context.case_id, run)
        logger.info(
            "agent run stored",
            extra=context.log_fields(
                "agent_run_stored",
                calls=len(run.tool_calls),
                ms=run.ms,
                model=run.model,
                final=decision is not None,
            ),
        )
        return run
