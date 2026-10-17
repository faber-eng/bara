import logging

import pytest

from adapters.identity import IdentityUnavailable
from adapters.secrets import SecretUnavailable
from tests.fakes import FakeClaimsAdmin, FakeSecretReader
from tests.join_support import (
    ANON_TOKEN,
    BODY,
    CODE,
    GOOGLE_TOKEN,
    bearer,
    make_join_app,
    make_limiter,
)


def join(client, token=GOOGLE_TOKEN, body=BODY, headers=None):
    return client.post(
        "/api/join", json=body, headers={**bearer(token), **(headers or {})}
    )


def test_a_google_user_with_the_right_code_joins(settings):
    client, volunteers = make_join_app(settings)

    response = join(client)

    assert response.status_code == 200
    assert response.json() == {"volunteer_id": "u-google", "created": True}
    stored = volunteers.get("u-google")
    assert stored.example is False
    assert stored.role == "volunteer"
    assert stored.available is True
    assert stored.region == "riau"
    assert stored.name == "Sari"
    assert stored.channels.whatsapp == "+6281234567890"


def test_a_join_sets_the_volunteer_claim(settings):
    admin = FakeClaimsAdmin({"u-google": {"locale": "id"}})
    client, _ = make_join_app(settings, admin=admin)

    join(client)

    assert admin.claims_by_uid["u-google"] == {"locale": "id", "role": "volunteer"}


def test_a_wrong_code_is_403_and_creates_nothing(settings):
    admin = FakeClaimsAdmin()
    client, volunteers = make_join_app(settings, admin=admin)

    response = join(client, body={**BODY, "invite_code": "nope"})

    assert response.status_code == 403
    assert response.json() == {"detail": "invalid_invite_code"}
    assert volunteers.get("u-google") is None
    assert admin.writes == []


def test_an_anonymous_token_is_403_before_the_secret_is_read(settings):
    secrets = FakeSecretReader(CODE)
    client, volunteers = make_join_app(settings, secrets=secrets)

    response = join(client, token=ANON_TOKEN)

    assert response.status_code == 403
    assert response.json() == {"detail": "anonymous_not_allowed"}
    assert secrets.reads == 0
    assert volunteers.get("u-anon") is None


def test_a_token_with_no_provider_is_403(settings):
    client, _ = make_join_app(settings)

    response = join(client, token="token-no-provider")

    assert response.status_code == 403
    assert response.json() == {"detail": "anonymous_not_allowed"}


def test_no_token_is_401(settings):
    client, _ = make_join_app(settings)

    assert client.post("/api/join", json=BODY).status_code == 401


def test_a_bad_token_is_401(settings):
    client, _ = make_join_app(settings)

    assert join(client, token="garbage").status_code == 401


@pytest.mark.parametrize(
    "change",
    [
        {"name": ""},
        {"name": "   "},
        {"language": "xx"},
        {"home": {"lat": 91, "lon": 0}},
        {"whatsapp": "081234"},
        {"invite_code": ""},
        {"extra": 1},
    ],
)
def test_an_invalid_body_is_422_and_reads_no_secret(settings, change):
    secrets = FakeSecretReader(CODE)
    client, volunteers = make_join_app(settings, secrets=secrets)

    response = join(client, body={**BODY, **change})

    assert response.status_code == 422
    assert secrets.reads == 0
    assert volunteers.get("u-google") is None


def test_a_missing_whatsapp_field_is_422(settings):
    client, _ = make_join_app(settings)
    body = {key: value for key, value in BODY.items() if key != "whatsapp"}

    assert join(client, body=body).status_code == 422


def test_a_null_whatsapp_joins_without_a_number(settings):
    client, volunteers = make_join_app(settings)

    response = join(client, body={**BODY, "whatsapp": None})

    assert response.status_code == 200
    assert volunteers.get("u-google").channels.whatsapp is None


def test_a_repeat_join_is_200_created_false_and_keeps_the_profile(settings):
    client, volunteers = make_join_app(settings)
    join(client)

    response = join(client, body={**BODY, "name": "Someone Else"})

    assert response.status_code == 200
    assert response.json() == {"volunteer_id": "u-google", "created": False}
    assert volunteers.get("u-google").name == "Sari"


def test_a_repeat_join_reasserts_a_missing_claim(settings):
    admin = FakeClaimsAdmin()
    client, _ = make_join_app(settings, admin=admin)
    join(client)
    admin.claims_by_uid["u-google"] = {}

    join(client)

    assert admin.claims_by_uid["u-google"] == {"role": "volunteer"}


def test_an_ops_claim_cannot_join_and_nothing_is_written(settings):
    admin = FakeClaimsAdmin({"u-google": {"role": "ops"}})
    client, collection = make_join_app(settings, admin=admin)

    response = join(client)

    assert response.status_code == 409
    assert response.json() == {"detail": "already_has_role"}
    assert admin.claims_by_uid["u-google"] == {"role": "ops"}
    assert admin.writes == []
    assert collection.get("u-google") is None


