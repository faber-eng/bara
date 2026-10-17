from collections.abc import Callable
from datetime import timedelta
from typing import Protocol

import google.auth
from google.auth.transport.requests import Request

MAX_UPLOAD_BYTES = 26214400
URL_LIFETIME = timedelta(minutes=15)
LENGTH_RANGE_HEADER = "x-goog-content-length-range"


class InvalidObjectName(Exception):
    pass


class SigningUnavailable(Exception):
    pass


class SigningAuth(Protocol):
    service_account_email: str
    access_token: str


class AdcSigningAuth:
    def __init__(self):
        credentials, _ = google.auth.default()
        credentials.refresh(Request())
        email = getattr(credentials, "service_account_email", None)
        if email is None or email == "default":
            raise SigningUnavailable(
                "ADC has no service account email; run on Cloud Run or "
                "impersonate bara-api to sign URLs"
            )
        self.service_account_email: str = email
        self.access_token: str = credentials.token


def require_safe_name(name: str) -> str:
    if name == "" or name.startswith("/") or ".." in name:
        raise InvalidObjectName("object name must be relative and contain no '..'")
    return name


class EvidenceStorage:
    def __init__(self, bucket, signing_auth_factory: Callable[[], SigningAuth]):
        self._bucket = bucket
        self._signing_auth_factory = signing_auth_factory

    def signed_put_url(self, object_name: str) -> str:
        return self._sign(
            object_name,
            method="PUT",
            headers={LENGTH_RANGE_HEADER: f"0,{MAX_UPLOAD_BYTES}"},
        )

    def signed_get_url(self, object_name: str) -> str:
        return self._sign(object_name, method="GET")

    def _sign(self, object_name: str, **options) -> str:
        blob = self._bucket.blob(require_safe_name(object_name))
        auth = self._signing_auth_factory()
        return blob.generate_signed_url(
            version="v4",
            expiration=URL_LIFETIME,
            service_account_email=auth.service_account_email,
            access_token=auth.access_token,
            **options,
        )
