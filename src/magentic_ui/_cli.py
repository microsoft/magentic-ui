import os
from pathlib import Path
import sys
import json
import asyncio
import argparse
import signal
from datetime import datetime
import types
import yaml
from typing import Any, Optional, Literal, cast
from autogen_core import EVENT_LOGGER_NAME, CancellationToken
from autogen_agentchat.ui import Console
from .task_team import get_task_team
from loguru import logger
import logging
from .utils import LLMCallFilter
from .types import RunPaths
from .magentic_ui_config import MagenticUIConfig, ModelClientConfigs

logging.basicConfig(level=logging.WARNING, handlers=[])
logger_llm = logging.getLogger(EVENT_LOGGER_NAME)
logger_llm.setLevel(logging.INFO)

ApprovalPolicy = Literal["always", "never", "auto-conservative", "auto-permissive"]


async def cancellable_input(
    prompt: str,
    cancellation_token: Optional[CancellationToken],
    input_type: Optional[str] = "text_input",
) -> str:
    # Copied from autogen_agentchat.agents.UserProxyAgent
    assert input_type in ["text_input", "approval"]
    task: asyncio.Task[str] = asyncio.create_task(asyncio.to_thread(input, prompt))
    if cancellation_token is not None:
        cancellation_token.link_future(task)
    return await task


