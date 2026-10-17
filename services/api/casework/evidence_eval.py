import asyncio
import time
from collections.abc import Awaitable, Callable, Sequence

from casework.evidence_check import Reader, prepare_media
from casework.evidence_reader import ReaderFailed
from casework.media import PreparedMedia, UnreadableMedia
from contracts import EvidenceKind
from domain.evidence_eval import (
    FIELDS,
    LabelRow,
    ScoredItem,
    kind_for,
    task_type_for,
)

DEFAULT_CONCURRENCY = 4
MS_PER_S = 1000.0

Prepare = Callable[[EvidenceKind, bytes], Awaitable[PreparedMedia]]


class EvidenceEvaluator:
    def __init__(
        self,
        reader: Reader,
        *,
        prepare: Prepare = prepare_media,
        timer: Callable[[], float] = time.perf_counter,
        concurrency: int = DEFAULT_CONCURRENCY,
    ):
        self._reader = reader
        self._prepare = prepare
        self._timer = timer
        self._gate = asyncio.Semaphore(concurrency)

    async def score_all(
        self, rows: Sequence[LabelRow], read_bytes: Callable[[LabelRow], bytes]
    ) -> list[ScoredItem]:
        return list(
            await asyncio.gather(*(self._score(row, read_bytes(row)) for row in rows))
        )

    async def _score(self, row: LabelRow, data: bytes) -> ScoredItem:
        async with self._gate:
            started = self._timer()
            try:
                media = await self._prepare(kind_for(row.object_path), data)
                verdict = await self._reader.read(
                    media, task_type_for(row.labels["subject"])
                )
            except (ReaderFailed, UnreadableMedia) as error:
                return self._item(row, None, started, str(error))
            values = verdict.model_dump(mode="json")
            scored = {field: values[field] for field in FIELDS}
            return self._item(row, scored, started, None)

    def _item(
        self,
        row: LabelRow,
        verdict: dict[str, str] | None,
        started: float,
        error: str | None,
    ) -> ScoredItem:
        latency_ms = (self._timer() - started) * MS_PER_S
        return ScoredItem(row=row, verdict=verdict, latency_ms=latency_ms, error=error)
