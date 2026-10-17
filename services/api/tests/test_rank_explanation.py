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
    render_facts,
)
from contracts import RankedCell, RankExplanation
from domain.rank_explanation import (
    ExplanationRejected,
    check_explanation,
    shown_values,
)
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
    "The radar dryness signal is -4.2 dB and the nearest canal is 140 m away."
)
GOOD_CITED = {
    "drying_score": 90.5,
    "rank": 1,
    "s1_anom_db": -4.2,
    "canal_dist_m": 140.0,
}


def check(text=GOOD_TEXT, cited=None):
    check_explanation(
        text,
        GOOD_CITED if cited is None else cited,
        shown_values(FACTS),
        "riau-1-1",
    )


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

    assert explanation == RankExplanation(
        text=GOOD_TEXT, cited=GOOD_CITED, prompt_version=EXPLAIN_PROMPT_VERSION
    )
    assert world.stored() == explanation
    assert world.facts.calls == ["riau-1-1"]
    role, contents, config = world.model.calls[0]
    assert role == "fast"
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
    assert EXPLAIN_PROMPT_VERSION == "explain-v2"


@pytest.mark.parametrize(
    "text",
    [
        "Cell riau-1-1 ranks 1 with a drying score of 90.5 and a canal 140 m away.",
    ],
)
def test_an_integer_written_for_a_whole_value_passes(text):
    check(text=text, cited={"drying_score": 90.5, "rank": 1, "canal_dist_m": 140.0})


@pytest.mark.parametrize(
    "text,bad",
    [
        ("Rank 1 with a drying score of 90.", "90"),
        ("Rank 1, score 90.5, deficit 0.", "0"),
    ],
)
def test_a_rounded_or_stray_number_is_rejected(text, bad):
    facts = shown_values({**FACTS, "peat_class": 2})
    with pytest.raises(ExplanationRejected, match="not cited"):
        check_explanation(text, {"drying_score": 90.5, "rank": 1}, facts, "riau-1-1")


def test_digits_inside_field_names_are_not_numbers():
    text = (
        "Rank 1 with s1_anom_db of -4.2 dB and rain_30d_mm of 180 mm near Sentinel-1."
    )
    check_explanation(
        text,
        {"rank": 1, "s1_anom_db": -4.2, "rain_30d_mm": 180},
        shown_values(FACTS),
        "riau-1-1",
    )


def test_a_field_cited_twice_is_retried():
    dup = reply()
    body = json.loads(dup.text)
    body["cited"].append({"field": "rank", "value": 1})
    doubled = types.GenerateContentResponse(
        candidates=[
            types.Candidate(
                content=types.Content(
                    role="model", parts=[types.Part(text=json.dumps(body))]
                )
            )
        ]
    )
    world = World([doubled, reply()])

    assert world.explain().text == GOOD_TEXT
    assert len(world.model.calls) == 2


def test_a_model_error_is_not_remembered_for_the_week():
    world = World(
        [errors.APIError(503, {"error": {"code": 503, "message": "x"}}), reply()]
    )

    assert world.explain() is None
    assert world.explain().text == GOOD_TEXT


def test_two_requests_at_once_make_one_model_call():
    world = World([reply()])

    async def both():
        return await asyncio.gather(
            world.explainer.explain("riau-1-1"), world.explainer.explain("riau-1-1")
        )

    first, second = asyncio.run(both())

    assert first == second
    assert len(world.model.calls) == 1


def test_a_store_failure_still_returns_the_explanation(caplog):
    world = World([reply()])

    def down(*args):
        raise RuntimeError("firestore is down")

    world.explainer._rankings.set_explanation = down

    with caplog.at_level(logging.ERROR):
        explanation = world.explain()

    assert explanation.text == GOOD_TEXT
    events = [r.fields["event"] for r in caplog.records if hasattr(r, "fields")]
    assert "explain_rank_store_failed" in events


def test_a_facts_failure_gives_null_not_an_exception():
    class Broken:
        def get_area_facts(self, cell_id):
            raise RuntimeError("bigquery is down")

    world = World([], facts=Broken())

    assert world.explain() is None