def setup_llm_logging(log_dir: str) -> None:
    """Set up logging to capture only LLM calls to a directory."""
    log_file = os.path.join(
        log_dir, f"llm_calls_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    )
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(logging.INFO)
    formatter = logging.Formatter(
        "%(message)s"
    )  # Only log the message since it contains the JSON
    file_handler.setFormatter(formatter)
    file_handler.addFilter(LLMCallFilter())
    for handler in logger_llm.handlers[:]:  # Remove any existing handlers
        logger_llm.removeHandler(handler)
    logger_llm.addHandler(file_handler)


async def get_team(
    cooperative_planning: bool,
    autonomous_execution: bool,
    reset: bool = False,
    task: str | None = None,
    final_answer_prompt: str | None = None,
    debug: bool = False,
    state_file: str = ".magentic_ui_state.json",
    internal_workspace_root: str | None = None,
    external_workspace_root: str | None = None,
    playwright_port: int = -1,
    novnc_port: int = -1,
    inside_docker: bool = False,
    work_dir: str | None = None,
    model_context_token_limit: int = 128000,
    client_config: str | None = None,
    action_policy: ApprovalPolicy = "never",
    user_proxy_type: str | None = None,
    task_metadata: str | None = None,
    hints: str | None = None,
    answer: str | None = None,
) -> None:
    if reset:
        print(f"Resetting state file: {state_file}")
        # delete the state file if it exists
        if os.path.exists(state_file):
            print(f"Deleting state file: {state_file}")
            os.remove(state_file)

    if inside_docker:
        # Use environment variables as fallback if paths not provided
        if internal_workspace_root is None:
            internal_workspace_root = os.environ.get("INTERNAL_WORKSPACE_ROOT")
        if external_workspace_root is None:
            external_workspace_root = os.environ.get("EXTERNAL_WORKSPACE_ROOT")

        if not internal_workspace_root or not external_workspace_root:
            raise ValueError(
                "When running inside docker, both internal and external workspace root paths must be provided either via arguments or environment variables"
            )

        # In contrast to the UI -- where each session creates a new folder --
        # we need a consistent folder name so that benchmark scripts will know
        # where to place input files.
        os.makedirs(os.path.join(internal_workspace_root, "cli_files"), exist_ok=True)

        paths = RunPaths(
            internal_root_dir=Path(internal_workspace_root),
            external_root_dir=Path(external_workspace_root),
            run_suffix="run",
            internal_run_dir=Path(os.path.join(internal_workspace_root, "cli_files")),
            external_run_dir=Path(os.path.join(external_workspace_root, "cli_files")),
        )
    else:
        if not work_dir:
            raise ValueError(
                "When running outside docker, work_dir path must be provided"
            )

        work_dir_path = Path(work_dir)

        os.makedirs(os.path.join(work_dir, "cli_files"), exist_ok=True)
        work_dir_files = work_dir_path / "cli_files"

        paths = RunPaths(
            internal_root_dir=work_dir_path,
            external_root_dir=work_dir_path,
            run_suffix="run",
            internal_run_dir=work_dir_files,
            external_run_dir=work_dir_files,
        )

    client_config_dict: dict[str, Any] = {}
    if client_config:
        with open(client_config, "r") as f:
            client_config_dict = yaml.safe_load(f)

    model_client_configs = ModelClientConfigs(
        orchestrator=client_config_dict.get("orchestrator_client", None),
        web_surfer=client_config_dict.get("web_surfer_client", None),
        coder=client_config_dict.get("coder_client", None),
        file_surfer=client_config_dict.get("file_surfer_client", None),
    )

    magentic_ui_config = MagenticUIConfig(
        model_client_configs=model_client_configs,
        approval_policy=action_policy,
        cooperative_planning=cooperative_planning,
        autonomous_execution=autonomous_execution,
        allow_for_replans=True,
        do_bing_search=False,
        model_context_token_limit=model_context_token_limit,
        allow_follow_up_input=False,
        final_answer_prompt=final_answer_prompt,
        playwright_port=playwright_port,
        novnc_port=novnc_port,
        user_proxy_type=user_proxy_type,
        task=task_metadata,
        hints=hints,
        answer=answer,
        inside_docker=inside_docker,
    )

    team = await get_task_team(
        magentic_ui_config=magentic_ui_config,
        input_func=cancellable_input,
        paths=paths,
    )

    try:
        if state_file and os.path.exists(state_file) and not reset:
            state = None
            with open(state_file, "r") as f:
                state = json.load(f)
            await team.load_state(state)

        if not task:

            def flushed_input(prompt: str) -> str:
                # Prompt for input, but flush the prompt to ensure it appears immediately
                print(prompt, end="", flush=True)
                return input()

            task = await asyncio.get_event_loop().run_in_executor(
                None, flushed_input, ">: "
            )

        stream = team.run_stream(task=task)
        await Console(stream)

        state = await team.save_state()

        with open(state_file, "w") as f:
            json.dump(state, f, indent=2)

    finally:
        logger.info("Closing team...")
        await team.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Magentic-UI CLI")
    parser.add_argument(
        "--disable-planning",
        dest="cooperative_planning",
        action="store_false",
        default=True,
        help="Disable co-planning mode (default: enabled), user will not be involved in the planning process",
    )
    parser.add_argument(
        "--autonomous-execution",
        dest="autonomous_execution",
        action="store_true",
        default=False,
        help="Enable autonomous execution mode (default: disabled), user will not be involved in the execution",
    )
    parser.add_argument(
        "--autonomous",
        dest="autonomous",
        action="store_true",
        default=False,
        help="Enable autonomous mode (default: disabled), no co-planning and no human involvment in execution",
    )
    parser.add_argument(
        "--reset",
        dest="reset",
        action="store_true",
        default=False,
        help="Reset the team state before running the task otherwise continue with the previous state (default: False)",
    )
    parser.add_argument(
        "--task",
        dest="task",
        type=str,
        default="",
        help="Specifies the initial task. If a plain string, use this input verbatim. If the string matches a filename, read the initial task from a file. Use '-' to read from stdin. (default: prompt's the user for the task)",
    )
    parser.add_argument(
        "--final-answer-prompt",
        dest="final_answer_prompt",
        type=str,
        default="",
        help="Overrides the final answer prompt used to summarize the conversation. If a plain string, use this input verbatim. If the string matches a filename, read the prompt from a file. (default: use orchestrator's built-in prompt)",
    )
    parser.add_argument(
        "--debug",
        dest="debug",
        action="store_true",
        default=False,
        help="Enable debug mode to show internal messages (default: disabled)",
    )
    parser.add_argument(
        "--internal-root",
        dest="internal_workspace_root",
        type=str,
        default=None,
        help="Internal workspace root directory path (default: use INTERNAL_WORKSPACE_ROOT environment variable)",
    )
    parser.add_argument(
        "--external-root",
        dest="external_workspace_root",
        type=str,
        default=None,
        help="External workspace root directory path (default: use EXTERNAL_WORKSPACE_ROOT environment variable)",
    )
    parser.add_argument(
        "--playwright-port",
        dest="playwright_port",
        type=int,
        default=-1,
        help="Port to run the Playwright browser on (default: -1 means use default port)",
    )
    parser.add_argument(
        "--novnc-port",
        dest="novnc_port",
        type=int,
        default=-1,
        help="Port to run the noVNC server on (default: -1 means use default port)",
    )
    parser.add_argument(
        "--inside-docker",
        dest="inside_docker",
        action="store_true",
        default=False,
        help="Indicates if running inside docker container (default: False)",
    )
    parser.add_argument(
        "--work-dir",
        dest="work_dir",
        type=str,
        default=None,
        help="Working directory path when running outside docker (required if not inside docker)",
    )
    parser.add_argument(
        "--config",
        dest="config",
        type=str,
        default=None,
        help="Path to the configuration file (default: 'config.yaml')",
    )
    parser.add_argument(
        "--user-proxy-type",
        dest="user_proxy_type",
        type=str,
        choices=["dummy", "metadata"],
        default=None,
        help="Type of user proxy agent to use ('dummy', 'metadata', or None for default; default: None)",
    )
    parser.add_argument(
        "--metadata-task",
        dest="metadata_task",
        type=str,
        default=None,
        help="Task description for metadata user proxy (required if user-proxy-type is 'metadata')",
    )
    parser.add_argument(
        "--metadata-hints",
        dest="metadata_hints",
        type=str,
        default=None,
        help="Task hints for metadata user proxy (required if user-proxy-type is 'metadata')",
    )
    parser.add_argument(
        "--metadata-answer",
        dest="metadata_answer",
        type=str,
        default=None,
        help="Task answer for metadata user proxy (required if user-proxy-type is 'metadata')",
    )
    parser.add_argument(
        "--llmlog-dir",
        dest="llmlog_dir",
        type=str,
        help="Directory path to save LLM call logs (if not provided, LLM logging is disabled)",
    )
    parser.add_argument(
        "--action-policy",
        dest="action_policy",
        type=str,
        default="never",
        help="ActionGuard policy ('always', 'never', 'auto-conservative', 'auto-permissive'; default: never)",
    )

    args = parser.parse_args()

    # Validate user proxy type
    if args.user_proxy_type not in [None, "dummy", "metadata"]:
        raise ValueError(
            f"Invalid user proxy type: {args.user_proxy_type}. Valid options are None, 'dummy', or 'metadata'."
        )

    # Validate metadata user proxy parameters
    if args.user_proxy_type == "metadata":
        if not all([args.metadata_task, args.metadata_hints, args.metadata_answer]):
            raise ValueError(
                "When using metadata user proxy type, all metadata parameters (--metadata-task, --metadata-hints, --metadata-answer) must be provided."
            )

    # Validate action policy
    if args.action_policy not in [
        "always",
        "never",
        "auto-conservative",
        "auto-permissive",
    ]:
        raise ValueError(
            f"Invalid action policy: {args.action_policy}. Valid options are 'always', 'never', 'auto-conservative', 'auto-permissive'."
        )

    # Set up LLM logging if requested
    if args.llmlog_dir:
        setup_llm_logging(args.llmlog_dir)

    # If the config file is not provided, check for the default config file
    client_config: str | None = args.config
    if not client_config:
        if os.path.isfile("config.yaml"):
            client_config = "config.yaml"
        else:
            logger.info("Config file not provided. Using default settings.")

    # Expand the task and final answer prompt
    task: str | None = None
    if args.task:
        if args.task == "-":
            task = sys.stdin.buffer.read().decode("utf-8")
        elif os.path.isfile(args.task):
            with open(args.task, "r") as f:
                task = f.read()
        else:
            task = args.task

    final_answer_prompt: str | None = None
    if args.final_answer_prompt:
        if os.path.isfile(args.final_answer_prompt):
            with open(args.final_answer_prompt, "r") as f:
                final_answer_prompt = f.read()
        else:
            final_answer_prompt = args.final_answer_prompt

    # Set up autonomous execution mode if requestes
    if args.autonomous:
        args.autonomous_execution = True
        args.cooperative_planning = False

    # Add a basic signal handler to log as soon as SIGINT is received
    def signal_handler(sig: int, frame: types.FrameType | None) -> Any:
        logger.info("magentic-ui cli caught SIGINT...")
        raise KeyboardInterrupt

    signal.signal(signal.SIGINT, signal_handler)

    # Run the team
    asyncio.run(
        get_team(
            cooperative_planning=args.cooperative_planning,
            autonomous_execution=args.autonomous_execution,
            reset=args.reset,
            task=task,
            final_answer_prompt=final_answer_prompt,
            debug=args.debug,
            internal_workspace_root=args.internal_workspace_root,
            external_workspace_root=args.external_workspace_root,
            playwright_port=args.playwright_port,
            novnc_port=args.novnc_port,
            inside_docker=args.inside_docker,
            work_dir=args.work_dir,
            client_config=client_config,
            action_policy=cast(ApprovalPolicy, args.action_policy),
            user_proxy_type=args.user_proxy_type,
            task_metadata=args.metadata_task
            if args.user_proxy_type == "metadata"
            else task,
            hints=args.metadata_hints if args.user_proxy_type == "metadata" else None,
            answer=args.metadata_answer if args.user_proxy_type == "metadata" else None,
        )
    )


if __name__ == "__main__":
    main()
