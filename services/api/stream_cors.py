import re

from starlette.middleware.cors import CORSMiddleware
from starlette.types import ASGIApp, Receive, Scope, Send

STREAM_PATH = re.compile(r"^/api/cases/[^/]+/stream$")
STREAM_METHODS = ["GET", "OPTIONS"]
STREAM_HEADERS = ["Authorization", "X-Bara-Role"]


class StreamOnlyCors:
    def __init__(self, app: ASGIApp, allow_origins: list[str]):
        self._app = app
        self._cors = CORSMiddleware(
            app,
            allow_origins=allow_origins,
            allow_methods=STREAM_METHODS,
            allow_headers=STREAM_HEADERS,
        )

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and STREAM_PATH.match(scope["path"]):
            await self._cors(scope, receive, send)
            return
        await self._app(scope, receive, send)
