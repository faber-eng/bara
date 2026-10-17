import asyncio
import logging
import os
from collections.abc import Mapping
from typing import Protocol

from google import genai
from google.adk.models import BaseLlm, FallbackModel, Gemini
from google.genai import errors, types

from config import ConfigError, ModelsConfig, Role, Settings

logger = logging.getLogger(__name__)

FALLBACK_STATUS_CODES = frozenset({404, 429})
RETRY_STATUS_CODES = [500, 502, 503, 504]
RETRY_ATTEMPTS = 3
REQUEST_TIMEOUT_MS = 60_000
ENTERPRISE_VARIABLE = "GOOGLE_GENAI_USE_ENTERPRISE"
ENABLED_VALUES = frozenset({"true", "1"})


class AsyncModels(Protocol):
    async def generate_content(
        self,
        *,
        model: str,
        contents: types.ContentListUnion,
        config: types.GenerateContentConfigOrDict | None = None,
    ) -> types.GenerateContentResponse: ...


class SyncModels(Protocol):
    def generate_content(
        self,
        *,
        model: str,
        contents: types.ContentListUnion,
        config: types.GenerateContentConfigOrDict | None = None,
    ) -> types.GenerateContentResponse: ...


class SyncClient(Protocol):
    @property
    def models(self) -> SyncModels: ...


class ThreadedModels:
    def __init__(self, client: SyncClient):
        self._client = client

    async def generate_content(
        self,
        *,
        model: str,
        contents: types.ContentListUnion,
        config: types.GenerateContentConfigOrDict | None = None,
    ) -> types.GenerateContentResponse:
        return await asyncio.to_thread(
            self._client.models.generate_content,
            model=model,
            contents=contents,
            config=config,
        )


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
        timeout=REQUEST_TIMEOUT_MS,
        retry_options=types.HttpRetryOptions(
            attempts=RETRY_ATTEMPTS, http_status_codes=RETRY_STATUS_CODES
        ),
    )


def build_vertex_clients(settings: Settings) -> dict[Role, AsyncModels]:
    return {
        role: ThreadedModels(
            genai.Client(
                enterprise=True,
                project=settings.project,
                location=settings.models.for_role(role).location,
                http_options=build_http_options(),
            )
        )
        for role in ("reasoning", "fast")
    }


def require_enterprise_mode(environ: Mapping[str, str]) -> None:
    value = environ.get(ENTERPRISE_VARIABLE, "").lower()
    if value not in ENABLED_VALUES:
        raise ConfigError(
            f"{ENTERPRISE_VARIABLE} must be True: ADK sends the agent's output "
            "schema together with its tools only in Vertex enterprise mode"
        )


def agent_gemini(settings: Settings, model: str, location: str) -> Gemini:
    return Gemini(
        model=model,
        client_kwargs={
            "enterprise": True,
            "project": settings.project,
            "location": location,
            "http_options": build_http_options(),
        },
    )


def compose_agent_model(primary: BaseLlm, fallback: BaseLlm) -> FallbackModel:
    return FallbackModel(
        models=[primary, fallback], retriable_status_codes=FALLBACK_STATUS_CODES
    )


def build_agent_model(
    settings: Settings, environ: Mapping[str, str] = os.environ
) -> FallbackModel:
    require_enterprise_mode(environ)
    route = settings.models.reasoning
    return compose_agent_model(
        agent_gemini(settings, route.model, route.location),
        agent_gemini(settings, route.fallback, route.location),
    )
