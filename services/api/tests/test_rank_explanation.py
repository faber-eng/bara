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
from contracts import ExplanationPoint, RankedCell, RankExplanation
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
LEAD = "drying faster than any other area in Riau this week"
GOOD_TEXT = (
    f"This area is {LEAD} (score 90.5 of 100). "
    "The radar dryness signal is -4.2 dB and the nearest canal is 140 m away."
)
GOOD_CITED = {
    "drying_score": 90.5,
    "s1_anom_db": -4.2,
    "canal_dist_m": 140.0,
}


WEIGHTS = {
    "s1_anom_db": 0.45,
    "rain_deficit_pct": 0.30,
    "canal_dist_m": 0.15,
    "peat_class": 0.10,
}
SUMMARY = f"This area is {LEAD} (score 90.5 of 100)."
POINTS = [
    (
        "s1_anom_db",
        "raises",
        (
            "The radar dryness signal is -4.2 dB, so the peat is drier than usual, "
            "which pushes the score up."
        ),
    ),
    (
        "rain_deficit_pct",
        "raises",
        "It had 31% less rain than normal, which pushes the score up.",
    ),
    (
        "canal_dist_m",
        "raises",
        "A canal 140 m away drains the peat, which pushes the score up.",
    ),
]
REPLY_TEXT = " ".join([SUMMARY, *(text for _, _, text in POINTS)])
REPLY_CITED = {
    "drying_score": 90.5,
    "s1_anom_db": -4.2,
    "rain_deficit_pct": 31,
    "canal_dist_m": 140.0,
}


