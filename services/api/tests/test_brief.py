import asyncio
import json
from dataclasses import replace

import httpx
import pytest
from google.genai import errors, types

from casework.brief import (
    BRIEF_PROMPT_VERSION,
    ENGLISH_MARKERS,
    MAX_SENTENCES,
    SYSTEM_INSTRUCTION,
    BriefWriter,
    english_leaks,
    render_facts,
    template_brief,
)
from casework.messenger import sentence_count
from domain.brief import BriefFacts
from domain.escalation import FieldSigns, OverdueTask

FACTS = BriefFacts(
    case_type="dam_risk",
    cell_id="riau-0412",
    dam_id="dam-07",
    drying_score=96.67,
    p_reignite=None,
    smoke_seen_before=False,
    field_signs=None,
    overdue_task=OverdueTask(task_type="dam_check", attempt=1),
    photo_count=0,
)
EVERY_GROUND = BriefFacts(
    case_type="reignition",
    cell_id="riau-180-77",
    dam_id=None,
    drying_score=80.0,
    p_reignite=0.62,
    smoke_seen_before=True,
    field_signs=FieldSigns(smoke="plume", open_flame=True, hot_ground=True),
    overdue_task=OverdueTask(task_type="patrol_recheck", attempt=2),
    photo_count=2,
)


class FakeModel:
    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []

    async def generate(self, role, contents, config=None):
        self.calls.append((role, contents, config))
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return types.GenerateContentResponse(
            candidates=[
                types.Candidate(
                    content=types.Content(role="model", parts=[types.Part(text=reply)])
                )
            ]
        )


def reply(
    brief_id="Asap tipis terlihat di riau-0412.", brief_en="Smoke seen in riau-0412."
):
    return json.dumps({"brief_id": brief_id, "brief_en": brief_en})


def write(model):
    return asyncio.run(BriefWriter(model).write(FACTS))


def test_the_brief_is_one_reasoning_call_with_the_facts_fenced():
    model = FakeModel([reply()])

    brief = write(model)

    role, contents, config = model.calls[0]
    assert role == "reasoning"
    assert "<<<CASE" in contents and "riau-0412" in contents
    assert config.system_instruction == SYSTEM_INSTRUCTION
    assert config.response_mime_type == "application/json"
    assert brief.brief_id == "Asap tipis terlihat di riau-0412."
    assert brief.brief_en == "Smoke seen in riau-0412."
    assert brief.source == "gemini"


def test_a_long_brief_is_retried_once():
    long_text = "One. Two. Three. Four."
    model = FakeModel([reply(brief_en=long_text), reply()])

    assert write(model).brief_en == "Smoke seen in riau-0412."
    assert len(model.calls) == 2


def test_two_bad_replies_fall_back_to_the_template():
    model = FakeModel(["{}", "not json"])

    brief = write(model)

    assert brief.source == "template"
    assert brief == template_brief(FACTS)


def test_a_model_error_falls_back_to_the_template_without_a_retry():
    model = FakeModel([errors.APIError(503, {"error": {"message": "down"}})])

    brief = write(model)

    assert brief.source == "template"
    assert len(model.calls) == 1


def test_a_model_timeout_falls_back_to_the_template():
    model = FakeModel([httpx.ReadTimeout("slow")])

    brief = write(model)

    assert brief.source == "template"
    assert len(model.calls) == 1


def test_the_template_states_the_facts_in_plain_words():
    brief = template_brief(FACTS)

    assert brief.brief_id == (
        "Risiko bendungan di sel riau-0412, bendungan dam-07. Regu dibutuhkan "
        "sekarang karena skor kekeringan 96,7, di atas batas 80; tugas "
        "pemeriksaan bendungan lewat tenggat; belum ada foto dari lapangan. "
        "Kirim regu untuk memeriksa dan mengamankan bendungan."
    )
    assert brief.brief_en == (
        "Dam risk in cell riau-0412, dam dam-07. A crew is needed now because "
        "drying score 96.7, above the limit of 80; the dam check task is past "
        "its deadline; no field photo yet. Send a crew to check and secure the dam."
    )


