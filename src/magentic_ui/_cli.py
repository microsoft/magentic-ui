import argparse
import asyncio
import json
import logging
import os
import signal
import sys
import types
from datetime import datetime
from pathlib import Path
from typing import Any, List, Literal, Optional, cast

import yaml
from autogen_core import EVENT_LOGGER_NAME, CancellationToken
from .cli import Console, PrettyConsole
from .task_team import get_task_team
from loguru import logger

from .agents.mcp._config import McpAgentConfig
from .magentic_ui_config import MagenticUIConfig, ModelClientConfigs
from .types import RunPaths
from .utils import LLMCallFilter
from ._docker import (
    check_docker_running,
    check_browser_image,
    check_python_image,
    build_browser_image,
    build_python_image,
)

BOLD = "\033[1m"
RESET = "\033[0m"
MAGENTA = "\033[35m"


# Simple debug logging helper - no formatting, just output
# This lets the StylizedConsole handle all the formatting consistently
def log_debug(msg: str, debug: bool = False) -> None:
    """Log debug information if debug mode is enabled."""
    if debug:
        # Simple logging - StylizedConsole will handle formatting
        print(f"DEBUG: {msg}")


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
    log_debug(
        f"Starting cancellable_input with type: {input_type}",
        getattr(cancellation_token, "_debug", False),
    )

    # Suppress the "Enter your response:" prompt which appears at the wrong time in the UI
    if prompt.strip() == "Enter your response:":
        prompt = ""

    # Add a newline before the prompt to ensure it appears on a new line
    # This fixes the issue where the prompt appears on the same line as previous output
    if input_type == "text_input" and not prompt.startswith("\n"):
        prompt = f"\n{prompt}"

    task: asyncio.Task[str] = asyncio.create_task(asyncio.to_thread(input, prompt))
    if cancellation_token is not None:
        log_debug(
            "Linking cancellation token to input task",
            getattr(cancellation_token, "_debug", False),
        )
        cancellation_token.link_future(task)
    result = await task
    log_debug(
        f"Cancellable input completed with result length: {len(result)}",
        getattr(cancellation_token, "_debug", False),
    )
    return result


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
    log_debug(f"LLM logging configured to: {log_file}", True)


