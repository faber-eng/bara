import os
import uuid
from datetime import timedelta

import httpx
import pytest
from google.cloud import storage

from adapters.storage import (
    MAX_UPLOAD_BYTES,
    AdcSigningAuth,
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

    upload = storage.signed_put_url("evidence/e1.jpg", "image/jpeg")

    call = bucket.calls[0]
    assert upload.url.startswith("https://storage.test/evidence/e1.jpg")
    assert call["version"] == "v4"
    assert call["method"] == "PUT"
    assert call["expiration"] == timedelta(minutes=15)


def test_signed_put_url_signs_and_returns_the_content_type_and_length_range():
    storage, bucket = make_storage()

    upload = storage.signed_put_url("evidence/e1.jpg", "image/png")

    assert bucket.calls[0]["headers"] == {"x-goog-content-length-range": "0,26214400"}
    assert bucket.calls[0]["content_type"] == "image/png"
    assert upload.headers == {
        "Content-Type": "image/png",
        "x-goog-content-length-range": "0,26214400",
    }


def test_read_returns_the_object_bytes_or_none_when_missing():
    storage, bucket = make_storage()
    bucket.objects["evidence/e1.jpg"] = b"jpeg"

    assert storage.read("evidence/e1.jpg") == b"jpeg"
    assert storage.read("evidence/e2.jpg") is None


def test_gcs_uri_names_the_bucket_and_the_object():
    storage, _ = make_storage()

    assert storage.gcs_uri("evidence/e1.jpg") == "gs://bucket-test/evidence/e1.jpg"


def test_read_uri_reads_an_object_of_this_bucket():
    storage, bucket = make_storage()
    bucket.objects["evidence/e1.jpg"] = b"jpeg"

    assert storage.read_uri("gs://bucket-test/evidence/e1.jpg") == b"jpeg"


def test_read_uri_refuses_another_bucket():
    storage, _ = make_storage()

    with pytest.raises(InvalidObjectName):
        storage.read_uri("gs://other-bucket/evidence/e1.jpg")


def test_signed_put_url_signs_with_the_service_account_and_access_token():
    storage, bucket = make_storage()

    storage.signed_put_url("evidence/e1.jpg", "image/jpeg")

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
        storage.signed_put_url(name, "image/jpeg")
    with pytest.raises(InvalidObjectName):
        storage.signed_get_url(name)

    assert bucket.calls == []


@pytest.mark.live
def test_live_signed_put_round_trip_with_the_returned_headers():
    project = os.environ["GOOGLE_CLOUD_PROJECT"]
    bucket = storage.Client(project=project).bucket(f"{project}-bara-evidence")
    evidence = EvidenceStorage(bucket, AdcSigningAuth)
    name = f"live/probe-{uuid.uuid4().hex[:8]}.jpg"

    upload = evidence.signed_put_url(name, "image/jpeg")
    response = httpx.put(upload.url, content=b"probe", headers=upload.headers)
    unsigned = httpx.put(
        upload.url, content=b"probe", headers={"Content-Type": "image/jpeg"}
    )

    try:
        assert response.status_code == 200, response.text
        assert unsigned.status_code == 403
        assert evidence.read(name) == b"probe"
    finally:
        bucket.blob(name).delete()