LIVE = {
    "drying_score": 96.84027719188221,
    "rank": 1,
    "s1_anom_db": -5.0767897814995315,
    "rain_30d_mm": 183.6,
    "rain_deficit_pct": 0.3149,
    "canal_dist_m": 2504.7206600213553,
    "peat_class": 1,
}


def test_live_values_are_rounded_for_reading():
    written = {field: shown.written for field, shown in shown_values(LIVE).items()}

    assert written == {
        "drying_score": "96.8",
        "rank": "1",
        "s1_anom_db": "-5.1 dB",
        "rain_30d_mm": "184 mm",
        "rain_deficit_pct": "31%",
        "canal_dist_m": "2.5 km",
        "peat_class": "1",
    }


def test_a_distance_under_a_kilometre_is_whole_metres():
    assert shown_values({"canal_dist_m": 139.6})["canal_dist_m"].written == "140 m"


def test_the_facts_block_names_each_fact_in_plain_words_with_its_written_form():
    block = render_facts("riau-1-1", shown_values(LIVE))

    assert "radar dryness signal" in block
    assert "distance to the nearest canal" in block
    assert '"written": "2.5 km"' in block
    assert "2504" not in block
    assert "96.84" not in block


ROUNDED_TEXT = (
    "Cell riau-1-1 ranks 1 with a drying score of 96.8. The radar dryness "
    "signal is -5.1 dB and the nearest canal is 2.5 km away."
)
ROUNDED_CITED = {
    "drying_score": 96.8,
    "rank": 1,
    "s1_anom_db": -5.1,
    "canal_dist_m": 2.5,
}


def test_a_correctly_rounded_text_passes_the_number_check():
    check_explanation(ROUNDED_TEXT, ROUNDED_CITED, shown_values(LIVE), "riau-1-1")


@pytest.mark.parametrize(
    "old,new",
    [("96.8", "96.9"), ("-5.1", "-5.2"), ("2.5 km", "3.5 km"), ("96.8", "96.84")],
)
def test_an_invented_or_unrounded_number_in_the_text_fails_the_number_check(old, new):
    text = ROUNDED_TEXT.replace(old, new)

    with pytest.raises(ExplanationRejected):
        check_explanation(text, ROUNDED_CITED, shown_values(LIVE), "riau-1-1")


def test_a_cited_value_that_is_the_unrounded_figure_fails_the_number_check():
    cited = {**ROUNDED_CITED, "drying_score": 96.84027719188221}

    with pytest.raises(ExplanationRejected, match="drying_score"):
        check_explanation(ROUNDED_TEXT, cited, shown_values(LIVE), "riau-1-1")


def test_the_stored_explanation_names_the_prompt_version():
    world = World([reply()])

    assert world.explain().prompt_version == EXPLAIN_PROMPT_VERSION


def test_a_distance_written_in_the_wrong_unit_is_rejected():
    text = ROUNDED_TEXT.replace("2.5 km", "2.5 m")

    with pytest.raises(ExplanationRejected, match="canal_dist_m"):
        check_explanation(text, ROUNDED_CITED, shown_values(LIVE), "riau-1-1")


def test_a_deficit_written_as_millimetres_is_rejected():
    values = {**LIVE}
    text = "Cell riau-1-1 ranks 1 and the rain deficit is 31 mm."
    cited = {"rank": 1, "rain_deficit_pct": 31}

    with pytest.raises(ExplanationRejected, match="rain_deficit_pct"):
        check_explanation(text, cited, shown_values(values), "riau-1-1")


def test_a_small_negative_signal_is_not_written_as_negative_zero():
    assert shown_values({"s1_anom_db": -0.04})["s1_anom_db"].written == "0.0 dB"


def test_a_distance_that_rounds_to_a_kilometre_is_written_in_km():
    assert shown_values({"canal_dist_m": 999.6})["canal_dist_m"].written == "1.0 km"
