from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from pathlib import Path
from typing import (
    AsyncGenerator,
    Any,
    cast,
    Dict,
    List,
    Mapping,
    Optional,
    Sequence,
    Union,
)
from loguru import logger
from autogen_agentchat.base import ChatAgent, TaskResult, Team
from autogen_agentchat.messages import AgentEvent, ChatMessage, TextMessage
from autogen_core import EVENT_LOGGER_NAME, CancellationToken, ComponentModel
from autogen_core.logging import LLMCallEvent
from ...task_team import get_task_team
from ...types import RunPaths
from ...magentic_ui_config import MagenticUIConfig, ModelClientConfigs
from ...input_func import InputFuncType
from ...agents import WebSurfer

from ..datamodel.types import EnvironmentVariable, LLMCallEventMessage, TeamResult
from ..datamodel.db import Run
from ..utils.utils import get_modified_files
from ...tools.playwright.browser.utils import get_browser_resource_config


class RunEventLogger(logging.Handler):
    """Event logger that queues LLMCallEvents for streaming"""

    def __init__(self) -> None:
        super().__init__()
        self.events: asyncio.Queue[LLMCallEventMessage] = asyncio.Queue()

    def emit(self, record: logging.LogRecord) -> None:
        if isinstance(record.msg, LLMCallEvent):
            self.events.put_nowait(LLMCallEventMessage(content=str(record.msg)))


