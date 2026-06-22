from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Optional, Union

from ._ai_client import create_client
from .agents.base import Capability, SubAgentProtocol
from .agents.registry import AgentEntry, AgentRegistry
from .agents.web_surfer.fara._fara_web_surfer import FaraWebSurfer
from .magentic_ui_config import AgentMode, MagenticUIConfig
from .teams.omniagent._omni_agent import OmniAgent
from .teams.omniagent._registry import DELEGATE_CUA_DEF
from .tools.playwright.browser import get_browser_resource
from .types import PauseController

if TYPE_CHECKING:
    from .tools.playwright.browser.quicksand_browser_manager import (
        QuicksandBrowserManager,
    )


async def get_task_team(
    magentic_ui_config: Optional[MagenticUIConfig] = None,
    *,
    host_run_dir: Path,
    pause_controller: PauseController | None = None,
    quicksand_manager: "QuicksandBrowserManager | None" = None,
    session_id: str | None = None,
) -> Union[SubAgentProtocol, OmniAgent]:
    """Create and return an agent.

    Behavior depends on ``agent_mode``:
    - ``"all"``: OmniAgent with FaraWebSurfer for web delegation.
    - ``"websurfer_only"``: FaraWebSurfer directly.
    - ``"omniagent_only"``: OmniAgent with code/file tools only.
    """
    if magentic_ui_config is None:
        magentic_ui_config = MagenticUIConfig()

    agent_mode = magentic_ui_config.agent_mode

    # Per-session dir (parent of per-run host_run_dir) — survives runs.
    # Used by FaraWebSurfer and OmniAgent for state persistence.
    state_dir = host_run_dir.parent

    if agent_mode == AgentMode.OMNIAGENT_ONLY:
        orchestrator_config = magentic_ui_config.model_client_configs.orchestrator
        client, model = create_client(orchestrator_config)

        if quicksand_manager is not None:
            sandbox = quicksand_manager.sandbox
        else:
            from .sandbox._null import NullSandbox

            sandbox = NullSandbox(workspace=host_run_dir)
            await sandbox.__aenter__()

        return OmniAgent(
            client=client,
            model=model,
            host_workspace=host_run_dir,
            sandbox=sandbox,
            agent_registry=AgentRegistry(),
            agent_mode=agent_mode,
            approval_policy=magentic_ui_config.harness_config.orchestrator.approval_policy,
            temperature=magentic_ui_config.harness_config.orchestrator.temperature,
            max_rounds=magentic_ui_config.harness_config.orchestrator.max_rounds,
            pause_controller=pause_controller,
            state_dir=state_dir,
        )

    # Browser needed for websurfer_only and all modes
    browser, novnc_port, playwright_port = get_browser_resource(
        host_run_dir,
        quicksand_manager=quicksand_manager,
    )

    model_client_config = magentic_ui_config.model_client_configs.web_surfer
    if model_client_config is None:
        raise ValueError(
            "web_surfer model client config is required — configure it in config.yaml"
        )

    web_surfer_max_rounds = magentic_ui_config.harness_config.web_surfer.max_rounds

    if agent_mode == AgentMode.WEBSURFER_ONLY:
        return FaraWebSurfer(
            model_client_config=model_client_config,
            browser=browser,
            novnc_port=novnc_port,
            playwright_port=playwright_port,
            pause_controller=pause_controller,
            agent_variant=magentic_ui_config.web_surfer_variant,
            max_rounds=web_surfer_max_rounds,
            state_dir=state_dir,
            is_standalone=True,
        )

    # agent_mode == "all": OmniAgent with FaraWebSurfer via registry
    web_agent = FaraWebSurfer(
        model_client_config=model_client_config,
        browser=browser,
        novnc_port=novnc_port,
        playwright_port=playwright_port,
        pause_controller=pause_controller,
        agent_variant=magentic_ui_config.web_surfer_variant,
        max_rounds=web_surfer_max_rounds,
        state_dir=state_dir,
        is_standalone=False,
    )

    agent_registry = AgentRegistry()
    agent_registry.register(
        AgentEntry(
            agent=web_agent,
            tool_definition=DELEGATE_CUA_DEF,
            capabilities=frozenset({Capability.WEB_BROWSING}),
        )
    )

    orchestrator_config = magentic_ui_config.model_client_configs.orchestrator
    client, model = create_client(orchestrator_config)

    if quicksand_manager is not None:
        sandbox = quicksand_manager.sandbox
    else:
        from .sandbox._null import NullSandbox

        sandbox = NullSandbox(workspace=host_run_dir)
        await sandbox.__aenter__()

    return OmniAgent(
        client=client,
        model=model,
        host_workspace=host_run_dir,
        sandbox=sandbox,
        agent_registry=agent_registry,
        agent_mode=agent_mode,
        approval_policy=magentic_ui_config.harness_config.orchestrator.approval_policy,
        temperature=magentic_ui_config.harness_config.orchestrator.temperature,
        max_rounds=magentic_ui_config.harness_config.orchestrator.max_rounds,
        pause_controller=pause_controller,
        state_dir=state_dir,
    )
