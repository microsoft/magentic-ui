from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Annotated, Any, Literal

import yaml
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Agent mode
# ---------------------------------------------------------------------------


class AgentMode(str, Enum):
    """Deployment mode controlling which agents are active."""

    ALL = "all"
    WEBSURFER_ONLY = "websurfer_only"
    OMNIAGENT_ONLY = "omniagent_only"


def required_roles_for_mode(agent_mode: AgentMode) -> set[str]:
    """Return the ``model_client_configs`` keys required by ``agent_mode``."""
    if agent_mode == AgentMode.OMNIAGENT_ONLY:
        return {"orchestrator"}
    if agent_mode == AgentMode.WEBSURFER_ONLY:
        return {"web_surfer"}
    return {"orchestrator", "web_surfer"}


def is_onboarding_complete(config: dict[str, Any]) -> bool:
    """True iff every model required by the active ``agent_mode`` is set in
    ``model_client_configs``.

    Tolerates a missing or invalid ``agent_mode`` (falls back to ``ALL``).
    """
    raw_mode = config.get("agent_mode") or AgentMode.ALL.value
    try:
        mode = AgentMode(raw_mode)
    except ValueError:
        mode = AgentMode.ALL
    raw_model_configs = config.get("model_client_configs", {})
    if not isinstance(raw_model_configs, dict):
        return False
    model_configs: dict[str, Any] = raw_model_configs  # pyright: ignore[reportUnknownVariableType]
    return all(model_configs.get(role) for role in required_roles_for_mode(mode))


class ApprovalPolicy(str, Enum):
    """Policy for tool approval prompts.

    Controls whether the user is prompted before executing tools that
    have ``requires_approval=True``.
    """

    AUTO_APPROVE = "auto_approve"
    """Skip all approval prompts (eval runs, trusted environments)."""

    REQUIRE_APPROVAL_UNTRUSTED = "require_approval_untrusted"
    """Prompt for tools with requires_approval=True (default)."""

    REQUIRE_APPROVAL_ALL = "require_approval_all"
    """Prompt for every tool call."""


# ---------------------------------------------------------------------------
# Sandbox config (matching harness pattern)
# ---------------------------------------------------------------------------


class QuicksandSandboxConfig(BaseModel):
    """Quicksand VM sandbox configuration."""

    type: Literal["quicksand"] = "quicksand"
    memory: str = "6G"
    cpus: int = 3
    pool_size: int = 5


class NullSandboxConfig(BaseModel):
    """No sandbox — runs commands directly on host."""

    type: Literal["null"] = "null"


SandboxConfig = Annotated[
    QuicksandSandboxConfig | NullSandboxConfig,
    Field(discriminator="type"),
]


# ---------------------------------------------------------------------------
# Model info & role defaults
# ---------------------------------------------------------------------------


class ModelInfoConfig(BaseModel):
    """Model capability flags for a model endpoint."""

    vision: bool = False
    function_calling: bool = False
    json_output: bool = True
    family: str = "unknown"
    structured_output: bool = False
    multiple_system_messages: bool = False


# Authoritative defaults for non-user-facing fields per agent role.
# Used by onboarding API and YAML config loading to fill missing fields.
ROLE_DEFAULTS: dict[str, dict[str, Any]] = {
    "orchestrator": {
        "provider": "OpenAIChatCompletionClient",
        "max_retries": 3,
        "model_info": ModelInfoConfig().model_dump(),
    },
    "web_surfer": {
        "provider": "OpenAIChatCompletionClient",
        "max_retries": 3,
        "model_info": ModelInfoConfig(vision=True).model_dump(),
    },
}


# ---------------------------------------------------------------------------
# Model client configs
# ---------------------------------------------------------------------------


class ModelClientConfigs(BaseModel):
    """Configurations for the model clients."""

    orchestrator: dict[str, Any] | None = None
    web_surfer: dict[str, Any] | None = None


# ---------------------------------------------------------------------------
# Harness config
# ---------------------------------------------------------------------------


class OrchestratorHarnessConfig(BaseModel):
    """Harness config for the orchestrator agent.

    ``max_rounds`` caps how many tool-execution rounds the orchestrator may
    run per batch. When the cap is reached the orchestrator pauses and
    asks the user whether to keep going via a ``ContinuationRequest``;
    a best-effort final answer is generated only if the user chooses
    Stop. The value is exposed through the Settings UI so users can
    extend or shorten long tasks without restarting the backend.
    """

    approval_policy: ApprovalPolicy = ApprovalPolicy.REQUIRE_APPROVAL_UNTRUSTED
    temperature: float = 0.6
    max_rounds: int = Field(default=100, ge=1, le=1000)


class WebSurferHarnessConfig(BaseModel):
    """Harness config for the FaraWebSurfer agent (CUA).

    ``max_rounds`` caps how many actions the CUA may take before pausing
    to ask the user whether to keep going. When the cap is reached the
    harness yields a ``ContinuationRequest`` (``input_type="continuation"``)
    instead of failing — the user can choose to keep going (resets the
    counter for another batch) or to stop with a best-effort answer.
    Free-text replies in the chat input map to Stop (only ``yes`` /
    ``continue`` count as Continue).
    """

    max_rounds: int = Field(default=100, ge=1, le=1000)


class HarnessConfig(BaseModel):
    """Harness configuration — controls safety checks and approval policies."""

    orchestrator: OrchestratorHarnessConfig = Field(
        default_factory=OrchestratorHarnessConfig
    )
    web_surfer: WebSurferHarnessConfig = Field(default_factory=WebSurferHarnessConfig)


# ---------------------------------------------------------------------------
# Eval config
# ---------------------------------------------------------------------------


class EvalConfig(BaseModel):
    """Evaluation-specific configs — not used by the main agent pipeline."""

    eval_client: dict[str, Any] | None = None  # LLM-as-judge
    sim_user_client: dict[str, Any] | None = None  # Simulated user


# ---------------------------------------------------------------------------
# Top-level config
# ---------------------------------------------------------------------------


class MagenticUIConfig(BaseModel):
    """Magentic-UI configuration."""

    # Model clients
    model_client_configs: ModelClientConfigs = Field(default_factory=ModelClientConfigs)

    # Sandbox
    sandbox: SandboxConfig = QuicksandSandboxConfig()

    # Agent behavior
    agent_mode: AgentMode = AgentMode.ALL
    # Which Fara agent implementation to launch:
    #   "qwen3"      — FaraQwen3Agent (11 actions, legacy coordinate API)
    #   "qwen3_next" — FaraQwen3NextAgent (adds double/right/triple_click, drag,
    #                  hscroll, read_page_answer_question, ask_user_question)
    # TODO: For release we get rid of this and pick the one that works best
    web_surfer_variant: Literal["qwen3", "qwen3_next"] = "qwen3_next"
    final_answer_prompt: str | None = None
    user_proxy_type: str | None = None

    # Harness
    harness_config: HarnessConfig = Field(default_factory=HarnessConfig)

    # Eval
    eval: EvalConfig = Field(default_factory=EvalConfig)

    @classmethod
    def from_yaml(cls, path: Path) -> MagenticUIConfig:
        """Load config from a YAML file.

        Returns a fully-validated MagenticUIConfig. Callers that need
        the raw YAML dict (e.g. for partial-merge semantics) should
        read the file directly with ``yaml.safe_load``.
        """
        path = path.expanduser().resolve()
        with open(path) as f:
            data: dict[str, Any] = yaml.safe_load(f) or {}
        return cls(**data)
