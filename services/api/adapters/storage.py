from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from typing import Protocol

import google.auth
from google.api_core import exceptions as gax
from google.auth.exceptions import GoogleAuthError
from google.auth.transport.requests import Request

MAX_UPLOAD_BYTES = 26214400
URL_LIFETIME = timedelta(minutes=15)
LENGTH_RANGE_HEADER = "x-goog-content-length-range"


@dataclass(frozen=True)
class SignedUpload:
    url: str
    headers: dict[str, str]


class InvalidObjectName(Exception):
    pass


class SigningUnavailable(Exception):
    pass


SIGNING_ERRORS = (
    InvalidObjectName,
    SigningUnavailable,
    GoogleAuthError,
    gax.GoogleAPIError,
)


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

    def signed_put_url(self, object_name: str, content_type: str) -> SignedUpload:
        length_range = {LENGTH_RANGE_HEADER: f"0,{MAX_UPLOAD_BYTES}"}
        url = self._sign(
            object_name,
            method="PUT",
            content_type=content_type,
            headers=dict(length_range),
        )
        return SignedUpload(url, {"Content-Type": content_type, **length_range})

    def read(self, object_name: str) -> bytes | None:
        try:
            return self._bucket.blob(require_safe_name(object_name)).download_as_bytes()
        except gax.NotFound:
            return None

    def gcs_uri(self, object_name: str) -> str:
        return f"gs://{self._bucket.name}/{require_safe_name(object_name)}"

    def object_name_of(self, uri: str) -> str:
        prefix = f"gs://{self._bucket.name}/"
        if not uri.startswith(prefix):
            raise InvalidObjectName(f"{uri!r} is not in the evidence bucket")
        return uri.removeprefix(prefix)

    def read_uri(self, uri: str) -> bytes | None:
        return self.read(self.object_name_of(uri))

    def signed_get_url(self, object_name: str) -> str:
        return self._sign(object_name, method="GET")

    def signed_get_url_for(self, uri: str) -> str:
        return self.signed_get_url(self.object_name_of(uri))

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
