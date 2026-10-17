from dataclasses import dataclass
from typing import Protocol

from firebase_admin import auth as firebase_auth
from firebase_admin.exceptions import FirebaseError
from google.auth.exceptions import GoogleAuthError

from auth import Role
from domain.join import with_role


class IdentityUnavailable(Exception):
    pass


class UserNotFound(Exception):
    pass


class ClaimsAdmin(Protocol):
    def get_claims(self, uid: str) -> dict[str, object]: ...

    def set_claims(self, uid: str, claims: dict[str, object]) -> None: ...

    def uid_for_email(self, email: str) -> str | None: ...


class FirebaseClaimsAdmin:
    def __init__(self, app=None):
        self._app = app

    def get_claims(self, uid: str) -> dict[str, object]:
        try:
            user = firebase_auth.get_user(uid, app=self._app)
        except (FirebaseError, GoogleAuthError) as error:
            raise IdentityUnavailable(describe(error)) from error
        return dict(user.custom_claims or {})

    def set_claims(self, uid: str, claims: dict[str, object]) -> None:
        try:
            firebase_auth.set_custom_user_claims(uid, claims, app=self._app)
        except (FirebaseError, GoogleAuthError) as error:
            raise IdentityUnavailable(describe(error)) from error

    def uid_for_email(self, email: str) -> str | None:
        try:
            return firebase_auth.get_user_by_email(email, app=self._app).uid
        except firebase_auth.UserNotFoundError:
            return None
        except (FirebaseError, GoogleAuthError) as error:
            raise IdentityUnavailable(describe(error)) from error


def describe(error: Exception) -> str:
    return f"{type(error).__name__}: {error}"


@dataclass(frozen=True)
class GrantResult:
    uid: str
    role: Role


def grant_role(
    admin: ClaimsAdmin, email: str, role: Role, dry_run: bool
) -> GrantResult:
    uid = admin.uid_for_email(email)
    if uid is None:
        raise UserNotFound(email)
    merged = with_role(admin.get_claims(uid), role)
    if not dry_run:
        admin.set_claims(uid, merged)
    return GrantResult(uid, role)
