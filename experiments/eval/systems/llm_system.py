import asyncio
import json
import os
from typing import List, Tuple, Dict, Any, Optional, Union
from autogen_core import ComponentModel
from autogen_core.models import ChatCompletionClient, SystemMessage, UserMessage
from magentic_ui.eval.basesystem import BaseSystem
from magentic_ui.eval.models import BaseQATask, BaseCandidate

class LLMSystem(BaseSystem):

    default_client_config = {
        "provider": "OpenAIChatCompletionClient",
        "config": {
            "model": "gpt-4o-2024-08-06",
        },
        "max_retries": 10,
    }

    def __init__(self, system_name, endpoint_config=default_client_config, dataset_name:str="SimpleQA"):
        super().__init__(system_name)

        self.endpoint_config = endpoint_config
        self.dataset_name = dataset_name
        self.candidate_class = BaseCandidate

    def get_answer(
        self, task_id: str, task: BaseQATask, output_dir: str
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
            """Asynchronous runner to answer the task and return the answer"""
            task_question = task.format_to_user_message() if hasattr(task, 'format_to_user_message') else task.question
            system_instruction = task.system_instruction if hasattr(task, 'system_instruction') else ""

            def get_model_client(
                endpoint_config: Optional[Union[ComponentModel, Dict[str, Any]]],
            ) -> ChatCompletionClient:
                """
                Loads a ChatCompletionClient from a given endpoint configuration.

                Args:
                    endpoint_config (Optional[Union[ComponentModel, Dict[str, Any]]]):
                        The configuration for the model client.

                Returns:
                    ChatCompletionClient: The loaded model client.
                """
                if endpoint_config is None:
                    return ChatCompletionClient.load_component(
                        self.default_client_config
                    )
                return ChatCompletionClient.load_component(endpoint_config)

            messages = [
                SystemMessage(content=system_instruction),
                UserMessage(content=task_question, source="user"),
            ]
            client = get_model_client(self.endpoint_config)

            response = await client.create(
                messages=messages,
            )

            await client.close()

            answer = response.content
            usage = response.usage

            return answer, usage

        answer, usage = asyncio.run(_runner())
        return BaseCandidate(answer=answer)


            