def test_the_template_names_every_ground():
    brief = template_brief(EVERY_GROUND)

    assert "skor kekeringan 80, tepat di batas 80" in brief.brief_id
    assert "peluang api menyala kembali 62%, di atas batas 50%" in brief.brief_id
    assert "asap pernah terlihat di sel ini" in brief.brief_id
    assert "tugas patroli ulang lewat tenggat setelah 2 orang diminta" in (
        brief.brief_id
    )
    assert (
        "foto dari lapangan menunjukkan asap tebal dan api terbuka dan tanda "
        "tanah panas" in brief.brief_id
    )
    assert "Kirim regu untuk memeriksa lokasi dan memadamkan api." in brief.brief_id
    assert "re-ignition chance 62%, above the limit of 50%" in brief.brief_en


def test_a_score_under_the_limit_carries_no_rule():
    facts = replace(FACTS, drying_score=61.04)

    assert "skor kekeringan 61; tugas" in template_brief(facts).brief_id


@pytest.mark.parametrize("facts", [FACTS, EVERY_GROUND])
def test_the_indonesian_template_has_no_english_and_no_field_names(facts):
    brief = template_brief(facts)

    assert english_leaks(brief.brief_id) == []
    assert sentence_count(brief.brief_id) <= MAX_SENTENCES
    assert sentence_count(brief.brief_en) <= MAX_SENTENCES


@pytest.mark.parametrize("facts", [FACTS, EVERY_GROUND])
def test_the_indonesian_facts_have_no_english_and_no_field_names(facts):
    data = json.loads(render_facts(facts).split("<<<CASE", 1)[1].split("CASE>>>")[0])

    assert english_leaks(json.dumps(data["id"], ensure_ascii=False)) == []


def test_the_facts_hold_both_languages_and_no_instruction_inside():
    text = render_facts(FACTS)

    assert text.startswith("The block below is data")
    data = json.loads(text.split("<<<CASE", 1)[1].split("CASE>>>", 1)[0])
    assert data["id"]["temuan"] == "Risiko bendungan di sel riau-0412, bendungan dam-07"
    assert data["en"]["reasons"][0] == "drying score 96.7, above the limit of 80"
    assert "reason" not in data and "timeline" not in data


@pytest.mark.parametrize(
    "mixed",
    [
        "Tim dibutuhkan sekarang karena the case risk is 80 or more.",
        "Tim dibutuhkan karena drying_score 96,7.",
    ],
)
def test_an_indonesian_brief_with_english_is_retried(mixed):
    model = FakeModel([reply(brief_id=mixed), reply()])

    assert write(model).brief_id == "Asap tipis terlihat di riau-0412."
    assert len(model.calls) == 2


def test_english_leaks_finds_snake_case_and_the_marker_words():
    leaks = english_leaks("Tim dibutuhkan karena the Case drying_score tinggi.")

    assert leaks == ["drying_score", "the", "Case"]


def test_the_prompt_rules():
    assert BRIEF_PROMPT_VERSION == "brief-v2"
    assert f"at most {MAX_SENTENCES}" in SYSTEM_INSTRUCTION
    assert "Indonesian" in SYSTEM_INSTRUCTION
    assert ENGLISH_MARKERS == ("the", "is", "or", "because", "case")


@pytest.mark.parametrize("field", ["brief_id", "brief_en"])
def test_an_empty_brief_is_rejected(field):
    model = FakeModel([reply(**{field: " "}), reply()])

    write(model)

    assert len(model.calls) == 2


AREA_FACTS = replace(FACTS, dam_id=None, overdue_task=None)


def test_a_dam_risk_case_without_a_dam_says_area_not_dam():
    brief = template_brief(AREA_FACTS)

    assert brief.brief_en == (
        "Area at risk in cell riau-0412. A crew is needed now because drying "
        "score 96.7, above the limit of 80; no field photo yet. "
        "Send a crew to check the area."
    )
    assert "dam" not in brief.brief_en.lower()
    assert "bendungan" not in brief.brief_id
    assert brief.brief_id.startswith("Lokasi berisiko di sel riau-0412.")


def test_the_facts_sent_to_the_model_say_area_for_a_case_without_a_dam():
    facts = render_facts(AREA_FACTS)

    assert "dam" not in facts.lower()
    assert "bendungan" not in facts
