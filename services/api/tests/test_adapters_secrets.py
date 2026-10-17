from types import SimpleNamespace

import pytest
from google.api_core import exceptions as gax

from adapters.secrets import SecretManagerReader, SecretUnavailable


class FakeSecretClient:
    def __init__(self, payload=b"bara-secret\n", error=None):
        self._payload = payload
        self._error = error
        self.requested: list[str] = []

    def access_secret_version(self, *, request):
        self.requested.append(request["name"])
        if self._error is not None:
            raise self._error
        return SimpleNamespace(payload=SimpleNamespace(data=self._payload))


def test_the_join_code_is_read_from_the_latest_version_and_trimmed():
    client = FakeSecretClient()

    code = SecretManagerReader(client, "example-project").join_code()

    assert code == "bara-secret"
    assert client.requested == [
        "projects/example-project/secrets/join-code/versions/latest"
    ]


@pytest.mark.parametrize(
    "error",
    [gax.PermissionDenied("no"), gax.NotFound("gone"), gax.ServiceUnavailable("x")],
)
def test_a_google_error_becomes_secret_unavailable(error):
    reader = SecretManagerReader(FakeSecretClient(error=error), "example-project")

    with pytest.raises(SecretUnavailable):
        reader.join_code()


def test_an_empty_secret_is_unavailable():
    reader = SecretManagerReader(FakeSecretClient(payload=b"\n"), "example-project")

    with pytest.raises(SecretUnavailable):
        reader.join_code()
