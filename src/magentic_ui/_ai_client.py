"""LLM client factory and wrapper.

Config format (from config.yaml):
    provider: AzureOpenAIChatCompletionClient   # or OpenAIChatCompletionClient
    config:
        model: gpt-4o
        base_url: ...
        api_key: ...
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any, Union, cast

import httpx
import openai
from openai import AsyncOpenAI

if TYPE_CHECKING:
    from .agents.web_surfer.fara._types import LLMMessage


# A short connect timeout surfaces "can't reach the server" (wrong base_url,
# VPN off) in seconds instead of hanging. The read timeout only guards against
# a server that accepted the request but never replies; a generous default
# tolerates cold starts, and the slow-model UI signal covers the wait.
_CONNECT_TIMEOUT_SECONDS = 5.0
_READ_TIMEOUT_SECONDS = 120.0


def _build_timeout() -> httpx.Timeout:
    # Pool acquisition uses the short connect timeout so an unreachable server
    # fails fast instead of waiting the full read timeout for a free
    # connection. Writing the request body shares the generous read budget.
    return httpx.Timeout(
        connect=_CONNECT_TIMEOUT_SECONDS,
        read=_READ_TIMEOUT_SECONDS,
        write=_READ_TIMEOUT_SECONDS,
        pool=_CONNECT_TIMEOUT_SECONDS,
    )


def humanize_model_error(error: BaseException) -> str | None:
    """Translate a model-call exception into a user-readable message.

    Follows the ``__cause__`` chain so transient errors wrapped in a
    ``RuntimeError`` are still recognized. Returns ``None`` for anything
    unrecognized, leaving the caller to surface the raw text.
    """
    seen: set[int] = set()
    exc: BaseException | None = error
    while exc is not None and id(exc) not in seen:
        seen.add(id(exc))
        # APITimeoutError subclasses APIConnectionError, so check it first.
        if isinstance(exc, openai.APITimeoutError):
            return (
                "The model server did not respond in time. It may be overloaded "
                "or still starting up — try again in a moment."
            )
        if isinstance(exc, openai.APIConnectionError):
            host = _error_host(exc)
            where = f" at {host}" if host else ""
            return (
                f"Could not reach the model server{where}. Check your network "
                "connection, VPN, and the configured base_url."
            )
        if isinstance(exc, openai.AuthenticationError):
            return "The model server rejected the API key. Check your API key configuration."
        if isinstance(exc, openai.PermissionDeniedError):
            return "The model server denied access. Check that the API key may use this model."
        if isinstance(exc, openai.RateLimitError):
            if getattr(exc, "code", None) == "insufficient_quota":
                return "The model account is out of quota. Check the plan and billing."
            return (
                "The model server is rate limiting requests. Wait a moment and retry."
            )
        if isinstance(exc, openai.NotFoundError):
            return "The configured model was not found on the server. Check the model name."
        exc = exc.__cause__
    return None


def _error_host(error: BaseException) -> str | None:
    request = getattr(error, "request", None)
    url = getattr(request, "url", None)
    host = getattr(url, "host", None)
    return str(host) if host else None


def is_retryable_model_error(error: BaseException) -> bool:
    """Whether a model-call error is transient and worth retrying.

    Retryable (transient): plain 429 rate limits, request timeouts, 5xx.
    Fatal (fail fast): connection errors (the SDK already retried and
    still couldn't reach the server), auth / permission / not-found, and
    quota exhaustion — retrying these can't help.

    Shared by OmniAgent (``_responses._call_api``) and FaraWebSurfer
    (``_fara_web_surfer`` run loop) so both classify network errors the
    same way. Unrecognized errors are treated as fatal.
    """
    # APITimeoutError subclasses APIConnectionError, so check it first.
    if isinstance(error, openai.APITimeoutError):
        return True
    if isinstance(error, openai.APIConnectionError):
        return False
    if isinstance(error, openai.RateLimitError):
        return getattr(error, "code", None) != "insufficient_quota"
    if isinstance(error, openai.APIStatusError):
        return error.status_code >= 500
    return False


# ---------------------------------------------------------------------------
# ChatClient — thin AsyncOpenAI wrapper that converts LLMMessage to OpenAI format.
# ---------------------------------------------------------------------------


class ChatClient:
    """Holds AsyncOpenAI + model, converts LLMMessage to OpenAI format.

    Usage:
        client = create_client(config)
        result = await client.create(messages)
    """

    def __init__(self, client: AsyncOpenAI, model: str) -> None:
        self._client = client
        self.model = model

    async def create(self, messages: list[LLMMessage], **kwargs: Any) -> str:  # noqa: ANN401
        """Call LLM and return response text."""
        openai_messages = [m.to_openai_dict() for m in messages]
        response = await self._client.chat.completions.create(  # type: ignore[reportUnknownMemberType]
            model=self.model,
            messages=openai_messages,  # type: ignore[arg-type]
            **kwargs,
        )
        return str(response.choices[0].message.content or "").strip()  # type: ignore[reportUnknownMemberType]

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.close()


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

# Provider names that trigger Azure client creation
_AZURE_PROVIDERS = {
    "AzureOpenAIChatCompletionClient",
    "azure_openai_chat_completion_client",
    "azure",
}


def create_client(config: Union[Any, None]) -> tuple[AsyncOpenAI, str]:
    """Create an AsyncOpenAI client from model config dict.

    Args:
        config: Top-level model config with ``provider`` and ``config`` keys.

    Returns:
        ``(client, model_name)`` tuple.
    """
    if config is None:
        raise ValueError(
            "Model client config is required — configure it in config.yaml"
        )

    if hasattr(config, "model_dump"):
        config = config.model_dump()

    all_config = cast(dict[str, Any], config)
    provider: str = all_config.get("provider", "")
    model_config: dict[str, Any] = all_config.get("config", {})

    if provider in _AZURE_PROVIDERS:
        return _create_azure(model_config)

    return create_openai_client(model_config)


def create_openai_client(model_config: dict[str, Any]) -> tuple[AsyncOpenAI, str]:
    model = model_config.get("model", "gpt-4.1-2025-04-14")

    kwargs: dict[str, Any] = {"max_retries": 5, "timeout": _build_timeout()}
    if model_config.get("base_url"):
        kwargs["base_url"] = model_config["base_url"]
    api_key = (
        model_config.get("api_key") or os.environ.get("OPENAI_API_KEY") or "not-needed"
    )
    kwargs["api_key"] = api_key

    return AsyncOpenAI(**kwargs), model


def _create_azure(model_config: dict[str, Any]) -> tuple[AsyncOpenAI, str]:
    from azure.identity import (
        AzureCliCredential,
        ChainedTokenCredential,
        ManagedIdentityCredential,
        get_bearer_token_provider,
    )
    from openai import AsyncAzureOpenAI

    model = model_config.get("model") or model_config.get("azure_deployment")
    if not model:
        raise ValueError("Missing 'model' or 'azure_deployment' in config")

    azure_endpoint = model_config.get("azure_endpoint")
    if not azure_endpoint:
        raise ValueError("Missing 'azure_endpoint' in config")

    azure_deployment = model_config.get("azure_deployment")
    if not azure_deployment:
        raise ValueError("Missing 'azure_deployment' in config")

    api_version = model_config.get("api_version", "2024-12-01-preview")

    token_provider_cfg = model_config.get("azure_ad_token_provider", {})
    scopes = token_provider_cfg.get("config", {}).get("scopes", [])
    if not scopes:
        raise ValueError("Missing 'azure_ad_token_provider.config.scopes' in config")

    credential = get_bearer_token_provider(
        ChainedTokenCredential(AzureCliCredential(), ManagedIdentityCredential()),
        scopes[0],
    )

    client = AsyncAzureOpenAI(
        azure_endpoint=azure_endpoint,
        azure_deployment=azure_deployment,
        api_version=api_version,
        azure_ad_token_provider=credential,
        max_retries=5,
        timeout=_build_timeout(),
    )
    return client, model  # type: ignore[return-value]
