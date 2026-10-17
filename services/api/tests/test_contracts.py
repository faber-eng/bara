from typing import get_args

import pytest
from pydantic import ValidationError

from contracts import (
    Event,
    EventAdapter,
    EventType,
    HotspotDetectedEvent,
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