def test_brigade_and_judge_claims_cannot_join_either(settings):
    for role in ("brigade", "judge"):
        admin = FakeClaimsAdmin({"u-google": {"role": role}})
        client, _ = make_join_app(settings, admin=admin)

        assert join(client).status_code == 409


def test_a_wrong_code_is_still_403_for_a_staff_claim(settings):
    admin = FakeClaimsAdmin({"u-google": {"role": "ops"}})
    client, _ = make_join_app(settings, admin=admin)

    response = join(client, body={**BODY, "invite_code": "nope"})

    assert response.status_code == 403


def test_a_volunteer_claim_repeats_the_join_as_200(settings):
    admin = FakeClaimsAdmin({"u-google": {"role": "volunteer"}})
    client, _ = make_join_app(settings, admin=admin)

    assert join(client).status_code == 200
    assert join(client).status_code == 200


def test_a_claim_failure_is_502_and_a_retry_works(settings):
    admin = FakeClaimsAdmin()
    client, volunteers = make_join_app(settings, admin=admin)
    admin.fail_with = IdentityUnavailable("down")

    first = join(client)

    assert first.status_code == 502
    assert volunteers.get("u-google") is None
    admin.fail_with = None

    second = join(client)

    assert second.status_code == 200
    assert second.json()["created"] is True
    assert admin.claims_by_uid["u-google"] == {"role": "volunteer"}


def test_a_claim_write_failure_after_the_document_is_502_and_a_retry_works(settings):
    admin = FakeClaimsAdmin()
    client, volunteers = make_join_app(settings, admin=admin)
    admin.fail_set_with = IdentityUnavailable("down")

    first = join(client)

    assert first.status_code == 502
    assert volunteers.get("u-google") is not None
    admin.fail_set_with = None

    second = join(client)

    assert second.status_code == 200
    assert second.json()["created"] is False
    assert admin.claims_by_uid["u-google"] == {"role": "volunteer"}


def test_a_secret_failure_is_503_and_creates_nothing(settings):
    secrets = FakeSecretReader(SecretUnavailable("down"))
    client, volunteers = make_join_app(settings, secrets=secrets)

    response = join(client)

    assert response.status_code == 503
    assert volunteers.get("u-google") is None


class Ticker:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


def wrong(client, token=GOOGLE_TOKEN):
    return join(client, token=token, body={**BODY, "invite_code": "nope"})


def test_the_sixth_attempt_is_429_with_retry_after(settings):
    ticker = Ticker()
    client, _ = make_join_app(settings, limiter=make_limiter(ticker))
    for _ in range(5):
        assert wrong(client).status_code == 403

    response = join(client)

    assert response.status_code == 429
    assert response.headers["Retry-After"] == "900"


def test_another_user_is_not_limited(settings):
    client, _ = make_join_app(settings, limiter=make_limiter(Ticker()))
    for _ in range(5):
        wrong(client)

    assert join(client, token="token-google-2").status_code == 200


def test_the_limit_lifts_after_the_window(settings):
    ticker = Ticker()
    client, _ = make_join_app(settings, limiter=make_limiter(ticker))
    for _ in range(5):
        wrong(client)
    ticker.now += 900

    assert join(client).status_code == 200


def test_a_success_clears_the_failures(settings):
    client, _ = make_join_app(settings, limiter=make_limiter(Ticker()))
    for _ in range(4):
        wrong(client)
    assert join(client).status_code == 200

    for _ in range(4):
        assert wrong(client).status_code == 403


def test_a_blocked_attempt_does_not_read_the_secret(settings):
    secrets = FakeSecretReader(CODE)
    client, _ = make_join_app(settings, secrets=secrets, limiter=make_limiter(Ticker()))
    for _ in range(5):
        wrong(client)
    reads = secrets.reads

    join(client)

    assert secrets.reads == reads


def test_nothing_sensitive_is_logged(settings, caplog):
    client, _ = make_join_app(settings)

    with caplog.at_level(logging.DEBUG):
        join(client, body={**BODY, "invite_code": "guess-code-123"})
        join(client)

    for secret in ("guess-code-123", CODE, "Sari", "+6281234567890", GOOGLE_TOKEN):
        assert secret not in caplog.text


def test_the_judge_header_does_not_let_an_anonymous_user_join(settings):
    client, _ = make_join_app(settings, judge=True)

    response = join(client, token=ANON_TOKEN, headers={"X-Bara-Role": "volunteer"})

    assert response.status_code == 403


def test_the_judge_header_does_not_change_a_real_join(settings):
    admin = FakeClaimsAdmin()
    client, _ = make_join_app(settings, judge=True, admin=admin)

    response = join(client, headers={"X-Bara-Role": "ops"})

    assert response.status_code == 200
    assert admin.claims_by_uid["u-google"] == {"role": "volunteer"}
