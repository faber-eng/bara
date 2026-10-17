import asyncio
import json
from datetime import UTC, datetime

import httpx
from google.genai import types

from adapters.firestore_repos import BulletinRepository
from casework.bulletin import BulletinWriter
from contracts import Bulletin
from public_queries import NoRankings
from tests.fakes import InMemoryCollection, make_public_summary

NOW = datetime(2026, 10, 17, 4, 0, tzinfo=UTC)
TEXT_EN = "This week 12 cells are at high risk. 3 dams are broken."
TEXT_ID = "Minggu ini 12 sel berisiko tinggi. 3 bendungan rusak."
CITED = [
    {"field": "high_risk_cells", "value": 12},
    {"field": "dams_broken", "value": 3},
]


def reply(text_en=TEXT_EN, text_id=TEXT_ID, cited=None):
    body = {
        "text_en": text_en,
        "text_id": text_id,
        "cited": CITED if cited is None else cited,
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


class FakeSummaries:
    def __init__(self, summary=None, error=None):
        self.summary_value = summary or make_public_summary()
        self.error = error
        self.calls = []

    def summary(self, region, week, now):
        self.calls.append((region, week))
        if self.error:
            raise self.error
        return self.summary_value


class World:
    def __init__(self, replies, summaries=None):
        self.collection = InMemoryCollection(Bulletin)
        self.model = FakeModel(replies)
        self.summaries = summaries or FakeSummaries()
        self.writer = BulletinWriter(
            model=self.model,
            model_name="gemini-3.5-flash",
            summaries=self.summaries,
            bulletins=BulletinRepository(self.collection),
            now=lambda: NOW,
        )

    def write(self, region="riau", week=None):
        return asyncio.run(self.writer.write(region, week))

    def stored(self):
        return self.collection.get("riau_2026-W42")


def test_a_valid_reply_is_stored_as_gemini_with_model_and_prompt_version():
    world = World([reply()])

    bulletin = world.write()

    assert bulletin == world.stored()
    assert bulletin.source == "gemini"
    assert bulletin.model == "gemini-3.5-flash"
    assert bulletin.prompt_version == "bulletin-v1"
    assert bulletin.text_en == TEXT_EN
    assert [c.field for c in bulletin.cited] == ["high_risk_cells", "dams_broken"]
    role, contents, config = world.model.calls[0]
    assert role == "fast"
    assert "<<<SUMMARY" in contents
    assert "median_days_to_repair" in contents
    assert config.response_mime_type == "application/json"


def test_the_prompt_holds_only_the_public_summary_fields():
    world = World([reply()])

    world.write()

    contents = world.model.calls[0][1]
    assert "data_as_of" not in contents
    assert "cell_id" not in contents


def test_a_wrong_cited_value_is_retried_once_and_the_second_reply_is_stored():
    wrong = [{"field": "high_risk_cells", "value": 13}, CITED[1]]
    world = World([reply(cited=wrong), reply()])

    bulletin = world.write()

    assert bulletin.source == "gemini"
    assert len(world.model.calls) == 2


def test_two_rejected_replies_store_the_template():
    bad = reply(text_en=TEXT_EN + " 45 tasks were done.")
    world = World([bad, bad])

    bulletin = world.write()

    assert bulletin.source == "template"
    assert bulletin.model is None
    assert bulletin.prompt_version == "bulletin-template-v1"
    assert world.stored() == bulletin
    assert len(world.model.calls) == 2


def test_a_model_error_stores_the_template_without_a_retry():
    world = World([httpx.ConnectError("down")])

    bulletin = world.write()

    assert bulletin.source == "template"
    assert len(world.model.calls) == 1


def test_a_reply_with_too_many_sentences_is_rejected():
    long_en = "A 12. B 12. C 12. D 12. E 3."
    world = World([reply(text_en=long_en), reply(text_en=long_en)])

    assert world.write().source == "template"


def test_a_region_with_no_rankings_writes_nothing():
    world = World([], FakeSummaries(error=NoRankings("congo")))

    assert world.write("congo") is None
    assert world.model.calls == []


def test_a_zero_field_is_cited_and_passes():
    summary = make_public_summary(
        dams_broken=0, median_days_to_repair=None, tasks_on_time_pct=None
    )
    cited = [CITED[0], {"field": "dams_broken", "value": 0}]
    ok = reply(
        text_en="This week 12 cells are at high risk. 0 dams are broken.",
        text_id="Minggu ini 12 sel berisiko tinggi. 0 bendungan rusak.",
        cited=cited,
    )
    world = World([ok], FakeSummaries(summary))

    assert world.write().source == "gemini"


def test_a_slow_model_stores_the_template_inside_the_budget(monkeypatch):
    import casework.bulletin as module

    class Slow:
        async def generate(self, role, contents, config=None):
            await asyncio.sleep(5)

    monkeypatch.setattr(module, "GENERATE_BUDGET_SECONDS", 0.05)
    world = World([])
    world.writer._model = Slow()

    assert world.write().source == "template"
    assert world.stored().source == "template"


def test_an_unexpected_model_error_stores_the_template():
    world = World([ValueError("boom")])

    assert world.write().source == "template"


def test_the_stored_model_is_the_one_that_answered():
    answered = reply()
    answered.model_version = "gemini-2.5-flash"
    world = World([answered])

    assert world.write().model == "gemini-2.5-flash"
