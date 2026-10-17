from pathlib import Path
from typing import get_args

import pytest
import yaml
from pydantic import ValidationError

from contracts import (
    ClockState,
    Event,
    EventAdapter,
    EventType,
    HotspotDetectedEvent,
    JoinRequest,
    JoinResponse,
    Language,
    SampleItem,
    SampleKind,
    Verdict,
)

VALID_VERDICT = {
    "subject": "canal_dam",
    "dam_state": "broken",
    "smoke": "none",
    "hot_ground_signs": "none",
    "open_flame": "no",
    "transcript": "Sekatnya jebol di sisi kiri, air kanal sudah turun",
    "transcript_en": "The dam is broken on the left side, the canal water has dropped",
    "reasons": ["gap in the dam wall", "water level below the crest"],
    "confidence": 0.9,
    "needs_human": False,
}

HOTSPOT_ENVELOPE = {
    "type": "hotspot.detected",
    "id": "msg-0001",
    "occurred_at": "2026-07-30T06:00:00+07:00",
    "region": "riau",
    "example": False,
    "payload": {
        "cell_id": "riau-0412",
        "lat": 0.412,
        "lon": 102.15,
        "frp": 12.5,
        "confidence": 80,
        "source": "VIIRS_SNPP_NRT",
    },
}


def test_valid_verdict_parses():
    verdict = Verdict.model_validate(VALID_VERDICT)

    assert verdict.dam_state == "broken"
    assert verdict.confidence == 0.9


def test_verdict_rejects_five_reasons():
    with pytest.raises(ValidationError):
        Verdict.model_validate({**VALID_VERDICT, "reasons": ["a", "b", "c", "d", "e"]})


def test_verdict_rejects_confidence_above_one():
    with pytest.raises(ValidationError):
        Verdict.model_validate({**VALID_VERDICT, "confidence": 1.5})


def test_verdict_rejects_unknown_dam_state():
    with pytest.raises(ValidationError):
        Verdict.model_validate({**VALID_VERDICT, "dam_state": "gone"})


def test_verdict_rejects_extra_field():
    with pytest.raises(ValidationError):
        Verdict.model_validate({**VALID_VERDICT, "notes": "extra"})


def test_verdict_rejects_missing_field():
    with pytest.raises(ValidationError):
        Verdict.model_validate(
            {k: v for k, v in VALID_VERDICT.items() if k != "needs_human"}
        )


def test_hotspot_envelope_parses_to_its_class():
    event = EventAdapter.validate_python(HOTSPOT_ENVELOPE)

    assert isinstance(event, HotspotDetectedEvent)
    assert event.payload.cell_id == "riau-0412"


def test_envelope_with_mismatched_type_and_payload_fails():
    with pytest.raises(ValidationError):
        EventAdapter.validate_python({**HOTSPOT_ENVELOPE, "type": "task.overdue"})


def test_envelope_with_unknown_type_fails():
    with pytest.raises(ValidationError):
        EventAdapter.validate_python({**HOTSPOT_ENVELOPE, "type": "hotspot.gone"})


def test_envelope_rejects_naive_occurred_at():
    with pytest.raises(ValidationError):
        EventAdapter.validate_python(
            {**HOTSPOT_ENVELOPE, "occurred_at": "2026-07-30T06:00:00"}
        )


def test_every_event_type_has_one_envelope_class():
    envelope_types = {
        get_args(member.model_fields["type"].annotation)[0]
        for member in get_args(get_args(Event)[0])
    }

    assert envelope_types == set(get_args(EventType))


def test_task_rejects_a_naive_deadline():
    from datetime import datetime

    from tests.fakes import make_task

    with pytest.raises(ValidationError):
        make_task(deadline_at=datetime(2026, 10, 20, 12, 0))


VALID_JOIN = {
    "invite_code": "bara-2026",
    "name": "Ari Wijaya",
    "home": {"lat": 0.41, "lon": 102.15},
    "language": "id",
    "whatsapp": "+6281234567890",
}


