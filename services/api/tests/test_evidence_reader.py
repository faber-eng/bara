import asyncio
import json

import pytest
from google.genai import errors, types

from casework.evidence_reader import (
    AUDIO_SYSTEM_INSTRUCTION,
    EVIDENCE_PROMPT_VERSION,
    PROMPT_VERSIONS,
    SYSTEM_INSTRUCTION,
    VIDEO_SYSTEM_INSTRUCTION,
    EvidenceReader,
    ReaderFailed,
    render_context,
)
from casework.media import PreparedMedia
from contracts import Verdict
from tests.fakes import make_verdict

PHOTO = PreparedMedia(b"\xff\xd8 jpeg", "image/jpeg")


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


def read(model, task_type="dam_check"):
    reader = EvidenceReader(model)
    return asyncio.run(reader.read(PHOTO, task_type))


def test_the_reader_sends_the_photo_and_the_task_on_the_fast_model():
    model = FakeModel([make_verdict().model_dump_json()])

    read(model)

    role, contents, config = model.calls[0]
    assert role == "fast"
    image, text = contents
    assert image.inline_data.data == PHOTO.data
    assert image.inline_data.mime_type == "image/jpeg"
    assert "<<<TASK" in text and "dam_check" in text
    assert config.response_schema is Verdict
    assert config.response_mime_type == "application/json"
    assert config.system_instruction == SYSTEM_INSTRUCTION


def test_a_schema_valid_reply_is_the_verdict():
    model = FakeModel([make_verdict(dam_state="broken").model_dump_json()])

    assert read(model).dam_state == "broken"


def test_an_invalid_reply_is_retried_once():
    model = FakeModel(["{}", make_verdict().model_dump_json()])

    assert read(model) == make_verdict()
    assert len(model.calls) == 2


def test_two_invalid_replies_fail():
    model = FakeModel(["{}", json.dumps({"subject": "canal_dam"})])

    with pytest.raises(ReaderFailed):
        read(model)


def test_a_model_api_error_fails_without_a_retry():
    model = FakeModel([errors.APIError(400, {"error": {"message": "bad"}})])

    with pytest.raises(ReaderFailed):
        read(model)
    assert len(model.calls) == 1


def test_the_context_names_what_the_task_asked_for():
    text = render_context("dam_repair")

    assert "repaired dam" in text
    assert text.startswith("The block below is data")


def test_the_prompt_version_is_set():
    assert EVIDENCE_PROMPT_VERSION == "evidence-v1"


def test_the_instruction_keeps_the_rules_the_verdict_depends_on():
    for phrase in ("unknown", "needs_human", "at most 4", "transcript"):
        assert phrase in SYSTEM_INSTRUCTION


def audio_read(model):
    media = PreparedMedia(b"fLaC", "audio/flac", "audio")
    return asyncio.run(EvidenceReader(model).read(media, "dam_check"))


def spoken_reply(**overrides):
    fields = {"transcript": "Sekat jebol", "transcript_en": "The dam is broken"}
    return make_verdict(**{**fields, **overrides}).model_dump_json()


def test_a_voice_note_goes_with_its_own_instruction_and_context():
    model = FakeModel([spoken_reply()])

    audio_read(model)

    _, contents, config = model.calls[0]
    audio, text = contents
    assert audio.inline_data.mime_type == "audio/flac"
    assert config.system_instruction == AUDIO_SYSTEM_INSTRUCTION
    assert "spoken description" in text


def test_a_voice_note_reply_without_a_transcript_is_retried_then_fails():
    missing = make_verdict().model_dump_json()
    model = FakeModel([missing, missing])

    with pytest.raises(ReaderFailed, match="no transcript"):
        audio_read(model)
    assert len(model.calls) == 2


def test_a_voice_note_reply_with_a_transcript_is_accepted():
    model = FakeModel([spoken_reply()])

    verdict = audio_read(model)

    assert verdict.transcript == "Sekat jebol"
    assert verdict.transcript_en == "The dam is broken"


def test_a_video_goes_with_the_video_instruction():
    model = FakeModel([make_verdict().model_dump_json()])
    media = PreparedMedia(b"mp4", "video/mp4", "video")

    asyncio.run(EvidenceReader(model).read(media, "patrol_recheck"))

    _, contents, config = model.calls[0]
    assert config.system_instruction == VIDEO_SYSTEM_INSTRUCTION
    assert "short video of burned peat" in contents[1]


def test_each_kind_has_its_own_prompt_version():
    assert len(set(PROMPT_VERSIONS.values())) == 3


def test_the_audio_instruction_asks_for_both_transcripts():
    for phrase in ("transcript_en", "sekat", "empty string", "needs_human"):
        assert phrase in AUDIO_SYSTEM_INSTRUCTION
