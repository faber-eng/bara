from typing import Protocol

from google.api_core import exceptions as gax

JOIN_CODE_SECRET = "join-code"


class SecretUnavailable(Exception):
    pass


class SecretReader(Protocol):
    def join_code(self) -> str: ...


class SecretManagerReader:
    def __init__(self, client, project: str):
        self._client = client
        self._project = project

    def join_code(self) -> str:
        name = f"projects/{self._project}/secrets/{JOIN_CODE_SECRET}/versions/latest"
        try:
            response = self._client.access_secret_version(request={"name": name})
        except gax.GoogleAPICallError as error:
            raise SecretUnavailable(type(error).__name__) from error
        code = response.payload.data.decode().strip()
        if code == "":
            raise SecretUnavailable("empty secret")
        return code
