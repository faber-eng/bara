import asyncio

from adapters.firestore_repos import RankingRepository
from casework.explanation_batch import ExplanationPrecomputer
from contracts import RankedCell, RankExplanation
from domain.rank_explanation import EXPLAIN_PROMPT_VERSION
from tests.fakes import InMemoryCollection, make_ranked_cell

CURRENT = RankExplanation(
    text="new", cited={"rank": 1}, prompt_version=EXPLAIN_PROMPT_VERSION
)
OLD = RankExplanation(text="old", cited={"rank": 1}, prompt_version="explain-v1")


class FakeExplainer:
    def __init__(self, fail: set[str] | None = None, delay: float = 0.01):
        self.calls: list[str] = []
        self.in_flight = 0
        self.peak = 0
        self._fail = fail or set()
        self._delay = delay

    async def explain(self, cell_id: str) -> RankExplanation | None:
        self.calls.append(cell_id)
        self.in_flight += 1
        self.peak = max(self.peak, self.in_flight)
        await asyncio.sleep(self._delay)
        self.in_flight -= 1
        if cell_id in self._fail:
            return None
        return CURRENT


def world(count: int, **overrides):
    collection = InMemoryCollection(RankedCell)
    for rank in range(1, count + 1):
        cell_id = f"riau-{rank}"
        collection.put(
            cell_id, make_ranked_cell(cell_id=cell_id, rank=rank, **overrides)
        )
    return RankingRepository(lambda region: collection), collection


def run(explainer, rankings, **kwargs):
    precomputer = ExplanationPrecomputer(
        explainer_factory=lambda: explainer, rankings=rankings, **kwargs
    )
    return asyncio.run(precomputer.run("riau"))


def test_only_the_top_cells_up_to_the_limit_are_explained():
    rankings, _ = world(30)
    explainer = FakeExplainer()

    result = run(explainer, rankings, limit=20)

    assert sorted(explainer.calls) == sorted(f"riau-{n}" for n in range(1, 21))
    assert (result.wanted, result.done, result.failed, result.skipped) == (
        20,
        20,
        0,
        0,
    )


def test_no_more_than_the_concurrency_runs_at_once():
    rankings, _ = world(40)
    explainer = FakeExplainer()

    run(explainer, rankings, limit=40, concurrency=8)

    assert explainer.peak == 8


def test_a_cell_with_a_current_explanation_is_skipped():
    rankings, collection = world(3)
    collection.put(
        "riau-2", make_ranked_cell(cell_id="riau-2", rank=2, explanation=CURRENT)
    )
    explainer = FakeExplainer()

    result = run(explainer, rankings)

    assert sorted(explainer.calls) == ["riau-1", "riau-3"]
    assert result.skipped == 1


def test_a_cell_with_an_older_prompt_version_is_explained_again():
    rankings, _ = world(2, explanation=OLD)
    explainer = FakeExplainer()

    result = run(explainer, rankings)

    assert sorted(explainer.calls) == ["riau-1", "riau-2"]
    assert result.skipped == 0


def test_a_failed_cell_is_counted_and_does_not_stop_the_others():
    rankings, _ = world(5)
    explainer = FakeExplainer(fail={"riau-3"})

    result = run(explainer, rankings)

    assert (result.done, result.failed) == (4, 1)
    assert len(explainer.calls) == 5


def test_the_result_carries_the_time_of_the_run_and_of_one_call():
    rankings, _ = world(16)

    result = run(FakeExplainer(delay=0.05), rankings, concurrency=8)

    assert result.seconds >= 0.1
    assert 0.05 <= result.call_p50_seconds <= result.call_p95_seconds


def test_a_region_with_no_ranked_cells_does_nothing():
    rankings = RankingRepository(lambda region: InMemoryCollection(RankedCell))

    result = run(FakeExplainer(), rankings)

    assert (result.wanted, result.done, result.seconds >= 0) == (0, 0, True)


def test_no_new_cell_starts_after_the_start_budget():
    rankings, _ = world(12)
    explainer = FakeExplainer(delay=0.05)

    result = run(explainer, rankings, concurrency=2, start_budget_seconds=0.12)

    assert result.unstarted > 0
    assert result.done + result.unstarted == 12
    assert len(explainer.calls) == result.done


def test_each_run_builds_a_fresh_explainer():
    rankings, _ = world(2)
    built = []

    def factory():
        built.append(FakeExplainer())
        return built[-1]

    precomputer = ExplanationPrecomputer(explainer_factory=factory, rankings=rankings)
    asyncio.run(precomputer.run("riau"))
    asyncio.run(precomputer.run("riau"))

    assert len(built) == 2
