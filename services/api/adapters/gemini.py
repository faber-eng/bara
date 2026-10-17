import logging
from collections.abc import Mapping
from typing import Protocol

from google import genai
from google.genai import errors, types

from config import ModelsConfig, Role, Settings

logger = logging.getLogger(__name__)

FALLBACK_STATUS_CODES = frozenset({404, 429})
RETRY_STATUS_CODES = [500, 502, 503, 504]
RETRY_ATTEMPTS = 3


class AsyncModels(Protocol):
    async def generate_content(
        self,
        *,
        model: str,
        contents: types.ContentListUnion,
        config: types.GenerateContentConfigOrDict | None = None,
    ) -> types.GenerateContentResponse: ...


class ModelGateway:
    def __init__(self, routes: ModelsConfig, clients: Mapping[Role, AsyncModels]):
        self._routes = routes
        self._clients = clients
        self._fallback_used = False

    @property
    def fallback_used(self) -> bool:
        return self._fallback_used

    async def generate(
        self,
        role: Role,
        contents: types.ContentListUnion,
        config: types.GenerateContentConfigOrDict | None = None,
    ) -> types.GenerateContentResponse:
        route = self._routes.for_role(role)
        client = self._clients[role]
        try:
            return await client.generate_content(
                model=route.model, contents=contents, config=config
            )
        except errors.APIError as error:
            if error.code not in FALLBACK_STATUS_CODES:
                raise
            logger.warning(
                "model fallback",
                extra={
                    "fields": {
                        "event": "model_fallback",
                        "role": role,
                        "primary": route.model,
                        "fallback": route.fallback,
                        "code": error.code,
                    }
                },
            )
            self._fallback_used = True
        return await client.generate_content(
            model=route.fallback, contents=contents, config=config
        )


def build_http_options() -> types.HttpOptions:
    return types.HttpOptions(
        retry_options=types.HttpRetryOptions(
            attempts=RETRY_ATTEMPTS, http_status_codes=RETRY_STATUS_CODES
        )
    )


def build_vertex_clients(settings: Settings) -> dict[Role, AsyncModels]:
    return {
        role: genai.Client(
            enterprise=True,
            project=settings.project,
            location=settings.models.for_role(role).location,
            http_options=build_http_options(),
        ).aio.models
        for role in ("reasoning", "fast")
    }
