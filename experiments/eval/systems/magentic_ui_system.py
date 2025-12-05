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
from magentic_ui.eval.basesystem import BaseSystem
from magentic_ui.eval.models import BaseTask, BaseCandidate, WebVoyagerCandidate
from magentic_ui.types import CheckpointEvent
from magentic_ui.agents import WebSurfer, CoderAgent, FileSurfer
from magentic_ui.teams import GroupChat
from magentic_ui.tools.playwright.browser import VncDockerPlaywrightBrowser
from magentic_ui.tools.playwright.browser import LocalPlaywrightBrowser
from magentic_ui.tools.playwright.browser.utils import get_available_port


logger = logging.getLogger(__name__)
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
            messages_so_far: List[LogEventSystem] = []

            task_question: str = task.question
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
            termination_condition = TimeoutTermination(
                timeout_seconds=60 * 15
            )  # 15 minutes
            model_context_token_limit = 110000
            # ORCHESTRATOR CONFIGURATION
            orchestrator_config = OrchestratorConfig(
                cooperative_planning=False,
                autonomous_execution=True,
                allow_follow_up_input=False,
                final_answer_prompt=FINAL_ANSWER_PROMPT,
                model_context_token_limit=model_context_token_limit,
                no_overwrite_of_task=True,
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
            if self.use_local_browser:
                browser = LocalPlaywrightBrowser(headless=True)
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
            if not self.web_surfer_only:
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
            # Step 4: Run the team on the task
            async for message in team.run_stream(task=task_message):
                # Store log events
                message_str: str = ""
                try:
                    if isinstance(message, TaskResult) or isinstance(
                        message, CheckpointEvent
                    ):
                        continue
                    message_str = message.to_text()
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
                async with aiofiles.open(
                    f"{output_dir}/{task_id}_messages.json", "w"
                ) as f:
                    # Convert list of logevent objects to list of dicts
                    messages_json = [msg.model_dump() for msg in messages_so_far]
                    await f.write(json.dumps(messages_json, indent=2))
                    await f.flush()  # Flush to disk immediately
                # how the final answer is formatted:  "Final Answer: FINAL ANSWER: Actual final answer"

                if message_str.startswith("Final Answer:"):
                    answer = message_str[len("Final Answer:") :].strip()
                    # remove the "FINAL ANSWER:" part and get the string after it
                    answer = answer.split("FINAL ANSWER:")[1].strip()

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
            async with aiofiles.open(f"{output_dir}/model_tokens_usage.json", "w") as f:
                await f.write(json.dumps(usage_json, indent=2))

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
