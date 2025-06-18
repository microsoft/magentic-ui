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
import aiofiles
import yaml
from loguru import logger
from autogen_agentchat.base import ChatAgent, TaskResult, Team
from autogen_agentchat.messages import AgentEvent, ChatMessage, TextMessage
from autogen_core import EVENT_LOGGER_NAME, CancellationToken, ComponentModel
from autogen_core.logging import LLMCallEvent
from ...task_team import get_task_team
from ...teams import GroupChat
from ...types import RunPaths
from ...magentic_ui_config import MagenticUIConfig, ModelClientConfigs
from ...input_func import InputFuncType
from ...agents import WebSurfer

from ..datamodel.types import EnvironmentVariable, LLMCallEventMessage, TeamResult
from ..datamodel.db import Run
from ..utils.utils import get_modified_files, decompress_state
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
        inside_docker: bool = True,
        config: dict[str, Any] = {},
    ) -> None:
        self.team: Team | None = None
        self.load_from_config = False
        self.internal_workspace_root = internal_workspace_root
        self.external_workspace_root = external_workspace_root
        self.inside_docker = inside_docker
        self.config = config

    @staticmethod
    async def load_from_file(path: Union[str, Path]) -> Dict[str, Any]:
        """Load team configuration from JSON/YAML file"""
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Config file not found: {path}")

        async with aiofiles.open(path) as f:
            content = await f.read()
            if path.suffix == ".json":
                return json.loads(content)
            elif path.suffix in (".yml", ".yaml"):
                return yaml.safe_load(content)
            raise ValueError(f"Unsupported file format: {path.suffix}")

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
        # TO-ANSWER: why?
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

    @staticmethod
    async def load_from_directory(directory: Union[str, Path]) -> List[Dict[str, Any]]:
        """Load all team configurations from a directory"""
        directory = Path(directory)
        configs: List[Dict[str, Any]] = []
        valid_extensions = {".json", ".yaml", ".yml"}

        for path in directory.iterdir():
            if path.is_file() and path.suffix.lower() in valid_extensions:
                try:
                    config = await TeamManager.load_from_file(path)
                    configs.append(config)
                except Exception as e:
                    logger.error(f"Failed to load {path}: {e}")

        return configs

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

        _, novnc_port, playwright_port = get_browser_resource_config(
            paths.external_run_dir, -1, -1, self.inside_docker
        )
        try:
            if not self.load_from_config:
                # Load model configurations from settings if provided
                model_configs: Dict[str, Any] = {}
                if settings_config.get("model_configs"):
                    try:
                        model_configs = yaml.safe_load(settings_config["model_configs"])
                    except Exception as e:
                        logger.error(f"Error loading model configs: {e}")
                        raise e

                # Use model configs from settings if available, otherwise fall back to config
                model_client_configs = ModelClientConfigs(
                    orchestrator=model_configs.get(
                        "orchestrator_client",
                        self.config.get("orchestrator_client", None),
                    ),
                    web_surfer=model_configs.get(
                        "web_surfer_client",
                        self.config.get("web_surfer_client", None),
                    ),
                    coder=model_configs.get(
                        "coder_client", self.config.get("coder_client", None)
                    ),
                    file_surfer=model_configs.get(
                        "file_surfer_client",
                        self.config.get("file_surfer_client", None),
                    ),
                    action_guard=model_configs.get(
                        "action_guard_client",
                        self.config.get("action_guard_client", None),
                    ),
                )

                magentic_ui_config = MagenticUIConfig(
                    **(settings_config or {}),
                    model_client_configs=model_client_configs,
                    playwright_port=playwright_port,
                    novnc_port=novnc_port,
                    inside_docker=self.inside_docker,
                )

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
                        try:
                            # Try to decompress if it's compressed
                            state_dict = decompress_state(state)
                            await self.team.load_state(state_dict)
                        except Exception:
                            # If decompression fails, assume it's a regular JSON string
                            state_dict = json.loads(state)
                            await self.team.load_state(state_dict)
                    else:
                        await self.team.load_state(state)

                return self.team, novnc_port, playwright_port

            if isinstance(team_config, (str, Path)):
                config = await self.load_from_file(team_config)
            elif isinstance(team_config, dict):
                config = team_config
            else:
                config = team_config.model_dump()

            # Load env vars into environment if provided
            if env_vars:
                logger.info("Loading environment variables")
                for var in env_vars:
                    os.environ[var.name] = var.value

            self.team = cast(Team, GroupChat.load_component(config))

            if hasattr(self.team, "_participants"):
                for agent in cast(list[ChatAgent], self.team._participants):  # type: ignore
                    if hasattr(agent, "input_func"):
                        agent.input_func = input_func  # type: ignore
                    if isinstance(agent, WebSurfer):
                        novnc_port = agent.novnc_port or -1
                        playwright_port = agent.playwright_port or -1
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
        global_new_files: List[Dict[str, str]] = []
        try:
            # TODO: This might cause problems later if we are not careful
            if self.team is None:
                # TODO: if we start allowing load from config, we'll need to write the novnc and playwright ports back to the team config..
                _, _novnc_port, _playwright_port = await self._create_team(
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

                yield TextMessage(
                    source="system",
                    content=f"Browser noVNC address can be found at http://localhost:{_novnc_port}/vnc.html",
                    metadata={
                        "internal": "no",
                        "type": "browser_address",
                        "novnc_port": str(_novnc_port),
                        "playwright_port": str(_playwright_port),
                    },
                )

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

                    # Find new files
                    new_file_names = current_file_names - known_files
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
