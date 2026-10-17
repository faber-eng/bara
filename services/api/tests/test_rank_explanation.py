import asyncio
import json
import logging
from datetime import date

import pytest
from google.genai import errors, types

from adapters.firestore_repos import RankingRepository
from casework.rank_explanation import (
    EXPLAIN_PROMPT_VERSION,
    RankExplainer,
)
from contracts import RankedCell, RankExplanation
from domain.rank_explanation import ExplanationRejected, check_explanation
from tests.fakes import InMemoryCollection, make_ranked_cell

FACTS = {
    "drying_score": 90.5,
    "rank": 1,
    "s1_anom_db": -4.2,
    "rain_30d_mm": 180.0,
    "rain_deficit_pct": 0.31,
    "canal_dist_m": 140.0,
    "peat_class": 1,
}
GOOD_TEXT = (
    "Cell riau-1-1 ranks 1 with a drying score of 90.5. "
    "The radar anomaly is -4.2 dB and the canal is 140.0 m away."
)
GOOD_CITED = {
    "drying_score": 90.5,
    "rank": 1,
    "s1_anom_db": -4.2,
    "canal_dist_m": 140.0,
}


def check(text=GOOD_TEXT, cited=None):
    check_explanation(text, GOOD_CITED if cited is None else cited, FACTS, "riau-1-1")


def test_a_text_whose_numbers_are_all_cited_and_exact_passes():
    check()


def test_a_number_in_the_text_that_is_not_cited_is_rejected():
    with pytest.raises(ExplanationRejected, match="12"):
        check(text=GOOD_TEXT + " It rained 12 mm.")


def test_a_cited_value_that_differs_from_the_data_is_rejected():
    with pytest.raises(ExplanationRejected, match="drying_score"):
        check(cited={**GOOD_CITED, "drying_score": 91.0})


def test_a_cited_field_that_is_not_a_known_field_is_rejected():
    with pytest.raises(ExplanationRejected, match="humidity"):
        check(cited={**GOOD_CITED, "humidity": 4})


def test_a_cited_value_missing_from_the_text_is_rejected():
    with pytest.raises(ExplanationRejected, match="rain_30d_mm"):
        check(cited={**GOOD_CITED, "rain_30d_mm": 180.0})


def test_a_text_number_that_is_a_wrong_figure_is_rejected():
    with pytest.raises(ExplanationRejected, match="91.5"):
        check(text=GOOD_TEXT.replace("90.5", "91.5"))


def test_a_text_number_rounded_to_its_written_precision_passes():
    facts = {**FACTS, "drying_score": 90.5321}
    check_explanation(
        GOOD_TEXT.replace("90.5", "90.53"),
        {**GOOD_CITED, "drying_score": 90.5321},
        facts,
        "riau-1-1",
    )


def test_a_text_without_cited_numbers_is_rejected():
    with pytest.raises(ExplanationRejected, match="no cited"):
        check(text="The cell is drying fast.", cited={})


def reply(text=GOOD_TEXT, cited=None):
    cited = GOOD_CITED if cited is None else cited
    body = {
        "text": text,
        "cited": [{"field": key, "value": value} for key, value in cited.items()],
    }
    return types.GenerateContentResponse(
        candidates=[
            types.Candidate(
                content=types.Content(
                    role="model", parts=[types.Part(text=json.dumps(body))]
                )
            )
        ]
    )


class FakeModel:
    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []

    async def generate(self, role, contents, config=None):
        self.calls.append((role, contents, config))
        outcome = self.replies.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class FakeFacts:
    def __init__(self, result=None):
        self.calls = []
        self.result = result

    def get_area_facts(self, cell_id):
        self.calls.append(cell_id)
        if self.result is not None:
            return self.result
        return {
            "cell_id": cell_id,
            "region": "riau",
            "week": "2026-W42",
            "components": {
                "s1_anom_db": -4.2,
                "rain_30d_mm": 180.0,
                "rain_deficit_pct": 0.31,
                "canal_dist_m": 140.0,
                "peat_class": 1,
            },
            "drying_score": 90.5,
            "rank": 1,
            "stale_s1": False,
            "trend": [],
            "nearby_dams": [],
        }


class World:
    def __init__(self, replies, ranked=True, facts=None):
        self.collection = InMemoryCollection(RankedCell)
        if ranked:
            self.collection.put("riau-1-1", make_ranked_cell())
        self.model = FakeModel(replies)
        self.facts = facts or FakeFacts()
        self.explainer = RankExplainer(
            model=self.model,
            facts=self.facts,
            rankings=RankingRepository(lambda region: self.collection),
        )

    def explain(self, cell_id="riau-1-1"):
        return asyncio.run(self.explainer.explain(cell_id))

    def stored(self):
        return self.collection.get("riau-1-1").explanation


def test_a_valid_reply_is_returned_and_stored_on_the_ranked_cell():
    world = World([reply()])

    explanation = world.explain()

    assert explanation == RankExplanation(text=GOOD_TEXT, cited=GOOD_CITED)
    assert world.stored() == explanation
    assert world.facts.calls == ["riau-1-1"]
    role, contents, config = world.model.calls[0]
    assert role == "reasoning"
    assert "<<<FACTS" in contents
    assert "90.5" in contents
    assert config.response_mime_type == "application/json"


def test_an_invalid_reply_is_retried_once_and_the_second_is_stored():
    world = World([reply(text=GOOD_TEXT + " It rained 12 mm."), reply()])

    explanation = world.explain()

    assert explanation.text == GOOD_TEXT
    assert len(world.model.calls) == 2


def test_two_invalid_replies_give_null_and_a_log_and_store_nothing(caplog):
    bad = reply(cited={**GOOD_CITED, "drying_score": 99.0})
    world = World([bad, bad])

    with caplog.at_level(logging.WARNING):
        explanation = world.explain()

    assert explanation is None
    assert world.stored() is None
    assert len(world.model.calls) == 2
    events = [r.fields["event"] for r in caplog.records if hasattr(r, "fields")]
    assert events.count("explain_rank_rejected") == 2
    assert "explain_rank_failed" in events


def test_more_than_three_sentences_is_retried_then_null():
    long = reply(text=GOOD_TEXT + " One. Two.")
    world = World([long, long])

    assert world.explain() is None
    assert len(world.model.calls) == 2


def test_a_model_error_gives_null_without_a_retry():
    world = World([errors.APIError(500, {"error": {"code": 500, "message": "x"}})])

    assert world.explain() is None
    assert len(world.model.calls) == 1


def test_the_same_cell_and_week_is_never_generated_twice():
    world = World([reply()])

    world.explain()
    again = world.explain()

    assert again is not None
    assert len(world.model.calls) == 1


def test_a_failed_cell_and_week_is_not_retried_on_the_next_call():
    bad = reply(text="No numbers here at all.", cited={})
    world = World([bad, bad])

    world.explain()
    world.explain()

    assert len(world.model.calls) == 2


def test_a_cell_without_a_ranking_document_still_returns_the_explanation():
    world = World([reply()], ranked=False)

    assert world.explain().text == GOOD_TEXT


def test_an_unknown_cell_returns_null_without_a_model_call():
    world = World([], facts=FakeFacts({"error": "no drying data for cell 'x'"}))

    assert world.explain("x") is None
    assert world.model.calls == []


def test_a_ranking_document_of_another_week_is_left_alone():
    world = World([reply()])
    world.collection.put("riau-1-1", make_ranked_cell(week_start=date(2026, 10, 5)))

    world.explain()

    assert world.stored() is None


def test_the_prompt_version_is_named():
    assert EXPLAIN_PROMPT_VERSION == "explain-v1"
