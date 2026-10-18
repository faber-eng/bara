import pytest

from contracts import GeoPoint, Verdict
from domain.evidence import (
    UnsupportedMedia,
    case_status_after_verdict,
    final_verdict,
    location_ok,
    needs_human,
    object_name,
    readable_dam_state,
    stored_content_type,
    verdict_cache_key,
)


def verdict(**overrides) -> Verdict:
    fields = {
        "subject": "canal_dam",
        "dam_state": "intact",
        "smoke": "none",
        "hot_ground_signs": "none",
        "open_flame": "no",
        "transcript": None,
        "transcript_en": None,
        "reasons": ["water held behind the dam"],
        "confidence": 0.9,
        "needs_human": False,
    }
    return Verdict(**{**fields, **overrides})


@pytest.mark.parametrize(
    ("kind", "content_type", "suffix"),
    [
        ("photo", "image/jpeg", ".jpg"),
        ("photo", "image/png", ".png"),
        ("audio", "audio/webm", ".webm"),
        ("audio", "audio/ogg", ".ogg"),
        ("audio", "audio/wav", ".audio"),
        ("audio", "audio/x-m4a", ".audio"),
        ("audio", "audio/aac", ".audio"),
        ("audio", "audio/webm;codecs=opus", ".webm"),
        ("audio", "", ".webm"),
        ("audio", "video/webm", ".audio"),
        ("audio", "application/octet-stream", ".audio"),
        ("video", "video/mp4", ".mp4"),
        ("video", "video/quicktime", ".mov"),
    ],
)
def test_the_object_name_carries_the_case_the_id_and_the_extension(
    kind, content_type, suffix
):
    assert object_name(kind, content_type, "c1", "e1") == f"evidence/c1/e1{suffix}"


@pytest.mark.parametrize(
    ("kind", "content_type"),
    [
        ("photo", "audio/webm"),
        ("audio", "image/jpeg"),
        ("photo", "image/gif"),
        ("video", "audio/wav"),
    ],
)
def test_a_content_type_outside_the_kind_is_unsupported(kind, content_type):
    with pytest.raises(UnsupportedMedia):
        object_name(kind, content_type, "c1", "e1")


def test_low_confidence_needs_a_human():
    assert needs_human(verdict(confidence=0.69), threshold=0.7) is True
    assert needs_human(verdict(confidence=0.7), threshold=0.7) is False


def test_the_model_flag_needs_a_human_at_any_confidence():
    assert needs_human(verdict(needs_human=True, confidence=0.99), threshold=0.7)


def test_a_needs_human_verdict_sends_a_reviewing_case_to_human_review():
    assert case_status_after_verdict("reviewing", verdict(), True) == "human_review"


def test_a_verdict_with_nothing_to_act_on_resolves_pending_a_person():
    assert (
        case_status_after_verdict("reviewing", verdict(), False)
        == "resolved_pending_human"
    )


@pytest.mark.parametrize(
    "overrides",
    [
        {"dam_state": "broken"},
        {"dam_state": "damaged"},
        {"dam_state": "overtopped"},
        {"smoke": "wisps"},
        {"smoke": "plume"},
        {"open_flame": "yes"},
        {"hot_ground_signs": "clear"},
    ],
)
def test_a_verdict_that_needs_action_keeps_the_case_reviewing(overrides):
    assert case_status_after_verdict("reviewing", verdict(**overrides), False) == (
        "reviewing"
    )


@pytest.mark.parametrize("status", ["assigned", "resolved_pending_human", "closed"])
def test_a_case_not_in_review_keeps_its_status(status):
    assert case_status_after_verdict(status, verdict(), True) == status


def test_the_cache_key_changes_with_the_prompt_version():
    sha = "a" * 64

    first = verdict_cache_key(sha, "evidence-v1", "dam_check")

    assert len(first) == 64
    assert first == verdict_cache_key(sha, "evidence-v1", "dam_check")
    assert first != verdict_cache_key(sha, "evidence-v2", "dam_check")


@pytest.mark.parametrize(
    ("state", "readable"),
    [
        ("intact", "intact"),
        ("broken", "broken"),
        ("unknown", None),
        ("not_applicable", None),
    ],
)
def test_only_a_seen_dam_state_is_readable(state, readable):
    assert readable_dam_state(verdict(dam_state=state)) == readable


TARGET = GeoPoint(lat=0.5, lon=101.4)


def test_a_point_within_the_tolerance_is_ok():
    near = GeoPoint(lat=0.501, lon=101.4)

    assert location_ok(TARGET, near, tolerance_m=300) is True


def test_a_point_beyond_the_tolerance_is_not_ok():
    far = GeoPoint(lat=0.51, lon=101.4)

    assert location_ok(TARGET, far, tolerance_m=300) is False


def test_no_point_leaves_the_location_unchecked():
    assert location_ok(TARGET, None, tolerance_m=300) is None


def test_a_confident_verdict_at_the_place_stays_as_read():
    read = verdict(confidence=0.9)

    assert final_verdict(read, threshold=0.7, location=True, sample=False) == read


def test_a_low_confidence_verdict_needs_a_person():
    final = final_verdict(
        verdict(confidence=0.5), threshold=0.7, location=True, sample=False
    )

    assert final.needs_human is True


def test_a_location_mismatch_needs_a_person_and_says_why():
    final = final_verdict(
        verdict(confidence=0.9), threshold=0.7, location=False, sample=False
    )

    assert final.needs_human is True
    assert final.reasons[-1] == "location mismatch"


def test_a_location_mismatch_keeps_at_most_four_reasons():
    full = verdict(reasons=["a", "b", "c", "d"])

    final = final_verdict(full, threshold=0.7, location=False, sample=False)

    assert final.reasons == ["a", "b", "c", "location mismatch"]


def test_a_real_photo_without_a_location_needs_a_person():
    final = final_verdict(verdict(), threshold=0.7, location=None, sample=False)

    assert final.needs_human is True
    assert final.reasons[-1] == "no location"


def test_a_sample_photo_without_a_location_stays_as_read():
    read = verdict()

    assert final_verdict(read, threshold=0.7, location=None, sample=True) == read


def test_the_cache_key_depends_on_the_task_type():
    dam = verdict_cache_key("0" * 64, "evidence-v1", "dam_check")
    patrol = verdict_cache_key("0" * 64, "evidence-v1", "patrol_recheck")

    assert dam != patrol


@pytest.mark.parametrize(
    ("kind", "content_type", "expected"),
    [
        ("audio", "audio/webm;codecs=opus", "audio/webm"),
        ("audio", "", "audio/webm"),
        ("photo", "image/jpeg", "image/jpeg"),
    ],
)
def test_the_stored_content_type_drops_parameters_and_fills_an_empty_audio(
    kind, content_type, expected
):
    assert stored_content_type(kind, content_type) == expected