async def get_team(
    cooperative_planning: bool,
    autonomous_execution: bool,
    work_dir: str,
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
    model_context_token_limit: int = 128000,
    client_config: str | None = None,
    action_policy: ApprovalPolicy = "never",
    user_proxy_type: str | None = None,
    task_metadata: str | None = None,
    hints: str | None = None,
    answer: str | None = None,
    mcp_agents: List[McpAgentConfig] | None = None,
    use_pretty_ui: bool = True,
    run_without_docker: bool = False,
    browser_headless: bool = False,
    sentinel_tasks: bool = False,
) -> None:
    log_debug("=== Starting get_team function ===", debug)
    log_debug(
        f"Args: cooperative_planning={cooperative_planning}, autonomous_execution={autonomous_execution}, reset={reset}",
        debug,
    )
    log_debug(
        f"Args: inside_docker={inside_docker}, action_policy={action_policy}, user_proxy_type={user_proxy_type}",
        debug,
    )

    if reset:
        print(f"Resetting state file: {state_file}")
        # delete the state file if it exists
        if os.path.exists(state_file):
            print(f"Deleting state file: {state_file}")
            log_debug(f"Deleting existing state file at: {state_file}", debug)
            os.remove(state_file)

    if inside_docker:
        log_debug("Running inside Docker container", debug)
        # Use environment variables as fallback if paths not provided
        if internal_workspace_root is None:
            internal_workspace_root = os.environ.get("INTERNAL_WORKSPACE_ROOT")
            log_debug(
                f"Using INTERNAL_WORKSPACE_ROOT from env: {internal_workspace_root}",
                debug,
            )
        if external_workspace_root is None:
            external_workspace_root = os.environ.get("EXTERNAL_WORKSPACE_ROOT")
            log_debug(
                f"Using EXTERNAL_WORKSPACE_ROOT from env: {external_workspace_root}",
                debug,
            )

        if not internal_workspace_root or not external_workspace_root:
            error_msg = "When running inside docker, both internal and external workspace root paths must be provided either via arguments or environment variables"
            log_debug(f"ERROR: {error_msg}", debug)
            raise ValueError(error_msg)

        # In contrast to the UI -- where each session creates a new folder --
        # we need a consistent folder name so that benchmark scripts will know
        # where to place input files.
        cli_files_path = os.path.join(internal_workspace_root, "cli_files")
        log_debug(f"Creating CLI files directory at: {cli_files_path}", debug)
        os.makedirs(cli_files_path, exist_ok=True)

        paths = RunPaths(
            internal_root_dir=Path(internal_workspace_root),
            external_root_dir=Path(external_workspace_root),
            run_suffix="run",
            internal_run_dir=Path(cli_files_path),
            external_run_dir=Path(os.path.join(external_workspace_root, "cli_files")),
        )
        log_debug(
            f"RunPaths created with internal_root_dir: {paths.internal_root_dir}", debug
        )
    else:
        log_debug("Running outside Docker container", debug)
        if not work_dir:
            error_msg = "When running outside docker, work_dir path must be provided"
            log_debug(f"ERROR: {error_msg}", debug)
            raise ValueError(error_msg)

        work_dir_path = Path(work_dir)
        log_debug(f"Using work_dir: {work_dir_path}", debug)

        cli_files_path = os.path.join(work_dir, "cli_files")
        log_debug(f"Creating CLI files directory at: {cli_files_path}", debug)
        os.makedirs(cli_files_path, exist_ok=True)
        work_dir_files = work_dir_path / "cli_files"

        paths = RunPaths(
            internal_root_dir=work_dir_path,
            external_root_dir=work_dir_path,
            run_suffix="run",
            internal_run_dir=work_dir_files,
            external_run_dir=work_dir_files,
        )
        log_debug("RunPaths created with internal/external run dirs", debug)

    client_config_dict: dict[str, Any] = {}
    if client_config:
        log_debug(f"Loading client configuration from: {client_config}", debug)
        with open(client_config, "r") as f:
            client_config_dict = yaml.safe_load(f)
            log_debug(
                f"Client config loaded with {len(client_config_dict)} keys", debug
            )

    # sets the configurations for each different agent
    model_client_configs = ModelClientConfigs(
        orchestrator=client_config_dict.get("orchestrator_client", None),
        web_surfer=client_config_dict.get("web_surfer_client", None),
        coder=client_config_dict.get("coder_client", None),
        file_surfer=client_config_dict.get("file_surfer_client", None),
        action_guard=client_config_dict.get("action_guard_client", None),
    )

    mcp_agents = mcp_agents or []
    log_debug("Model client configs created for agents", debug)

    magentic_ui_config = MagenticUIConfig(
        model_client_configs=model_client_configs,
        mcp_agent_configs=mcp_agents,
        cooperative_planning=cooperative_planning,
        autonomous_execution=autonomous_execution,
        approval_policy=action_policy,
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
        sentinel_tasks=sentinel_tasks,
        run_without_docker=run_without_docker,
        browser_headless=browser_headless,
    )
    log_debug(
        f"MagenticUIConfig created with planning={cooperative_planning}, execution={autonomous_execution}",
        debug,
    )

    log_debug("Starting team creation", debug)

    # Creates and returns a RoundRobinGroupChat or a GroupChat with the passed configs
    log_debug("Calling get_task_team to create team object", debug)
    team = await get_task_team(
        magentic_ui_config=magentic_ui_config,
        input_func=cancellable_input,
        paths=paths,
    )
    log_debug(f"Team created with type: {type(team).__name__}", debug)

    # Team is a RoundRobinGroupChat or GroupChat instance
    log_debug("Team creation completed successfully", debug)

    if use_pretty_ui:
        display_magentic_ui_logo()
    log_debug("Logo displayed", debug)

    try:
        if state_file and os.path.exists(state_file) and not reset:
            state = None
            log_debug(f"Loading state from: {state_file}", debug)

            with open(state_file, "r") as f:
                state = json.load(f)
                log_debug("State loaded successfully", debug)

            log_debug("Calling team.load_state with loaded state", debug)
            await team.load_state(state)
            log_debug("State loading completed", debug)

        if not task:
            log_debug("No task provided, prompting user for input", debug)

            def flushed_input(prompt: str) -> str:
                # Prompt for input, but flush the prompt to ensure it appears immediately
                print(prompt, end="", flush=True)
                user_input = input()
                log_debug(f"User input received, length: {len(user_input)}", debug)
                return user_input

            log_debug("Creating input task in event loop", debug)
            task = await asyncio.get_event_loop().run_in_executor(
                None,
                flushed_input,
                f"{MAGENTA}{BOLD}Enter your task (or press Ctrl+C to cancel):  {RESET}",
            )
            log_debug("User input task completed", debug)

        log_debug(
            f"Task to execute: {task[:50] if task else ''}{'...' if task and len(task) > 50 else ''}",
            debug,
        )

        log_debug("Creating team run stream with task", debug)
        stream = team.run_stream(task=task)
        log_debug(
            f"Stream created, passing to {'PrettyConsole' if use_pretty_ui else 'Console'} with debug={debug}",
            debug,
        )

        # Use PrettyConsole or the regular console based on the use_pretty_ui parameter
        if use_pretty_ui:
            await PrettyConsole(stream, debug=debug)
        else:
            # Console doesn't accept debug parameter, using default Console
            log_debug(
                "Using default Console without debug parameter",
                debug,
            )
            await Console(stream)

        log_debug("Console processing completed", debug)

        log_debug("Saving team state", debug)
        state = await team.save_state()
        log_debug("State saved successfully", debug)

        log_debug(f"Writing state to file: {state_file}", debug)
        with open(state_file, "w") as f:
            json.dump(state, f, indent=2)
        log_debug("State file write completed", debug)

    finally:
        logger.info("Closing team...")
        log_debug("Closing team in finally block", debug)
        await team.close()
        log_debug("Team closed successfully", debug)


