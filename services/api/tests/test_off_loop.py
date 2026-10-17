import asyncio
import time

from bara_agent.tools.rank_areas import RankAreas
from bara_agent.tools.request_human_review import RequestHumanReview

BLOCK_SECONDS = 0.2


class BlockingRankings:
    def top(self, region, limit):
        time.sleep(BLOCK_SECONDS)
        return []


class BlockingReviewer:
    def request(self, case_id, reason):
        time.sleep(BLOCK_SECONDS)


async def beats_during(work) -> tuple[int, float]:
    beats = 0
    running = True

    async def heartbeat():
        nonlocal beats
        while running:
            beats += 1
            await asyncio.sleep(0.01)

    ticker = asyncio.create_task(heartbeat())
    started = time.perf_counter()
    await work()
    elapsed = time.perf_counter() - started
    running = False
    await ticker
    return beats, elapsed


def test_blocking_reads_in_a_sync_repository_do_not_stop_the_event_loop():
    tool = RankAreas(BlockingRankings())

    async def five_at_once():
        await asyncio.gather(*(tool.rank_areas("riau") for _ in range(5)))

    beats, elapsed = asyncio.run(beats_during(five_at_once))

    assert elapsed < BLOCK_SECONDS * 2
    assert beats >= 10


def test_the_human_review_write_does_not_stop_the_event_loop():
    tool = RequestHumanReview(BlockingReviewer())

    async def three_at_once():
        await asyncio.gather(
            *(tool.request_human_review(f"c{index}", "why") for index in range(3))
        )

    beats, elapsed = asyncio.run(beats_during(three_at_once))

    assert elapsed < BLOCK_SECONDS * 2
    assert beats >= 10
