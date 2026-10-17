from contracts import JoinRequest
from domain.join import (
    build_volunteer,
    claims_after_join,
    codes_match,
    with_role,
)

REQUEST = JoinRequest.model_validate(
    {
        "invite_code": "bara-secret",
        "name": "  Sari  ",
        "home": {"lat": 0.5, "lon": 101.4},
        "language": "id",
        "whatsapp": "+6281234567890",
    }
)


def test_codes_match_when_equal():
    assert codes_match("bara-secret", "bara-secret") is True


def test_codes_differ_by_one_character():
    assert codes_match("bara-secreT", "bara-secret") is False


def test_a_non_ascii_code_compares_without_raising():
    assert codes_match("bará-secret", "bara-secret") is False


def test_an_empty_expected_code_matches_nothing():
    assert codes_match("", "") is False


def test_join_claims_set_volunteer_on_a_user_with_no_role():
    assert claims_after_join({}) == {"role": "volunteer"}


def test_join_claims_keep_other_claims():
    assert claims_after_join({"locale": "id"}) == {"locale": "id", "role": "volunteer"}


def test_join_claims_never_downgrade_a_privileged_role():
    for role in ("ops", "brigade", "judge"):
        assert claims_after_join({"role": role}) == {"role": role}


def test_join_claims_keep_a_volunteer_equivalent_alias():
    assert claims_after_join({"role": "patrol"}) == {"role": "patrol"}


def test_with_role_replaces_the_role_and_keeps_the_rest():
    assert with_role({"role": "volunteer", "locale": "id"}, "ops") == {
        "role": "ops",
        "locale": "id",
    }


def test_with_role_does_not_mutate_its_input():
    original = {"role": "volunteer"}

    with_role(original, "ops")

    assert original == {"role": "volunteer"}


def test_build_volunteer_matches_the_live_shape():
    volunteer = build_volunteer("uid-1", REQUEST, "riau")

    assert volunteer.id == "uid-1"
    assert volunteer.name == "Sari"
    assert volunteer.role == "volunteer"
    assert volunteer.region == "riau"
    assert volunteer.home == REQUEST.home
    assert volunteer.language == "id"
    assert volunteer.channels.web is True
    assert volunteer.channels.whatsapp == "+6281234567890"
    assert volunteer.available is True
    assert volunteer.example is False


def test_build_volunteer_without_whatsapp_has_none():
    request = REQUEST.model_copy(update={"whatsapp": None})

    assert build_volunteer("u", request, "riau").channels.whatsapp is None
