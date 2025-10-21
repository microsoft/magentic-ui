import asyncio
import json
import os
import aiofiles
import logging
import datetime
from pathlib import Path
from PIL import Image
from pydantic import BaseModel
from typing import List, Dict, Any, Tuple
from autogen_core.models import ChatCompletionClient
from autogen_core import Image as AGImage
from autogen_agentchat.base import TaskResult, ChatAgent
from autogen_agentchat.messages import (
    MultiModalMessage,
    TextMessage,
)
from autogen_agentchat.conditions import TimeoutTermination
from magentic_ui import OrchestratorConfig
from magentic_ui.magentic_ui_config import SentinelPlanConfig
from magentic_ui.eval.basesystem import BaseSystem
from magentic_ui.eval.models import BaseTask, BaseCandidate, WebVoyagerCandidate
from magentic_ui.types import CheckpointEvent
from magentic_ui.agents import WebSurfer, CoderAgent, FileSurfer
from magentic_ui.teams import GroupChat
from magentic_ui.tools.playwright.browser import VncDockerPlaywrightBrowser
from magentic_ui.tools.playwright.browser import LocalPlaywrightBrowser
from magentic_ui.tools.playwright.browser.utils import get_available_port
from magentic_ui.cli import PrettyConsole
from magentic_ui.eval.benchmarks.sentinelbench.task_variants import (
    DURATION_TASKS,
    COUNT_TASKS,
    DURATION_TASK_TIMEOUTS,
    COUNT_TASK_TIMEOUTS,
    calculate_sentinelbench_timeout,
    get_timeout_display_info,
)


logger = logging.getLogger(__name__)
# Default to WARNING level - will be overridden by verbose flag via core.py
logging.getLogger("autogen").setLevel(logging.WARNING)
logging.getLogger("autogen.agentchat").setLevel(logging.WARNING)
logging.getLogger("autogen_agentchat.events").setLevel(logging.WARNING)


class LogEventSystem(BaseModel):
    """
    Data model for logging events.

    Attributes:
        source (str): The source of the event (e.g., agent name).
        content (str): The content/message of the event.
        timestamp (str): ISO-formatted timestamp of the event.
        metadata (Dict[str, str]): Additional metadata for the event.
    """

    source: str
    content: str
    timestamp: str
    metadata: Dict[str, str] = {}


