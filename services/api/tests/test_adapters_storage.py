import os
from datetime import timedelta

import pytest

from adapters.storage import (
    MAX_UPLOAD_BYTES,
    EvidenceStorage,
    InvalidObjectName,
)
from tests.fakes import RecordingBucket, fixed_signing_auth


def make_storage():
    bucket = RecordingBucket()
    return EvidenceStorage(bucket, fixed_signing_auth), bucket


def test_max_upload_is_25_mb():
    assert MAX_UPLOAD_BYTES == 26214400


def test_signed_put_url_is_v4_put_for_15_minutes():
    storage, bucket = make_storage()

    url = storage.signed_put_url("evidence/e1.jpg")

    call = bucket.calls[0]
    assert url.startswith("https://storage.test/evidence/e1.jpg")
    assert call["version"] == "v4"
    assert call["method"] == "PUT"
    assert call["expiration"] == timedelta(minutes=15)


def test_signed_put_url_signs_the_content_length_range_header():
    storage, bucket = make_storage()

    storage.signed_put_url("evidence/e1.jpg")

    assert bucket.calls[0]["headers"] == {"x-goog-content-length-range": "0,26214400"}


def test_signed_put_url_signs_with_the_service_account_and_access_token():
    storage, bucket = make_storage()

    storage.signed_put_url("evidence/e1.jpg")

    call = bucket.calls[0]
    assert call["service_account_email"] == "bara-api@example.iam.gserviceaccount.com"
    assert call["access_token"] == "ya29.fake-token"


def test_signed_get_url_is_v4_get_for_15_minutes_with_no_range_header():
    storage, bucket = make_storage()

    storage.signed_get_url("evidence/e1.jpg")

    call = bucket.calls[0]
    assert call["method"] == "GET"
    assert call["version"] == "v4"
    assert call["expiration"] == timedelta(minutes=15)
    assert "headers" not in call


@pytest.mark.parametrize(
    "name", ["../secret", "a/../b", "/abs/path.jpg", "evidence/..", ""]
)
def test_unsafe_object_names_are_rejected_for_put_and_get(name):
    storage, bucket = make_storage()

    with pytest.raises(InvalidObjectName):
        storage.signed_put_url(name)
    with pytest.raises(InvalidObjectName):
        storage.signed_get_url(name)

    assert bucket.calls == []


@pytest.mark.live
def test_live_signed_put_url_is_signed():
    from google.cloud import storage

    from adapters.storage import AdcSigningAuth

    project = os.environ["GOOGLE_CLOUD_PROJECT"]
    bucket = storage.Client(project=project).bucket(f"{project}-bara-evidence")

    url = EvidenceStorage(bucket, AdcSigningAuth).signed_put_url("live/probe.jpg")

    assert "X-Goog-Signature=" in url