def check(text=GOOD_TEXT, cited=None):
    check_explanation(
        text,
        GOOD_CITED if cited is None else cited,
        shown_values(FACTS, "riau"),
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


def reply(summary=SUMMARY, points=None, cited=None):
    cited = REPLY_CITED if cited is None else cited
    points = POINTS if points is None else points
    body = {
        "summary": summary,
        "points": [
            {"field": field, "effect": effect, "text": text}
            for field, effect, text in points
        ],
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

    def facts(self, cell_id):
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
            weights=WEIGHTS,
        )

    def explain(self, cell_id="riau-1-1"):
        return asyncio.run(self.explainer.explain(cell_id))

    def stored(self):
        return self.collection.get("riau-1-1").explanation


def test_a_valid_reply_is_returned_and_stored_on_the_ranked_cell():
    world = World([reply()])

    explanation = world.explain()

    assert explanation == RankExplanation(
        text=REPLY_TEXT,
        cited=REPLY_CITED,
        prompt_version=EXPLAIN_PROMPT_VERSION,
        summary=SUMMARY,
        points=tuple(
            ExplanationPoint(field=field, effect=effect, text=text)
            for field, effect, text in POINTS
        ),
    )
    assert world.stored() == explanation
    assert world.facts.calls == ["riau-1-1"]
    role, contents, config = world.model.calls[0]
    assert role == "reasoning"
    assert "<<<FACTS" in contents
    assert "90.5" in contents
    assert config.response_mime_type == "application/json"


def test_an_invalid_reply_is_retried_once_and_the_second_is_stored():
    world = World([reply(summary=SUMMARY + " It rained 12 mm."), reply()])

    explanation = world.explain()

    assert explanation.text == REPLY_TEXT
    assert len(world.model.calls) == 2


def test_two_invalid_replies_give_null_and_a_log_and_store_nothing(caplog):
    bad = reply(cited={**REPLY_CITED, "drying_score": 99.0})
    world = World([bad, bad])

    with caplog.at_level(logging.WARNING):
        explanation = world.explain()

    assert explanation is None
    assert world.stored() is None
    assert len(world.model.calls) == 2
    events = [r.fields["event"] for r in caplog.records if hasattr(r, "fields")]
    assert events.count("explain_rank_rejected") == 2
    assert "explain_rank_failed" in events


def test_a_summary_of_more_than_one_sentence_is_retried_then_null():
    long = reply(summary=SUMMARY + " One. Two.")
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
    bad = reply(summary="No numbers here at all.", points=[], cited={})
    world = World([bad, bad])

    world.explain()
    world.explain()

    assert len(world.model.calls) == 2


def test_a_cell_without_a_ranking_document_still_returns_the_explanation():
    world = World([reply()], ranked=False)

    assert world.explain().text == REPLY_TEXT


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
    assert EXPLAIN_PROMPT_VERSION == "explain-v4"


def test_an_integer_written_for_a_whole_value_passes():
    text = f"This area is {LEAD} (score 90.5 of 100) with a canal 140 m away."
    check(text=text, cited={"drying_score": 90.5, "canal_dist_m": 140.0})


@pytest.mark.parametrize(
    "text,bad",
    [
        (f"This area is {LEAD} (score 90 of 100).", "90"),
        (f"This area is {LEAD} (score 90.5 of 100), deficit 0.", "0"),
    ],
)
def test_a_rounded_or_stray_number_is_rejected(text, bad):
    facts = shown_values({**FACTS, "peat_class": 2}, "riau")
    with pytest.raises(ExplanationRejected, match="not cited"):
        check_explanation(text, {"drying_score": 90.5}, facts, "riau-1-1")


def test_digits_inside_field_names_are_not_numbers():
    text = (
        f"This area is {LEAD}, with s1_anom_db of -4.2 dB and rain_30d_mm of "
        "180 mm near Sentinel-1."
    )
    check_explanation(
        text,
        {"s1_anom_db": -4.2, "rain_30d_mm": 180},
        shown_values(FACTS, "riau"),
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

    assert world.explain().text == REPLY_TEXT
    assert len(world.model.calls) == 2


def test_a_model_error_is_not_remembered_for_the_week():
    world = World(
        [errors.APIError(503, {"error": {"code": 503, "message": "x"}}), reply()]
    )

    assert world.explain() is None
    assert world.explain().text == REPLY_TEXT


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

    assert explanation.text == REPLY_TEXT
    events = [r.fields["event"] for r in caplog.records if hasattr(r, "fields")]
    assert "explain_rank_store_failed" in events


def test_a_facts_failure_gives_null_not_an_exception():
    class Broken:
        def facts(self, cell_id):
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


def written_for(values, region="riau"):
    return {
        field: shown.written for field, shown in shown_values(values, region).items()
    }


def test_live_values_are_rounded_for_reading():
    assert written_for(LIVE) == {
        "drying_score": "96.8 of 100",
        "rank": "drying faster than any other area in Riau this week",
        "s1_anom_db": "-5.1 dB",
        "rain_30d_mm": "184 mm",
        "rain_deficit_pct": "31% less rain than normal",
        "canal_dist_m": "2.5 km",
        "peat_class": "1",
    }


@pytest.mark.parametrize(
    "fraction,written,number",
    [
        (0.3149, "31% less rain than normal", 31),
        (-0.0471, "5% more rain than normal", 5),
        (-0.004, "rain close to normal (0% difference)", 0),
    ],
)
def test_the_rain_deficit_sign_is_written_in_words(fraction, written, number):
    shown = shown_values({"rain_deficit_pct": fraction}, "riau")["rain_deficit_pct"]

    assert shown.written == written
    assert shown.number == number


@pytest.mark.parametrize(
    "rank,written",
    [
        (1, "drying faster than any other area in Kalteng this week"),
        (2, "the 2nd fastest-drying area in Kalteng this week"),
        (3, "the 3rd fastest-drying area in Kalteng this week"),
        (4, "the 4th fastest-drying area in Kalteng this week"),
        (11, "the 11th fastest-drying area in Kalteng this week"),
        (12, "the 12th fastest-drying area in Kalteng this week"),
        (13, "the 13th fastest-drying area in Kalteng this week"),
        (21, "the 21st fastest-drying area in Kalteng this week"),
        (102, "the 102nd fastest-drying area in Kalteng this week"),
    ],
)
def test_the_rank_is_written_as_a_plain_lead(rank, written):
    assert written_for({"rank": rank}, "kalteng")["rank"] == written


def test_a_text_without_the_rank_lead_is_rejected():
    text = GOOD_TEXT.replace(LEAD, "drying fast")

    with pytest.raises(ExplanationRejected, match="rank"):
        check(text=text)


def test_a_wrong_ordinal_for_the_rank_is_rejected():
    facts = shown_values({**FACTS, "rank": 3}, "riau")
    text = (
        "This area is the 3rd fastest-drying area in Riau this week, "
        "the 5th in the province."
    )

    with pytest.raises(ExplanationRejected, match="5"):
        check_explanation(text, {"rank": 3}, facts, "riau-1-1")


def test_an_ordinal_rank_is_read_as_its_number():
    facts = shown_values({**FACTS, "rank": 3}, "riau")
    text = "This area is the 3rd fastest-drying area in Riau this week."

    check_explanation(text, {"rank": 3}, facts, "riau-1-1")


def test_the_rain_wording_passes_when_copied():
    text = GOOD_TEXT + " It had 31% less rain than normal."

    check(text=text, cited={**GOOD_CITED, "rain_deficit_pct": 31})


def test_a_flipped_rain_wording_is_rejected():
    text = GOOD_TEXT + " It had 31% more rain than normal."

    with pytest.raises(ExplanationRejected, match="rain_deficit_pct"):
        check(text=text, cited={**GOOD_CITED, "rain_deficit_pct": 31})


def test_a_negative_rain_deficit_is_never_written_with_a_minus():
    text = GOOD_TEXT + " The rain deficit is -5%."
    facts = shown_values({**FACTS, "rain_deficit_pct": -0.05}, "riau")

    with pytest.raises(ExplanationRejected):
        check_explanation(
            text, {**GOOD_CITED, "rain_deficit_pct": 5}, facts, "riau-1-1"
        )


def test_the_score_scale_is_not_an_uncited_number():
    check(text=GOOD_TEXT)


def test_a_score_without_its_scale_is_rejected():
    text = GOOD_TEXT.replace("90.5 of 100", "90.5")

    with pytest.raises(ExplanationRejected, match="drying_score"):
        check(text=text)


def test_a_distance_under_a_kilometre_is_whole_metres():
    assert written_for({"canal_dist_m": 139.6})["canal_dist_m"] == "140 m"


def test_the_explain_call_thinks_at_the_low_level():
    from casework.rank_explanation import generation_config

    level = generation_config("instruction").thinking_config.thinking_level

    assert level == types.ThinkingLevel.LOW


def test_the_facts_block_names_each_fact_in_plain_words_with_its_written_form():
    block = render_facts("riau-1-1", shown_values(LIVE, "riau"), [])

    assert "radar dryness signal" in block
    assert "distance to the nearest canal" in block
    assert '"written": "2.5 km"' in block
    assert "2504" not in block
    assert "96.84" not in block


ROUNDED_TEXT = (
    f"This area is {LEAD} (score 96.8 of 100). The radar dryness "
    "signal is -5.1 dB and the nearest canal is 2.5 km away."
)
ROUNDED_CITED = {
    "drying_score": 96.8,
    "s1_anom_db": -5.1,
    "canal_dist_m": 2.5,
}


def test_a_correctly_rounded_text_passes_the_number_check():
    check_explanation(
        ROUNDED_TEXT, ROUNDED_CITED, shown_values(LIVE, "riau"), "riau-1-1"
    )


@pytest.mark.parametrize(
    "old,new",
    [("96.8", "96.9"), ("-5.1", "-5.2"), ("2.5 km", "3.5 km"), ("96.8", "96.84")],
)
def test_an_invented_or_unrounded_number_in_the_text_fails_the_number_check(old, new):
    text = ROUNDED_TEXT.replace(old, new)

    with pytest.raises(ExplanationRejected):
        check_explanation(text, ROUNDED_CITED, shown_values(LIVE, "riau"), "riau-1-1")


def test_a_cited_value_that_is_the_unrounded_figure_fails_the_number_check():
    cited = {**ROUNDED_CITED, "drying_score": 96.84027719188221}

    with pytest.raises(ExplanationRejected, match="drying_score"):
        check_explanation(ROUNDED_TEXT, cited, shown_values(LIVE, "riau"), "riau-1-1")


def test_the_stored_explanation_names_the_prompt_version():
    world = World([reply()])

    assert world.explain().prompt_version == EXPLAIN_PROMPT_VERSION


def test_a_distance_written_in_the_wrong_unit_is_rejected():
    text = ROUNDED_TEXT.replace("2.5 km", "2.5 m")

    with pytest.raises(ExplanationRejected, match="canal_dist_m"):
        check_explanation(text, ROUNDED_CITED, shown_values(LIVE, "riau"), "riau-1-1")


def test_a_deficit_written_as_millimetres_is_rejected():
    text = f"This area is {LEAD} and the rain deficit is 31 mm."
    cited = {"rain_deficit_pct": 31}

    with pytest.raises(ExplanationRejected, match="rain_deficit_pct"):
        check_explanation(text, cited, shown_values(LIVE, "riau"), "riau-1-1")


def test_a_small_negative_signal_is_not_written_as_negative_zero():
    assert written_for({"s1_anom_db": -0.04})["s1_anom_db"] == "0.0 dB"


def test_a_distance_that_rounds_to_a_kilometre_is_written_in_km():
    assert written_for({"canal_dist_m": 999.6})["canal_dist_m"] == "1.0 km"


def test_the_explainer_reads_facts_from_the_real_area_facts_tool():
    import inspect

    from bara_agent.tools.get_area_facts import GetAreaFacts
    from casework.rank_explanation import AreaFacts

    assert not inspect.iscoroutinefunction(GetAreaFacts.facts)
    assert callable(AreaFacts.facts)


def test_a_point_that_contradicts_the_data_is_retried():
    flipped = [(POINTS[0]), ("rain_deficit_pct", "lowers", POINTS[1][2]), POINTS[2]]
    world = World([reply(points=flipped), reply()])

    assert world.explain().text == REPLY_TEXT
    assert len(world.model.calls) == 2


def test_a_reply_that_skips_a_factor_is_retried():
    world = World([reply(points=POINTS[:2]), reply()])

    assert world.explain().text == REPLY_TEXT
    assert len(world.model.calls) == 2


def test_the_facts_carry_each_factor_effect_and_weight():
    world = World([reply()])
    world.explain()

    _, contents, config = world.model.calls[0]
    data = json.loads(contents.split("<<<FACTS")[1].split("FACTS>>>")[0])
    factors = [fact for fact in data["facts"] if "effect" in fact]
    assert [(f["field"], f["effect"], f["weight_pct"]) for f in factors] == [
        ("s1_anom_db", "raises", 45),
        ("rain_deficit_pct", "raises", 30),
        ("canal_dist_m", "raises", 15),
    ]
    assert "the radar dryness signal 45%, rain compared with normal 30%" in (
        config.system_instruction
    )
