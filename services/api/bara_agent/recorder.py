import time
from collections.abc import Callable, Mapping
from typing import Any

from google.adk.agents.callback_context import CallbackContext
from google.adk.models.llm_response import LlmResponse
from google.adk.plugins.base_plugin import BasePlugin
from google.adk.tools.base_tool import BaseTool
from google.adk.tools.tool_context import ToolContext

from contracts import ToolCall

Summarizer = Callable[[Mapping[str, object]], str]

MAX_SUMMARY_CHARS = 200


def one_line(text: object) -> str:
    return " ".join(str(text).split())[:MAX_SUMMARY_CHARS]


def elapsed_ms(started: float) -> int:
    return max(0, round((time.perf_counter() - started) * 1000))


class RunRecorder(BasePlugin):
    def __init__(self, summarizers: Mapping[str, Summarizer]):
        super().__init__(name="bara_run_recorder")
        self._summarizers = summarizers
        self._pending: dict[int, tuple[int, float]] = {}
        self._calls: list[ToolCall | None] = []
        self._on_call_finished: Callable[[], None] | None = None
        self.model_version: str | None = None

    def on_call_finished(self, listener: Callable[[], None]) -> None:
        self._on_call_finished = listener

    @property
    def tool_calls(self) -> list[ToolCall]:
        return [call for call in self._calls if call is not None]

    def called_tools(self) -> set[str]:
        return {call.name for call in self.tool_calls}

    async def before_tool_callback(
        self, *, tool: BaseTool, tool_args: dict[str, Any], tool_context: ToolContext
    ) -> None:
        self._pending[id(tool_context)] = (len(self._calls), time.perf_counter())
        self._calls.append(None)

    async def after_tool_callback(
        self,
        *,
        tool: BaseTool,
        tool_args: dict[str, Any],
        tool_context: ToolContext,
        result: dict[str, Any],
    ) -> None:
        self._finish(tool, tool_args, tool_context, self._summarize(tool.name, result))

    async def on_tool_error_callback(
        self,
        *,
        tool: BaseTool,
        tool_args: dict[str, Any],
        tool_context: ToolContext,
        error: Exception,
    ) -> None:
        self._finish(tool, tool_args, tool_context, f"error: {type(error).__name__}")

    async def after_model_callback(
        self, *, callback_context: CallbackContext, llm_response: LlmResponse
    ) -> None:
        if llm_response.model_version:
            self.model_version = llm_response.model_version

    def _summarize(self, name: str, result: Mapping[str, object]) -> str:
        if "error" in result:
            return f"error: {one_line(result['error'])}"
        return one_line(self._summarizers[name](result))

    def _finish(
        self,
        tool: BaseTool,
        tool_args: dict[str, Any],
        tool_context: ToolContext,
        summary: str,
    ) -> None:
        slot, started = self._pending.pop(id(tool_context))
        self._calls[slot] = ToolCall(
            name=tool.name,
            args=dict(tool_args),
            result_summary=summary,
            ms=elapsed_ms(started),
        )
        if self._on_call_finished is not None:
            self._on_call_finished()
