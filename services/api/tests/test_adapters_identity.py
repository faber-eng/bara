from types import SimpleNamespace

import pytest
from firebase_admin import auth as firebase_auth
from firebase_admin.exceptions import FirebaseError
from google.auth.exceptions import DefaultCredentialsError

from adapters.identity import (
    FirebaseClaimsAdmin,
    IdentityUnavailable,
    UserNotFound,
    grant_role,
)
from tests.fakes import FakeClaimsAdmin


def test_get_claims_reads_the_user_custom_claims(monkeypatch):
    monkeypatch.setattr(
        firebase_auth,
        "get_user",
        lambda uid, app=None: SimpleNamespace(custom_claims={"role": "ops"}),
    )

    assert FirebaseClaimsAdmin().get_claims("u1") == {"role": "ops"}


def test_get_claims_of_a_user_with_none_is_empty(monkeypatch):
    monkeypatch.setattr(
        firebase_auth,
        "get_user",
        lambda uid, app=None: SimpleNamespace(custom_claims=None),
    )

    assert FirebaseClaimsAdmin().get_claims("u1") == {}


def test_set_claims_writes_the_whole_dict(monkeypatch):
    calls = []
    monkeypatch.setattr(
        firebase_auth,
        "set_custom_user_claims",
        lambda uid, claims, app=None: calls.append((uid, claims)),
    )

    FirebaseClaimsAdmin().set_claims("u1", {"role": "ops"})

    assert calls == [("u1", {"role": "ops"})]


def test_uid_for_email_returns_the_uid(monkeypatch):
    monkeypatch.setattr(
        firebase_auth,
        "get_user_by_email",
        lambda email, app=None: SimpleNamespace(uid="u1"),
    )

    assert FirebaseClaimsAdmin().uid_for_email("a@b.test") == "u1"


def test_uid_for_an_unknown_email_is_none(monkeypatch):
    def missing(email, app=None):
        raise firebase_auth.UserNotFoundError("none", cause=None)

    monkeypatch.setattr(firebase_auth, "get_user_by_email", missing)

    assert FirebaseClaimsAdmin().uid_for_email("a@b.test") is None


@pytest.mark.parametrize(
    "error", [FirebaseError("permission-denied", "no"), DefaultCredentialsError("none")]
)
def test_firebase_and_credential_errors_become_identity_unavailable(monkeypatch, error):
    def fail(email, app=None):
        raise error

    monkeypatch.setattr(firebase_auth, "get_user_by_email", fail)

    with pytest.raises(IdentityUnavailable):
        FirebaseClaimsAdmin().uid_for_email("a@b.test")


def make_admin():
    return FakeClaimsAdmin(
        {"u1": {"role": "volunteer", "locale": "id"}}, {"a@b.test": "u1"}
    )


def test_grant_role_merges_the_role_into_existing_claims():
    admin = make_admin()

    result = grant_role(admin, "a@b.test", "ops", dry_run=False)

    assert (result.uid, result.role) == ("u1", "ops")
    assert admin.claims_by_uid["u1"] == {"role": "ops", "locale": "id"}


def test_grant_role_dry_run_writes_nothing_but_reports_the_same_result():
    admin = make_admin()

    result = grant_role(admin, "a@b.test", "brigade", dry_run=True)

    assert (result.uid, result.role) == ("u1", "brigade")
    assert admin.writes == []


def test_grant_role_for_an_unknown_email_raises_user_not_found():
    with pytest.raises(UserNotFound):
        grant_role(make_admin(), "who@b.test", "ops", dry_run=False)