def display_magentic_ui_logo():
    """Display the MAGENTIC UI entry text."""

    magentic_logo = f"""{MAGENTA}{BOLD}
╔═══════════════════════════════════════════════════════════════════╗
║    __  __    _    ____ _____ _   _ _____ ___ ____    _   _ ___    ║
║   |  \\/  |  / \\  / ___| ____| \\ | |_   _|_ _/ ___|  | | | |_ _|   ║
║   | |\\/| | / _ \\| |  _|  _| |  \\| | | |  | | |      | | | || |    ║
║   | |  | |/ ___ \\ |_| | |___| |\\  | | |  | | |___   | |_| || |    ║
║   |_|  |_/_/   \\_\\____|_____|_| \\_| |_| |___\\____|   \\___/|___|   ║  
║                                                                   ║
╚═══════════════════════════════════════════════════════════════════╝                                                          
    {RESET}"""

    print(magentic_logo)


def main() -> None:
    parser = argparse.ArgumentParser(description="Magentic-UI CLI")
    parser.add_argument(
        "--work-dir",
        dest="work_dir",
        type=str,
        required=True,
        help="Working directory path: where the team will store its state and files (required)",
    )
    parser.add_argument(
        "--config",
        dest="config",
        type=str,
        default=None,
        help="Path to the configuration file (default: 'config.yaml')",
    )
    parser.add_argument(
        "--run-without-docker",
        dest="run_without_docker",
        action="store_true",
        default=False,
        help="Run without docker. This will remove coder and filesurfer agents and disable live browser view.",
    )
    parser.add_argument(
        "--headless",
        dest="browser_headless",
        action="store_true",
        default=False,
        help="Run browser in headless mode (default: False, browser runs with GUI)",
    )
    parser.add_argument(
        "--debug",
        dest="debug",
        action="store_true",
        default=False,
        help="Enable debug mode to show internal messages and detailed agent interactions (default: disabled)",
    )
    parser.add_argument(
        "--use-state",
        dest="use_state",
        action="store_true",
        default=False,
        help="Use and save the team state before and after running the task (default: always start fresh and do not use state)",
    )

    # Advanced options group
    advanced = parser.add_argument_group("Advanced options")
    advanced.add_argument(
        "--disable-planning",
        dest="cooperative_planning",
        action="store_false",
        default=True,
        help="Disable co-planning mode (default: enabled), user will not be involved in the planning process",
    )
    advanced.add_argument(
        "--autonomous-execution",
        dest="autonomous_execution",
        action="store_true",
        default=False,
        help="Enable autonomous execution mode (default: disabled), user will not be involved in the execution",
    )
    advanced.add_argument(
        "--autonomous",
        dest="autonomous",
        action="store_true",
        default=False,
        help="Enable autonomous mode (default: disabled), no co-planning and no human involvment in execution",
    )
    advanced.add_argument(
        "--task",
        dest="task",
        type=str,
        default="",
        help="Specifies the initial task. If a plain string, use this input verbatim. If the string matches a filename, read the initial task from a file. Use '-' to read from stdin. (default: prompt's the user for the task)",
    )
    advanced.add_argument(
        "--final-answer-prompt",
        dest="final_answer_prompt",
        type=str,
        default="",
        help="Overrides the final answer prompt used to summarize the conversation. If a plain string, use this input verbatim. If the string matches a filename, read the prompt from a file. (default: use orchestrator's built-in prompt)",
    )
    advanced.add_argument(
        "--internal-root",
        dest="internal_workspace_root",
        type=str,
        default=None,
        help="Deprecated: Internal workspace root directory path (default: use INTERNAL_WORKSPACE_ROOT environment variable)",
    )
    advanced.add_argument(
        "--external-root",
        dest="external_workspace_root",
        type=str,
        default=None,
        help="Deprecated: External workspace root directory path (default: use EXTERNAL_WORKSPACE_ROOT environment variable)",
    )
    advanced.add_argument(
        "--playwright-port",
        dest="playwright_port",
        type=int,
        default=-1,
        help="Port to run the Playwright browser on (default: -1 means use default port)",
    )
    advanced.add_argument(
        "--novnc-port",
        dest="novnc_port",
        type=int,
        default=-1,
        help="Port to run the noVNC server on (default: -1 means use default port)",
    )
    advanced.add_argument(
        "--inside-docker",
        dest="inside_docker",
        action="store_true",
        default=False,
        help="Deprecated:Indicates if running inside docker container (default: False)",
    )
    advanced.add_argument(
        "--user-proxy-type",
        dest="user_proxy_type",
        type=str,
        choices=["dummy", "metadata"],
        default=None,
        help="Type of user proxy agent to use for simulations ('dummy', 'metadata', or None for default; default: None)",
    )
    advanced.add_argument(
        "--metadata-task",
        dest="metadata_task",
        type=str,
        default=None,
        help="Task description for metadata user proxy (required if user-proxy-type is 'metadata')",
    )
    advanced.add_argument(
        "--metadata-hints",
        dest="metadata_hints",
        type=str,
        default=None,
        help="Task hints for metadata user proxy (required if user-proxy-type is 'metadata')",
    )
    advanced.add_argument(
        "--metadata-answer",
        dest="metadata_answer",
        type=str,
        default=None,
        help="Task answer for metadata user proxy (required if user-proxy-type is 'metadata')",
    )
    advanced.add_argument(
        "--llmlog-dir",
        dest="llmlog_dir",
        type=str,
        help="Directory path to save LLM call logs (if not provided, LLM logging is disabled)",
    )
    advanced.add_argument(
        "--action-policy",
        dest="action_policy",
        type=str,
        default="never",
        help="ActionGuard policy ('always', 'never', 'auto-conservative', 'auto-permissive'; default: never)",
    )
    advanced.add_argument(
        "--mcp-agents-file",
        dest="mcp_agents_file",
        type=str,
        default=None,
        help="Path to a .yaml file containing configuration compatible with MagenticUIConfig.mcp_agents",
    )
    advanced.add_argument(
        "--old-cli",
        dest="use_pretty_ui",
        action="store_false",
        default=True,
        help="Use the old console without fancy formatting (default: use pretty terminal)",
    )
    advanced.add_argument(
        "--sentinel-tasks",
        dest="sentinel_tasks",
        action="store_true",
        default=False,
        help="Use sentinel tasks to guide the agent's behavior (default: False)",
    )
    args = parser.parse_args()
    log_debug(f"Command line arguments parsed: debug={args.debug}", args.debug)

    # Show summary of important arguments when debug is enabled
    if args.debug:
        log_debug(f"Cooperative planning: {args.cooperative_planning}", args.debug)
        log_debug(f"Autonomous execution: {args.autonomous_execution}", args.debug)
        log_debug(f"Autonomous mode: {args.autonomous}", args.debug)
        log_debug(f"Use state: {args.use_state}", args.debug)
        log_debug(f"Task specified: {bool(args.task)}", args.debug)
        log_debug(f"Action policy: {args.action_policy}", args.debug)
        log_debug(f"Inside Docker: {args.inside_docker}", args.debug)
        log_debug(f"Work directory: {args.work_dir}", args.debug)
        log_debug(f"Config file: {args.config}", args.debug)
        log_debug(f"User proxy type: {args.user_proxy_type}", args.debug)
        log_debug(f"LLM log directory: {args.llmlog_dir}", args.debug)
        log_debug(f"Sentinel tasks: {args.sentinel_tasks}", args.debug)
        log_debug(
            f"Console mode: {'Pretty' if args.use_pretty_ui else 'Old'}", args.debug
        )
        log_debug(f"Browser headless: {args.browser_headless}", args.debug)

    # Validate user proxy type
    log_debug("Validating user proxy type", args.debug)
    if args.user_proxy_type not in [None, "dummy", "metadata"]:
        error_msg = f"Invalid user proxy type: {args.user_proxy_type}. Valid options are None, 'dummy', or 'metadata'."
        log_debug(f"ERROR: {error_msg}", args.debug)
        raise ValueError(error_msg)

    # Validate metadata user proxy parameters
    log_debug("Validating metadata user proxy parameters", args.debug)
    if args.user_proxy_type == "metadata":
        if not all([args.metadata_task, args.metadata_hints, args.metadata_answer]):
            error_msg = "When using metadata user proxy type, all metadata parameters (--metadata-task, --metadata-hints, --metadata-answer) must be provided."
            log_debug(f"ERROR: {error_msg}", args.debug)
            raise ValueError(error_msg)

    # Validate action policy
    log_debug("Validating action policy", args.debug)
    if args.action_policy not in [
        "always",
        "never",
        "auto-conservative",
        "auto-permissive",
    ]:
        error_msg = f"Invalid action policy: {args.action_policy}. Valid options are 'always', 'never', 'auto-conservative', 'auto-permissive'."
        log_debug(f"ERROR: {error_msg}", args.debug)
        raise ValueError(error_msg)

    # Set up LLM logging if requested
    if args.llmlog_dir:
        log_debug(f"Setting up LLM logging to directory: {args.llmlog_dir}", args.debug)
        setup_llm_logging(args.llmlog_dir)

    # If the config file is not provided, check for the default config file
    client_config: str | None = args.config
    if not client_config:
        if os.path.isfile("config.yaml"):
            client_config = "config.yaml"
            log_debug(
                "Using default config.yaml file found in current directory", args.debug
            )
        else:
            log_debug(
                "No config file provided or found. Using default settings.", args.debug
            )
            logger.info("Config file not provided. Using default settings.")

    # Expand the task and final answer prompt
    log_debug("Processing task input", args.debug)
    task: str | None = None
    if args.task:
        if args.task == "-":
            log_debug("Reading task from stdin", args.debug)
            task = sys.stdin.buffer.read().decode("utf-8")
            log_debug(
                f"Task read from stdin, length: {len(task if task else '')}", args.debug
            )
        elif os.path.isfile(args.task):
            log_debug(f"Reading task from file: {args.task}", args.debug)
            with open(args.task, "r") as f:
                task = f.read()
                log_debug(
                    f"Task read from file, length: {len(task if task else '')}",
                    args.debug,
                )
        else:
            log_debug("Using task from command line argument", args.debug)
            task = args.task
            log_debug(
                f"Task from argument, length: {len(task if task else '')}", args.debug
            )

    if not args.run_without_docker:
        # Check Docker and build images if necessary
        log_debug("Checking Docker setup...", args.debug)
        logger.info("Checking if Docker is running...")

        if not check_docker_running():
            logger.error("Docker is not running. Please start Docker and try again.")
            sys.exit(1)
        else:
            logger.success("Docker is running")

        # Check and build Docker images if needed
        logger.info("Checking Docker vnc browser image...")
        if not check_browser_image():
            logger.warning("VNC browser image needs to be built")
            logger.info("Building Docker vnc image (this WILL take a few minutes)")
            build_browser_image()
        else:
            logger.success("VNC browser image is available")

        logger.info("Checking Docker python image...")
        if not check_python_image():
            logger.warning("Python image needs to be built")
            logger.info("Building Docker python image (this WILL take a few minutes)")
            build_python_image()
        else:
            logger.success("Python image is available")

        # Verify Docker images exist after attempted build
        if not check_browser_image() or not check_python_image():
            logger.error(
                "Docker images not found. Please build the images and try again."
            )
            sys.exit(1)

        log_debug("Docker setup completed successfully", args.debug)

    log_debug("Processing final answer prompt", args.debug)
    final_answer_prompt: str | None = None
    if args.final_answer_prompt:
        if os.path.isfile(args.final_answer_prompt):
            log_debug(
                f"Reading final answer prompt from file: {args.final_answer_prompt}",
                args.debug,
            )
            with open(args.final_answer_prompt, "r") as f:
                final_answer_prompt = f.read()
                log_debug(
                    f"Final answer prompt read from file, length: {len(final_answer_prompt if final_answer_prompt else '')}",
                    args.debug,
                )
        else:
            log_debug(
                "Using final answer prompt from command line argument", args.debug
            )
            final_answer_prompt = args.final_answer_prompt
            log_debug(
                f"Final answer prompt from argument, length: {len(final_answer_prompt if final_answer_prompt else '')}",
                args.debug,
            )

    # Set up autonomous execution mode if requested
    if args.autonomous:
        log_debug(
            "Autonomous mode enabled, setting autonomous_execution=True and cooperative_planning=False",
            args.debug,
        )
        args.autonomous_execution = True
        args.cooperative_planning = False

    # Try and load an MCP Agents file
    mcp_agents: List[McpAgentConfig] = []
    if args.mcp_agents_file:
        with open(args.mcp_agents_file) as fd:
            mcp_agents_data: Any = yaml.safe_load(fd)

        if not isinstance(mcp_agents_data, list):
            raise TypeError(
                f"Expected root element of mcp_agents_file to be a list but found: {type(mcp_agents_data)}"
            )

        for value in mcp_agents_data:  # type: ignore
            mcp_agent = McpAgentConfig.model_validate(value)
            mcp_agents.append(mcp_agent)
            logger.info(
                f"Loaded MCP Agent '{mcp_agent.name}' with MCP Servers [{', '.join(server.server_name for server in mcp_agent.mcp_servers)}]"
            )

    # Add a basic signal handler to log as soon as SIGINT is received
    def signal_handler(sig: int, frame: types.FrameType | None) -> Any:
        log_debug(f"Signal handler caught signal: {sig}", args.debug)
        logger.info("magentic-ui cli caught SIGINT...")
        log_debug("Raising KeyboardInterrupt to terminate application", args.debug)
        raise KeyboardInterrupt

    log_debug("Registering SIGINT signal handler", args.debug)
    signal.signal(signal.SIGINT, signal_handler)

    # Starts an asyncio event loop responsible for running asynchronous tasks
    log_debug("Starting asyncio event loop for get_team", args.debug)
    asyncio.run(
        # Passes the arguments to the get_team function
        get_team(
            cooperative_planning=args.cooperative_planning,
            autonomous_execution=args.autonomous_execution,
            reset=not args.use_state,  # Invert logic: if not using state, reset is True
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
            use_pretty_ui=args.use_pretty_ui,
            mcp_agents=mcp_agents,
            run_without_docker=args.run_without_docker,
            browser_headless=args.browser_headless,
            sentinel_tasks=args.sentinel_tasks,
        )
    )
    log_debug("Asyncio event loop and get_team function completed", args.debug)


if __name__ == "__main__":
    main()