class TeamManager:
    """Manages team operations including loading configs and running teams"""

    def __init__(
        self,
        internal_workspace_root: Path,
        external_workspace_root: Path,
        run_without_docker: bool,
        inside_docker: bool = True,
        config: dict[str, Any] = {},
    ) -> None:
        self.team: Team | None = None
        self.load_from_config = False
        self.internal_workspace_root = internal_workspace_root
        self.external_workspace_root = external_workspace_root
        self.inside_docker = inside_docker
        self.run_without_docker = run_without_docker
        self.config = config
        # Track uploaded files across the entire conversation
        self.uploaded_files: set[str] = set()

    @staticmethod
    async def load_from_file(path: Union[str, Path]) -> Dict[str, Any]:
        """Load team configuration from JSON/YAML file"""
        raise NotImplementedError(
            "This method should be implemented in a subclass or replaced with actual loading logic."
        )

    def prepare_run_paths(
        self,
        run: Optional[Run] = None,
    ) -> RunPaths:
        external_workspace_root = self.external_workspace_root
        internal_workspace_root = self.internal_workspace_root

        if run:
            run_suffix = os.path.join(
                "files",
                "user",
                str(run.user_id or "unknown_user"),
                str(run.session_id or "unknown_session"),
                str(run.id or "unknown_run"),
            )
        else:
            run_suffix = os.path.join(
                "files", "user", "unknown_user", "unknown_session", "unknown_run"
            )

        internal_run_dir = internal_workspace_root / Path(run_suffix)
        external_run_dir = external_workspace_root / Path(run_suffix)
        # Can only make dir on internal, as it is what a potential docker container sees.
        # TO-ANSWER: why ?
        logger.info(f"Creating run dirs: {internal_run_dir} and {external_run_dir}")
        if self.inside_docker:
            internal_run_dir.mkdir(parents=True, exist_ok=True)
        else:
            external_run_dir.mkdir(parents=True, exist_ok=True)

        return RunPaths(
            internal_root_dir=internal_workspace_root,
            external_root_dir=external_workspace_root,
            run_suffix=run_suffix,
            internal_run_dir=internal_run_dir,
            external_run_dir=external_run_dir,
        )

    def _extract_uploaded_file_names(
        self, task: Optional[Union[ChatMessage, str, Sequence[ChatMessage]]]
    ) -> set[str]:
        """Extract names of uploaded files from the task to exclude them from generated files tracking"""
        uploaded_files: set[str] = set()

        if not task:
            return uploaded_files

        # Handle different task types
        if isinstance(task, str):
            return uploaded_files
        elif hasattr(task, "metadata"):
            # Single ChatMessage
            messages = [task]
        else:
            # Handle Sequence[ChatMessage]
            try:
                messages = list(task)
            except TypeError:
                return uploaded_files

        for message in messages:
            if hasattr(message, "metadata"):
                metadata = getattr(message, "metadata", None)
                if metadata and isinstance(metadata, dict):
                    attached_files_json: Any = metadata.get("attached_files")  # type: ignore
                    if attached_files_json and isinstance(attached_files_json, str):
                        try:
                            attached_files: Any = json.loads(attached_files_json)
                            if isinstance(attached_files, list):
                                for file_info in attached_files:  # type: ignore
                                    if isinstance(file_info, dict) and cast(
                                        Dict[str, Any], file_info
                                    ).get("uploaded", False):
                                        file_name: Any = cast(
                                            Dict[str, Any], file_info
                                        ).get("name", "")
                                        if isinstance(file_name, str):
                                            uploaded_files.add(file_name)
                        except (json.JSONDecodeError, TypeError):
                            # If parsing fails, continue without crashing
                            pass

        return uploaded_files

    def add_uploaded_files(self, file_names: set[str]) -> None:
        """Add uploaded file names to the tracking set to exclude them from generated files"""
        self.uploaded_files.update(file_names)
        logger.info(f"Added {len(file_names)} uploaded files to tracking: {file_names}")
        logger.info(f"Total uploaded files being tracked: {self.uploaded_files}")

    @staticmethod
    async def load_from_directory(directory: Union[str, Path]) -> List[Dict[str, Any]]:
        """Load all team configurations from a directory"""
        raise NotImplementedError(
            "This method should be implemented in a subclass or replaced with actual loading logic."
        )

    async def _create_team(
        self,
        team_config: Union[str, Path, Dict[str, Any], ComponentModel],
        state: Optional[Mapping[str, Any] | str] = None,
        input_func: Optional[InputFuncType] = None,
        env_vars: Optional[List[EnvironmentVariable]] = None,
        settings_config: dict[str, Any] = {},
        *,
        paths: RunPaths,
    ) -> tuple[Team, int, int]:
        """Create team instance from config"""
        if not self.run_without_docker:
            _, novnc_port, playwright_port = get_browser_resource_config(
                paths.external_run_dir, -1, -1, self.inside_docker
            )
        else:
            novnc_port = -1
            playwright_port = -1

        try:
            # Logic here: we first see if the config file passed to magentic-ui has valid configs for all clients
            # If Yes: this takes precedent over the UI LLM config and is passed to magentic-ui team
            # If No: we disregard it and use the UI LLM config
            model_client_from_config_file = ModelClientConfigs(
                orchestrator=self.config.get("orchestrator_client", None),
                web_surfer=self.config.get("web_surfer_client", None),
                coder=self.config.get("coder_client", None),
                file_surfer=self.config.get("file_surfer_client", None),
                action_guard=self.config.get("action_guard_client", None),
            )
            is_complete_config_from_file = all(
                [
                    model_client_from_config_file.orchestrator,
                    model_client_from_config_file.web_surfer,
                    model_client_from_config_file.coder,
                    model_client_from_config_file.file_surfer,
                    model_client_from_config_file.action_guard,
                ]
            )

            # Logic here: first, we see if the config file passed to magentic-ui has valid MCP agent configuration
            # If valid: the configuration file takes precedent over the UI settings to configure MCP agent for team
            # If invalid: we disregard in the configuration file and use the UI settings to configure MCP agent for team

            # Get mcp_agent_configs from configuration file
            mcp_agent_config_from_config_file: List[Dict[str, Any]] = self.config.get(
                "mcp_agent_configs", []
            )
            # Get mcp_agent_configs from frontend settings
            settings_mcp_configs = settings_config.get("mcp_agent_configs", [])

            # Verify the MCP agent configuration in the configuration file
            def validate_mcp_config(mcp_config: Dict[str, Any]) -> bool:
                """
                Verify the MCP agent configuration is valid
                Check if the mcp_servers field is a list and has at least one element, and name and description are alpha-numeric
                """
                mcp_servers: List[Dict[str, Any]] = mcp_config.get("mcp_servers", [])
                if not isinstance(mcp_servers, list) or len(mcp_servers) == 0:
                    return False

                agent_name: str | None = mcp_config.get("name")
                agent_description: str | None = mcp_config.get("description")
                if (
                    not isinstance(agent_name, str)
                    or not agent_name.isalnum()
                    or not isinstance(agent_description, str)
                ):
                    return False

                for server in mcp_servers:
                    if not isinstance(server, dict):
                        return False
                    server_name = server.get("server_name")
                    if not isinstance(server_name, str) or not server_name.isalnum():
                        return False

                return True

            # If there are MCP configurations in config file, validate and use them
            if mcp_agent_config_from_config_file:
                # Verify the MCP agent configuration in the configuration file
                all_valid = True
                for config in mcp_agent_config_from_config_file:
                    if validate_mcp_config(config):
                        pass
                    else:
                        all_valid = False
                        break

                if not all_valid:
                    logger.warning(
                        "MCP agent configurations in config file are invalid, falling back to frontend settings."
                    )
                    settings_config["mcp_agent_configs"] = settings_mcp_configs
                else:
                    settings_config["mcp_agent_configs"] = (
                        mcp_agent_config_from_config_file
                    )
            else:
                # If no MCP configurations in config file, use frontend settings
                settings_config["mcp_agent_configs"] = settings_mcp_configs

            # Common configuration parameters
            config_params = {
                **settings_config,  # type: ignore,
                # These must always be set to the values computed above
                "playwright_port": playwright_port,
                "novnc_port": novnc_port,
                # Defer to self for inside_docker
                "inside_docker": self.inside_docker,
            }

            # Override client configs if complete config from file is available
            if is_complete_config_from_file:
                config_params["model_client_configs"] = model_client_from_config_file
            else:
                logger.warning(
                    "Using LLM client configurations from UI settings (default is OpenAI) since no config file passed or config file incomplete."
                )
            if self.run_without_docker:
                config_params["run_without_docker"] = True
                # Allow browser_headless to be set by settings_config
            else:
                if settings_config.get("run_without_docker", False):
                    # Allow settings_config to set browser_headless
                    pass
                else:
                    config_params["browser_headless"] = False
            magentic_ui_config = MagenticUIConfig(**config_params)  # type: ignore
            self.team = cast(
                Team,
                await get_task_team(
                    magentic_ui_config=magentic_ui_config,
                    input_func=input_func,
                    paths=paths,
                ),
            )
            if hasattr(self.team, "_participants"):
                for agent in cast(list[ChatAgent], self.team._participants):  # type: ignore
                    if isinstance(agent, WebSurfer):
                        novnc_port = agent.novnc_port
                        playwright_port = agent.playwright_port

            if state:
                if isinstance(state, str):
                    # Check if the string is empty or whitespace only
                    if not state.strip():
                        # Skip loading if state is empty
                        pass
                    else:
                        try:
                            state_dict = json.loads(state)
                            await self.team.load_state(state_dict)
                        except json.JSONDecodeError as json_error:
                            # Log error and skip loading invalid JSON state
                            logger.warning(
                                f"Warning: Failed to load state - invalid JSON: {json_error}"
                            )

                else:
                    await self.team.load_state(state)

            return self.team, novnc_port, playwright_port
        except Exception as e:
            logger.error(f"Error creating team: {e}")
            await self.close()
            raise

    async def run_stream(
        self,
        task: Optional[Union[ChatMessage, str, Sequence[ChatMessage]]],
        team_config: Union[str, Path, dict[str, Any], ComponentModel],
        state: Optional[Mapping[str, Any] | str] = None,
        input_func: Optional[InputFuncType] = None,
        cancellation_token: Optional[CancellationToken] = None,
        env_vars: Optional[List[EnvironmentVariable]] = None,
        settings_config: Optional[Dict[str, Any]] = None,
        run: Optional[Run] = None,
    ) -> AsyncGenerator[
        Union[AgentEvent, ChatMessage, LLMCallEventMessage, TeamResult], None
    ]:
        """Stream team execution results"""
        start_time = time.time()

        # Setup logger correctly
        logger = logging.getLogger(EVENT_LOGGER_NAME)
        logger.setLevel(logging.CRITICAL)
        llm_event_logger = RunEventLogger()
        logger.handlers = [llm_event_logger]  # Replace all handlers
        logger.info(f"Running in docker: {self.inside_docker}")
        paths = self.prepare_run_paths(run=run)
        known_files = set(
            file["name"]
            for file in get_modified_files(
                0, time.time(), source_dir=str(paths.internal_run_dir)
            )
        )

        # Extract uploaded file names from the task to exclude them from generated files tracking
        task_uploaded_files = self._extract_uploaded_file_names(task)
        self.uploaded_files.update(task_uploaded_files)
        logger.info(
            f"Found {len(task_uploaded_files)} new uploaded files to exclude from generated files tracking: {task_uploaded_files}"
        )
        logger.info(f"Total uploaded files being tracked: {self.uploaded_files}")

        global_new_files: List[Dict[str, str]] = []
        try:
            # TODO: This might cause problems later if we are not careful
            if self.team is None:
                # TODO: if we start allowing load from config, we'll need to write the novnc and playwright ports back to the team config..
                _, _, _ = await self._create_team(
                    team_config,
                    state,
                    input_func,
                    env_vars,
                    settings_config or {},
                    paths=paths,
                )

                # Initialize known files by name for tracking
                initial_files = get_modified_files(
                    start_time, time.time(), source_dir=str(paths.internal_run_dir)
                )
                known_files = {file["name"] for file in initial_files}
                # Add uploaded files to known_files so they don't get marked as generated
                known_files.update(self.uploaded_files)

                async for message in self.team.run_stream(  # type: ignore
                    task=task, cancellation_token=cancellation_token
                ):
                    if cancellation_token and cancellation_token.is_cancelled():
                        break

                    # Get all current files with full metadata
                    modified_files = get_modified_files(
                        start_time, time.time(), source_dir=str(paths.internal_run_dir)
                    )
                    current_file_names = {file["name"] for file in modified_files}

                    # Find new files, excluding uploaded files
                    new_file_names = (
                        current_file_names - known_files - self.uploaded_files
                    )
                    known_files = current_file_names  # Update for next iteration

                    # Get the full data for new files
                    new_files = [
                        file
                        for file in modified_files
                        if file["name"] in new_file_names
                    ]

                    if new_files:
                        # filter files that start with "tmp_code"
                        new_files = [
                            file
                            for file in new_files
                            if not file["name"].startswith("tmp_code")
                            and not file["name"].startswith("supervisord.pid")
                        ]
                        if len(new_files) > 0:
                            file_message = TextMessage(
                                source="system",
                                content="File Generated",
                                metadata={
                                    "internal": "no",
                                    "type": "file",
                                    "files": json.dumps(new_files),
                                },
                            )
                            global_new_files.extend(new_files)
                            yield file_message

                    if isinstance(message, TaskResult):
                        yield TeamResult(
                            task_result=message,
                            usage="",
                            duration=time.time() - start_time,
                            files=modified_files,  # Full file data preserved
                        )
                    else:
                        yield message

                    # Add generated files to final output
                    if (
                        isinstance(message, TextMessage)
                        and message.metadata.get("type", "") == "final_answer"
                    ):
                        if len(global_new_files) > 0:
                            # only keep unique file names, if there is a file with the same name, keep the latest one
                            global_new_files = list(
                                {
                                    file["name"]: file for file in global_new_files
                                }.values()
                            )
                            file_message = TextMessage(
                                source="system",
                                content="File Generated",
                                metadata={
                                    "internal": "no",
                                    "type": "file",
                                    "files": json.dumps(global_new_files),
                                },
                            )
                            yield file_message
                            global_new_files = []

                    # Check for any LLM events
                    while not llm_event_logger.events.empty():
                        event = await llm_event_logger.events.get()
                        yield event
        finally:
            # Cleanup - remove our handler
            if llm_event_logger in logger.handlers:
                logger.handlers.remove(llm_event_logger)

            # Ensure cleanup happens
            if self.team and hasattr(self.team, "close"):
                logger.info("Closing team")
                await self.team.close()  # type: ignore
                logger.info("Team closed")

    async def close(self):
        """Close the team manager"""
        if self.team and hasattr(self.team, "close"):
            logger.info("Closing team")
            await self.team.close()  # type: ignore
            self.team = None
            logger.info("Team closed")
        else:
            logger.warning("Team manager is not initialized or already closed")

    async def run(
        self,
        task: ChatMessage | Sequence[ChatMessage] | str | None,
        team_config: Union[str, Path, dict[str, Any], ComponentModel],
        input_func: Optional[InputFuncType] = None,
        cancellation_token: Optional[CancellationToken] = None,
        env_vars: Optional[List[EnvironmentVariable]] = None,
    ) -> TeamResult:
        """Run team synchronously"""
        raise NotImplementedError("Use run_stream instead")

    async def pause_run(self) -> None:
        """Pause the run"""
        if self.team:
            await self.team.pause()

    async def resume_run(self) -> None:
        """Resume the run"""
        if self.team:
            await self.team.resume()