class MagenticUIAutonomousSystem(BaseSystem):
    """
    MagenticUIAutonomousSystem

    Args:
        name (str): Name of the system instance.
        web_surfer_only (bool): If True, only the web surfer agent is used.
        endpoint_config_orch (Optional[Dict]): Orchestrator model client config.
        endpoint_config_websurfer (Optional[Dict]): WebSurfer agent model client config.
        endpoint_config_coder (Optional[Dict]): Coder agent model client config.
        endpoint_config_file_surfer (Optional[Dict]): FileSurfer agent model client config.
        dataset_name (str): Name of the evaluation dataset (e.g., "Gaia").
        use_local_browser (bool): If True, use the local browser.
        browser_headless (bool): If True, run browser in headless mode (no GUI).
        run_without_docker (bool): If True, run without Docker (disables coder and file surfer agents, forces local browser).
        enable_sentinel (bool): If True, enable sentinel tasks functionality in the orchestrator.
        dynamic_sentinel_sleep (bool): If True, enable dynamic sleep duration adjustment for sentinel steps.
        pretty_output (bool): If True, use PrettyConsole for formatted agent output (default: False).
    """

    def __init__(
        self,
        endpoint_config_orch: Dict[str, Any],
        endpoint_config_websurfer: Dict[str, Any],
        endpoint_config_coder: Dict[str, Any],
        endpoint_config_file_surfer: Dict[str, Any],
        name: str = "MagenticUIAutonomousSystem",
        dataset_name: str = "Gaia",
        web_surfer_only: bool = False,
        use_local_browser: bool = False,
        browser_headless: bool = False,
        run_without_docker: bool = False,
        enable_sentinel: bool = False,
        dynamic_sentinel_sleep: bool = False,
        timeout_minutes: int = 15,
        verbose: bool = False,
        pretty_output: bool = False,
    ):
        super().__init__(name)
        self.candidate_class = WebVoyagerCandidate
        self.endpoint_config_orch = endpoint_config_orch
        self.endpoint_config_websurfer = endpoint_config_websurfer
        self.endpoint_config_coder = endpoint_config_coder
        self.endpoint_config_file_surfer = endpoint_config_file_surfer
        self.web_surfer_only = web_surfer_only
        self.dataset_name = dataset_name
        self.use_local_browser = use_local_browser
        self.browser_headless = browser_headless
        self.run_without_docker = run_without_docker
        self.enable_sentinel = enable_sentinel
        self.dynamic_sentinel_sleep = dynamic_sentinel_sleep
        self.timeout_minutes = timeout_minutes
        self.verbose = verbose
        self.pretty_output = pretty_output

    def _calculate_dynamic_timeout_silent(self, task: BaseTask) -> int:
        """Calculate timeout without printing (for display purposes)."""
        return calculate_sentinelbench_timeout(task, self.timeout_minutes)

    def _get_timeout_display_info(self, task: BaseTask, timeout_seconds: int) -> str:
        """Get formatted timeout display string."""
        return get_timeout_display_info(task, timeout_seconds)

    def _calculate_dynamic_timeout(self, task: BaseTask) -> int:
        """Calculate timeout (reuses silent calculation)."""
        return self._calculate_dynamic_timeout_silent(task)

    def get_answer(
        self, task_id: str, task: BaseTask, output_dir: str
    ) -> BaseCandidate:
        """
        Runs the agent team to solve a given task and saves the answer and logs to disk.

        Args:
            task_id (str): Unique identifier for the task.
            task (BaseTask): The task object containing the question and metadata.
            output_dir (str): Directory to save logs, screenshots, and answer files.

        Returns:
            BaseCandidate: An object containing the final answer and any screenshots taken during execution.
        """

        async def _runner() -> Tuple[str, List[str]]:
            """
            Asynchronous runner that executes the agent team and collects the answer and screenshots.

            Returns:
                Tuple[str, List[str]]: The final answer string and a list of screenshot file paths.
            """
            if self.verbose:
                print(f"\n🔧 VERBOSE MODE ENABLED - Agent conversations will be shown in real-time")
                print(f"🎯 Starting task: {task_id}")
                
            messages_so_far: List[LogEventSystem] = []

            task_question: str = task.question
            
            # Debug: Print the task information
            sentinel_status = "✅ ENABLED" if self.enable_sentinel else "❌ DISABLED"
            
            # Get timeout info for display (without printing it yet)
            timeout_seconds = self._calculate_dynamic_timeout_silent(task)
            timeout_display = self._get_timeout_display_info(task, timeout_seconds)
            
            print(f"\n🎯 \033[1;34m=== TASK INITIALIZATION ===\033[0m")
            print(f"📋 Task ID: \033[1;33m{task_id}\033[0m")
            print(f"🌐 Start URL: \033[1;32m{task.url_path}\033[0m")
            print(f"🛡️ Sentinel Tasks: \033[1;35m{sentinel_status}\033[0m")
            print(f"⏱️ Timeout: \033[1;31m{timeout_display}\033[0m")
            print(f"📝 Task Prompt: \033[1;36m{task_question}\033[0m")
            print(f"\033[1;34m==========================\033[0m\n")
            
            # Adapted from MagenticOne. Minor change is to allow an explanation of the final answer before the final answer.
            FINAL_ANSWER_PROMPT = f"""
            output a FINAL ANSWER to the task.

            The real task is: {task_question}


            To output the final answer, use the following template: [any explanation for final answer] FINAL ANSWER: [YOUR FINAL ANSWER]
            Don't put your answer in brackets or quotes. 
            Your FINAL ANSWER should be a number OR as few words as possible OR a comma separated list of numbers and/or strings.
            ADDITIONALLY, your FINAL ANSWER MUST adhere to any formatting instructions specified in the original question (e.g., alphabetization, sequencing, units, rounding, decimal places, etc.)
            If you are asked for a number, express it numerically (i.e., with digits rather than words), don't use commas, and don't include units such as $ or percent signs unless specified otherwise.
            If you are asked for a string, don't use articles or abbreviations (e.g. for cities), unless specified otherwise. Don't output any final sentence punctuation such as '.', '!', or '?'.
            If you are asked for a comma separated list, apply the above rules depending on whether the elements are numbers or strings.
            You must answer the question and provide a smart guess if you are unsure. Provide a guess even if you have no idea about the answer.
            """
            # Step 2: Create the Magentic-UI team
            # TERMINATION CONDITION
            # Dynamic timeout calculation for SentinelBench duration-based tasks
            timeout_seconds = self._calculate_dynamic_timeout(task)
            termination_condition = TimeoutTermination(
                timeout_seconds=timeout_seconds
            )
            model_context_token_limit = 110000
            # ORCHESTRATOR CONFIGURATION
            orchestrator_config = OrchestratorConfig(
                cooperative_planning=False,
                autonomous_execution=True,
                allow_follow_up_input=False,
                final_answer_prompt=FINAL_ANSWER_PROMPT,
                model_context_token_limit=model_context_token_limit,
                no_overwrite_of_task=True,
                sentinel_plan=SentinelPlanConfig(
                    enable_sentinel_steps=self.enable_sentinel,
                    dynamic_sentinel_sleep=self.dynamic_sentinel_sleep,
                ),
            )

            model_client_orch = ChatCompletionClient.load_component(
                self.endpoint_config_orch
            )
            model_client_coder = ChatCompletionClient.load_component(
                self.endpoint_config_coder
            )
            model_client_websurfer = ChatCompletionClient.load_component(
                self.endpoint_config_websurfer
            )
            model_client_file_surfer = ChatCompletionClient.load_component(
                self.endpoint_config_file_surfer
            )

            # launch the browser
            if self.use_local_browser or self.run_without_docker:
                browser = LocalPlaywrightBrowser(
                    headless=self.browser_headless)  # Use headless mode based on parameter
            else:
                playwright_port, socket = get_available_port()
                novnc_port, socket_vnc = get_available_port()
                socket.close()
                socket_vnc.close()
                browser = VncDockerPlaywrightBrowser(
                    bind_dir=Path(output_dir),
                    playwright_port=playwright_port,
                    novnc_port=novnc_port,
                    inside_docker=False,
                )
                browser_location_log = LogEventSystem(
                    source="browser",
                    content=f"Browser at novnc port {novnc_port} and playwright port {playwright_port} launched",
                    timestamp=datetime.datetime.now().isoformat(),
                )
                messages_so_far.append(browser_location_log)

            # Create web surfer
            web_surfer = WebSurfer(
                name="web_surfer",
                model_client=model_client_websurfer,
                browser=browser,
                animate_actions=False,
                max_actions_per_step=10,
                start_page="about:blank" if task.url_path == "" else task.url_path,
                downloads_folder=os.path.abspath(output_dir),
                debug_dir=os.path.abspath(output_dir),
                model_context_token_limit=model_context_token_limit,
                to_save_screenshots=True,
            )

            agent_list: List[ChatAgent] = [web_surfer]
            # If run_without_docker is True, force web_surfer_only mode to disable Docker-dependent agents
            if not self.web_surfer_only and not self.run_without_docker:
                coder_agent = CoderAgent(
                    name="coder_agent",
                    model_client=model_client_coder,
                    work_dir=os.path.abspath(output_dir),
                    model_context_token_limit=model_context_token_limit,
                )

                file_surfer = FileSurfer(
                    name="file_surfer",
                    model_client=model_client_file_surfer,
                    work_dir=os.path.abspath(output_dir),
                    bind_dir=os.path.abspath(output_dir),
                    model_context_token_limit=model_context_token_limit,
                )
                agent_list.append(coder_agent)
                agent_list.append(file_surfer)
            team = GroupChat(
                participants=agent_list,
                orchestrator_config=orchestrator_config,
                model_client=model_client_orch,
                termination_condition=termination_condition,
            )
            await team.lazy_init()
            # Step 3: Prepare the task message
            answer: str = ""
            # check if file name is an image if it exists
            if (
                hasattr(task, "file_name")
                and task.file_name
                and task.file_name.endswith((".png", ".jpg", ".jpeg"))
            ):
                task_message = MultiModalMessage(
                    content=[
                        task_question,
                        AGImage.from_pil(Image.open(task.file_name)),
                    ],
                    source="user",
                )
            else:
                task_message = TextMessage(content=task_question, source="user")
            # Step 4: Run the team on the task with explicit timeout wrapper
            # Dynamic timeout calculation for SentinelBench duration-based tasks
            timeout_seconds = self._calculate_dynamic_timeout(task)
            last_message_str = ""
            try:
                if self.pretty_output:
                    # Use PrettyConsole for formatted output with logging capture
                    async def run_with_pretty_console():
                        nonlocal last_message_str
                        
                        # Create a custom stream processor that captures messages for logging
                        async def message_processor():
                            nonlocal last_message_str  # Ensure we can modify the outer variable
                            async for message in team.run_stream(task=task_message):
                                # Store log events for file saving
                                message_str: str = ""
                                try:
                                    if isinstance(message, TaskResult) or isinstance(
                                        message, CheckpointEvent
                                    ):
                                        yield message  # Pass through without processing
                                        continue
                                    message_str = message.to_text()
                                    last_message_str = message_str  # Store for access outside
                                    # Create log event with source, content and timestamp
                                    log_event = LogEventSystem(
                                        source=message.source,
                                        content=message_str,
                                        timestamp=datetime.datetime.now().isoformat(),
                                        metadata=message.metadata,
                                    )
                                    messages_so_far.append(log_event)
                                except Exception as e:
                                    logger.info(
                                        f"[likely nothing] When creating model_dump of message encountered exception {e}"
                                    )
                                    pass

                                # Save to file (but suppress the verbose logging when using pretty console)
                                if self.verbose:
                                    logger.info(f"Run in progress: {task_id}, message: {message_str}")
                                
                                safe_task_id = task_id.replace("/", "_")
                                async with aiofiles.open(
                                    f"{output_dir}/{safe_task_id}_messages.json", "w"
                                ) as f:
                                    await f.write(
                                        json.dumps([msg.model_dump() for msg in messages_so_far], indent=2)
                                    )
                                
                                yield message  # Pass message to PrettyConsole
                        
                        # Use PrettyConsole to process the stream
                        await PrettyConsole(message_processor(), debug=self.verbose)
                        
                        # After PrettyConsole finishes, extract answer from messages_so_far as fallback
                        # This ensures we get the final answer even if last_message_str wasn't set correctly
                        if not last_message_str and messages_so_far:
                            # Try multiple strategies to find the final answer
                            for message in reversed(messages_so_far):
                                # Strategy 1: Look for final_answer type metadata
                                if (message.source == "Orchestrator" and 
                                    hasattr(message, 'metadata') and 
                                    message.metadata.get('type') == 'final_answer'):
                                    last_message_str = message.content
                                    break
                                # Strategy 2: Look for FINAL ANSWER pattern in any message
                                elif "FINAL ANSWER:" in message.content:
                                    last_message_str = message.content
                                    break
                                # Strategy 3: Look for Final Answer pattern in any message
                                elif message.content.startswith("Final Answer:"):
                                    last_message_str = message.content
                                    break
                    
                    await asyncio.wait_for(run_with_pretty_console(), timeout=timeout_seconds)
                else:
                    # Keep existing logic for backward compatibility
                    async def run_with_timeout():
                        nonlocal last_message_str
                        async for message in team.run_stream(task=task_message):
                            # Store log events
                            message_str: str = ""
                            try:
                                if isinstance(message, TaskResult) or isinstance(
                                    message, CheckpointEvent
                                ):
                                    continue
                                message_str = message.to_text()
                                last_message_str = message_str  # Store for access outside
                                # Create log event with source, content and timestamp
                                log_event = LogEventSystem(
                                    source=message.source,
                                    content=message_str,
                                    timestamp=datetime.datetime.now().isoformat(),
                                    metadata=message.metadata,
                                )
                                messages_so_far.append(log_event)
                            except Exception as e:
                                logger.info(
                                    f"[likely nothing] When creating model_dump of message encountered exception {e}"
                                )
                                pass

                            # save to file
                            logger.info(f"Run in progress: {task_id}, message: {message_str}")
                            
                            # Add console output for verbose mode
                            if self.verbose:
                                print(f"\n🤖 [{message.source}]: {message_str}")
                            
                            safe_task_id = task_id.replace("/", "_")
                            async with aiofiles.open(
                                f"{output_dir}/{safe_task_id}_messages.json", "w"
                            ) as f:
                                await f.write(
                                    json.dumps([msg.model_dump() for msg in messages_so_far], indent=2)
                                )
                    
                    await asyncio.wait_for(run_with_timeout(), timeout=timeout_seconds)
                
                # how the final answer is formatted:  "Final Answer: FINAL ANSWER: Actual final answer"
                
                # Robust answer extraction with multiple fallback strategies
                if last_message_str and last_message_str.startswith("Final Answer:"):
                    answer = last_message_str[len("Final Answer:") :].strip()
                    # remove the "FINAL ANSWER:" part and get the string after it
                    if "FINAL ANSWER:" in answer:
                        answer = answer.split("FINAL ANSWER:")[1].strip()
                else:
                    # Fallback 1: Search messages_so_far for final answer patterns
                    answer_found = False
                    for message in reversed(messages_so_far):
                        content = message.content
                        
                        # Try different final answer patterns
                        if "FINAL ANSWER:" in content:
                            answer = content.split("FINAL ANSWER:")[-1].strip()
                            answer_found = True
                            break
                        elif content.startswith("Final Answer:"):
                            answer_part = content[len("Final Answer:"):].strip()
                            if "FINAL ANSWER:" in answer_part:
                                answer = answer_part.split("FINAL ANSWER:")[-1].strip()
                            else:
                                answer = answer_part
                            answer_found = True
                            break
                    
                    # Fallback 2: If no answer found, set a clear error message
                    if not answer_found:
                        answer = "ERROR: Could not extract final answer from agent responses"
                        logger.error(f"Failed to extract answer for task {task_id}. last_message_str was: '{last_message_str}'")

            except asyncio.TimeoutError:
                logger.warning(f"Task {task_id} timed out after {timeout_seconds} seconds")
                answer = "TIMEOUT: Task execution exceeded time limit"
                # Save timeout message to log
                timeout_log_event = LogEventSystem(
                    source="system",
                    content=f"Task timed out after {timeout_seconds} seconds",
                    timestamp=datetime.datetime.now().isoformat(),
                    metadata={"type": "timeout"},
                )
                messages_so_far.append(timeout_log_event)
                # Save final messages
                safe_task_id = task_id.replace("/", "_")
                async with aiofiles.open(
                    f"{output_dir}/{safe_task_id}_messages.json", "w"
                ) as f:
                    messages_json = [msg.model_dump() for msg in messages_so_far]
                    await f.write(json.dumps(messages_json, indent=2))
            except Exception as e:
                # Handle all other exceptions (browser crashes, agent errors, sentinel failures, etc.)
                logger.error(f"Task {task_id} failed with exception: {type(e).__name__}: {e}")
                answer = f"ERROR: {type(e).__name__} - {str(e)}"
                # Save exception message to log
                error_log_event = LogEventSystem(
                    source="system",
                    content=f"Task failed with exception: {type(e).__name__}: {str(e)}",
                    timestamp=datetime.datetime.now().isoformat(),
                    metadata={"type": "error", "exception_type": type(e).__name__},
                )
                messages_so_far.append(error_log_event)
                # Save final messages
                safe_task_id = task_id.replace("/", "_")
                try:
                    async with aiofiles.open(
                        f"{output_dir}/{safe_task_id}_messages.json", "w"
                    ) as f:
                        messages_json = [msg.model_dump() for msg in messages_so_far]
                        await f.write(json.dumps(messages_json, indent=2))
                except Exception as save_error:
                    logger.error(f"Failed to save messages.json for {task_id}: {save_error}")
                # Re-raise the exception so core.py can save partial_state.json
                raise

            assert isinstance(
                answer, str
            ), f"Expected answer to be a string, got {type(answer)}"

            # save the usage of each of the client in a usage json file
            def get_usage(model_client: ChatCompletionClient) -> Dict[str, int]:
                return {
                    "prompt_tokens": model_client.total_usage().prompt_tokens,
                    "completion_tokens": model_client.total_usage().completion_tokens,
                }

            usage_json = {
                "orchestrator": get_usage(model_client_orch),
                "websurfer": get_usage(model_client_websurfer),
                "coder": get_usage(model_client_coder),
                "file_surfer": get_usage(model_client_file_surfer),
            }
            usage_json["total_without_user_proxy"] = {
                "prompt_tokens": sum(
                    usage_json[key]["prompt_tokens"]
                    for key in usage_json
                    if key != "user_proxy"
                ),
                "completion_tokens": sum(
                    usage_json[key]["completion_tokens"]
                    for key in usage_json
                    if key != "user_proxy"
                ),
            }
            with open(f"{output_dir}/model_tokens_usage.json", "w") as f:
                json.dump(usage_json, f)

            await team.close()
            # Step 5: Prepare the screenshots
            screenshots_paths = []
            # check the directory for screenshots which start with screenshot_raw_
            for file in os.listdir(output_dir):
                if file.startswith("screenshot_raw_"):
                    timestamp = file.split("_")[1]
                    screenshots_paths.append(
                        [timestamp, os.path.join(output_dir, file)]
                    )

            # restrict to last 15 screenshots by timestamp
            screenshots_paths = sorted(screenshots_paths, key=lambda x: x[0])[-15:]
            screenshots_paths = [x[1] for x in screenshots_paths]
            return answer, screenshots_paths

        # Step 6: Return the answer and screenshots
        answer, screenshots_paths = asyncio.run(_runner())
        answer = WebVoyagerCandidate(answer=answer, screenshots=screenshots_paths)
        self.save_answer_to_disk(task_id, answer, output_dir)
        return answer
