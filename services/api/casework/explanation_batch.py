import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Protocol

from adapters.firestore_repos import RankingRepository
from contracts import RankExplanation
from domain.rank_explanation import EXPLAIN_PROMPT_VERSION, is_current

logger = logging.getLogger(__name__)

TOP_CELLS = 200
CONCURRENCY = 8


class CellExplainer(Protocol):
    async def explain(self, cell_id: str) -> RankExplanation | None: ...


@dataclass(frozen=True)
class BatchResult:
    region: str
    wanted: int
    skipped: int
    done: int
    failed: int
    seconds: float
    call_p50_seconds: float
    call_p95_seconds: float


def percentile(sorted_values: list[float], fraction: float) -> float:
    if not sorted_values:
        return 0.0
    index = min(len(sorted_values) - 1, int(fraction * len(sorted_values)))
    return sorted_values[index]


class ExplanationPrecomputer:
    def __init__(
        self,
        *,
        explainer: CellExplainer,
        rankings: RankingRepository,
        limit: int = TOP_CELLS,
        concurrency: int = CONCURRENCY,
    ):
        self._explainer = explainer
        self._rankings = rankings
        self._limit = limit
        self._concurrency = concurrency

    async def run(self, region: str) -> BatchResult:
        started = time.perf_counter()
        top = await asyncio.to_thread(self._rankings.top, region, self._limit)
        missing = [cell.cell_id for cell in top if not is_current(cell.explanation)]
        durations: list[float] = []
        gate = asyncio.Semaphore(self._concurrency)

        async def one(cell_id: str) -> bool:
            async with gate:
                begun = time.perf_counter()
                explanation = await self._explainer.explain(cell_id)
                durations.append(time.perf_counter() - begun)
                return explanation is not None

        outcomes = await asyncio.gather(*(one(cell_id) for cell_id in missing))
        durations.sort()
        result = BatchResult(
            region=region,
            wanted=len(top),
            skipped=len(top) - len(missing),
            done=outcomes.count(True),
            failed=outcomes.count(False),
            seconds=round(time.perf_counter() - started, 2),
            call_p50_seconds=round(percentile(durations, 0.5), 2),
            call_p95_seconds=round(percentile(durations, 0.95), 2),
        )
        log_result(result)
        return result


def log_result(result: BatchResult) -> None:
    logger.info(
        "explanations precomputed",
        extra={
            "fields": {
                "event": "explanations_precomputed",
                "prompt_version": EXPLAIN_PROMPT_VERSION,
                **result.__dict__,
            }
        },
    )