def test_language_equals_the_supported_languages_in_app_yaml():
    app_yaml = Path(__file__).resolve().parents[3] / "config" / "app.yaml"
    supported = yaml.safe_load(app_yaml.read_text())["languages"]["supported"]

    assert list(get_args(Language)) == supported


def test_valid_join_request_parses():
    request = JoinRequest.model_validate(VALID_JOIN)

    assert request.language == "id"
    assert request.whatsapp == "+6281234567890"


def test_join_request_allows_a_missing_whatsapp_as_null():
    request = JoinRequest.model_validate({**VALID_JOIN, "whatsapp": None})

    assert request.whatsapp is None


def test_join_request_strips_the_name():
    request = JoinRequest.model_validate({**VALID_JOIN, "name": "  Ari Wijaya  "})

    assert request.name == "Ari Wijaya"


@pytest.mark.parametrize("name", ["", "   ", "x" * 81])
def test_join_request_rejects_a_bad_name(name):
    with pytest.raises(ValidationError):
        JoinRequest.model_validate({**VALID_JOIN, "name": name})


@pytest.mark.parametrize("code", ["", "x" * 129])
def test_join_request_rejects_a_bad_invite_code(code):
    with pytest.raises(ValidationError):
        JoinRequest.model_validate({**VALID_JOIN, "invite_code": code})


@pytest.mark.parametrize(
    "number",
    [
        "081234567890",
        "+0123456789",
        "+1234567",
        "+1234567890123456",
        "+62 812 3456",
        "+62abc4567",
    ],
)
def test_join_request_rejects_a_bad_whatsapp_number(number):
    with pytest.raises(ValidationError):
        JoinRequest.model_validate({**VALID_JOIN, "whatsapp": number})


@pytest.mark.parametrize("number", ["+12345678", "+123456789012345"])
def test_join_request_accepts_the_whatsapp_length_bounds(number):
    JoinRequest.model_validate({**VALID_JOIN, "whatsapp": number})


def test_join_request_rejects_an_unsupported_language():
    with pytest.raises(ValidationError):
        JoinRequest.model_validate({**VALID_JOIN, "language": "de"})


def test_join_request_rejects_an_out_of_range_home():
    with pytest.raises(ValidationError):
        JoinRequest.model_validate({**VALID_JOIN, "home": {"lat": 91, "lon": 0}})


def test_join_request_rejects_extra_and_missing_keys():
    with pytest.raises(ValidationError):
        JoinRequest.model_validate({**VALID_JOIN, "role": "ops"})
    with pytest.raises(ValidationError):
        JoinRequest.model_validate(
            {k: v for k, v in VALID_JOIN.items() if k != "whatsapp"}
        )


def test_join_response_rejects_extra_key():
    JoinResponse.model_validate({"volunteer_id": "uid-1", "created": True})
    with pytest.raises(ValidationError):
        JoinResponse.model_validate(
            {"volunteer_id": "uid-1", "created": True, "role": "volunteer"}
        )


def test_clock_state_rejects_a_naive_now():
    with pytest.raises(ValidationError):
        ClockState.model_validate(
            {"now": "2026-07-20T08:00:00", "offset_seconds": 0, "judge_mode": True}
        )


def test_clock_state_rejects_extra_key():
    with pytest.raises(ValidationError):
        ClockState.model_validate(
            {
                "now": "2026-07-20T08:00:00+07:00",
                "offset_seconds": 0,
                "judge_mode": True,
                "tz": "Asia/Jakarta",
            }
        )


def test_sample_kind_is_photo_voice_area():
    assert get_args(SampleKind) == ("photo", "voice", "area")


def test_sample_item_rejects_an_unknown_kind():
    item = {
        "id": "s1",
        "kind": "photo",
        "label": "Dam",
        "credit": "Wikimedia",
        "url": "/s1",
    }
    SampleItem.model_validate(item)
    with pytest.raises(ValidationError):
        SampleItem.model_validate({**item, "kind": "video"})


def test_envelope_requires_the_example_flag():
    without = {k: v for k, v in HOTSPOT_ENVELOPE.items() if k != "example"}

    with pytest.raises(ValidationError):
        EventAdapter.validate_python(without)
