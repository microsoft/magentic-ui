import asyncio
import json
from typing import Tuple, Dict, Any
from autogen_core.models import ChatCompletionClient, SystemMessage, UserMessage
from ..basesystem import BaseSystem
from ..models import BaseTask, BaseCandidate, BaseQATask


class LLMSystem(BaseSystem):
    def __init__(
        self,
        system_name: str,
        endpoint_config: Dict[str, Any],
        system_instruction: str = "You are a helpful assistant.",
    ):
        """
        A simple system that uses a LLM without tools to answer a question.

        Args:
            system_name (str): The name of the system.
            endpoint_config (dict): The configuration for the model client.
            system_instruction (str): The system instruction to use for the LLM.

        """
        super().__init__(system_name)

        self.endpoint_config = endpoint_config
        self.candidate_class = BaseCandidate
        self.system_instruction = system_instruction

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
            BaseCandidate: An object containing the final answer.
        """

        async def _runner() -> Tuple[str, Dict[str, int]]:
            """Asynchronous runner to answer the task and return the answer"""
            if hasattr(task, "format_to_user_message"):
                assert isinstance(task, BaseQATask), "Task must be a BaseQATask"
                task_question = task.format_to_user_message()
            else:
                task_question = task.question

            if hasattr(task, "system_instruction"):
                assert isinstance(task, BaseQATask), "Task must be a BaseQATask"
                system_instruction = task.system_instruction
            else:
                system_instruction = self.system_instruction

            messages = [
                SystemMessage(content=system_instruction),
                UserMessage(content=task_question, source="user"),
            ]
            client = ChatCompletionClient.load_component(self.endpoint_config)

            response = await client.create(
                messages=messages,
            )

            await client.close()

            answer = response.content
            assert isinstance(answer, str), "Answer must be a string"
            usage = {
                "prompt_tokens": client.total_usage().prompt_tokens,
                "completion_tokens": client.total_usage().completion_tokens,
            }

            return answer, usage

        answer, usage = asyncio.run(_runner())
        with open(f"{output_dir}/model_tokens_usage.json", "w") as f:
            json.dump(usage, f)
        candidate = BaseCandidate(answer=answer)
        self.save_answer_to_disk(task_id, candidate, output_dir)
        return candidate
