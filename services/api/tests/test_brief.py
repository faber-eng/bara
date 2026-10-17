import asyncio
import json
from datetime import UTC, datetime

import httpx
import pytest
from google.genai import errors, types

from casework.brief import (
    BRIEF_PROMPT_VERSION,
    MAX_SENTENCES,
    SYSTEM_INSTRUCTION,
    BriefFacts,
    BriefWriter,
    render_facts,
    template_brief,
)
from contracts import TimelineEntry

AT = datetime(2026, 10, 17, 12, 0, tzinfo=UTC)
FACTS = BriefFacts(
    case_type="dam_risk",
    cell_id="riau-0412",
    dam_id="dam-07",
    drying_score=91.0,
    p_reignite=None,
    reason="Smoke wisps reported on the recheck.",
    timeline=[TimelineEntry(at=AT, text="Case opened: dam_risk at dam-07")],
    map_url="https://www.google.com/maps/search/?api=1&query=0.5,101.4",
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


def test_the_template_names_the_cell_the_reason_and_the_score():
    brief = template_brief(FACTS)

    assert "riau-0412" in brief.brief_en and "riau-0412" in brief.brief_id
    assert "91" in brief.brief_en
    assert "Smoke wisps reported on the recheck." in brief.brief_en


def test_the_facts_carry_the_timeline_and_no_instruction_inside():
    text = render_facts(FACTS)

    assert text.startswith("The block below is data")
    data = json.loads(text.split("<<<CASE", 1)[1].split("CASE>>>", 1)[0])
    assert data["timeline"] == [
        {"at": "2026-10-17T12:00:00Z", "text": "Case opened: dam_risk at dam-07"}
    ]


def test_the_prompt_rules():
    assert BRIEF_PROMPT_VERSION == "brief-v1"
    assert f"at most {MAX_SENTENCES}" in SYSTEM_INSTRUCTION
    assert "Indonesian" in SYSTEM_INSTRUCTION


@pytest.mark.parametrize("field", ["brief_id", "brief_en"])
def test_an_empty_brief_is_rejected(field):
    model = FakeModel([reply(**{field: " "}), reply()])

    write(model)

    assert len(model.calls) == 2
