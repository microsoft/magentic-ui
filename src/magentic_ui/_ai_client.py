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

from openai import AsyncOpenAI

if TYPE_CHECKING:
    from .agents.web_surfer.fara._types import LLMMessage


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

    kwargs: dict[str, Any] = {"max_retries": 5}
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
    )
    return client, model  # type: ignore[return-value]
