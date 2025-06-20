import asyncio
import re
import ast
import os
import logging
import pandas as pd
import requests
from ...baseqa import BaseQABenchmark
from ...utils import get_id_for_str
from ...models import (
    SimpleQATask,
    SimpleQACandidate,
    SimpleQAEvalResult,
    AllTaskTypes,
    AllCandidateTypes,
)
from .prompts import EVALUATOR_INSTRUCTION
from typing import Dict, List, Tuple, Any, Union, Optional
from autogen_core.models import UserMessage, ChatCompletionClient


class SimpleQABenchmark(BaseQABenchmark):
    CHOICES = ["A", "B", "C"]
    DATASET_URL = (
        "https://openaipublic.blob.core.windows.net/simple-evals/simple_qa_test_set.csv"
    )
    FILE_NAME = "simple_qa_test_set.csv"
    SYSTEM_INSTRUCTION = """You are a helpful assistant that answers questions."""
    EVALUATOR_INSTRUCTION = EVALUATOR_INSTRUCTION
    EVALUATOR_KWARGS = {
        "provider": "OpenAIChatCompletionClient",
        "config": {
            "model": "gpt-4o-2024-08-06",
        },
        "max_retries": 10,
    }

    def __init__(
        self,
        name: str,
        data_dir: Union[str, None] = None,
        tasks: Optional[Dict[str, AllTaskTypes]] = None,
        num_instances=None,  # type: ignore
        evaluator_kwargs: Dict = None,  # type: ignore
        system_instruction: str = SYSTEM_INSTRUCTION,
    ):
        super().__init__(name, data_dir, tasks, num_instances)  # type: ignore

        self.file_path = (  # type: ignore
            os.path.join(self.data_dir, self.FILE_NAME) if data_dir else self.FILE_NAME  # type: ignore
        )
        self.evaluator_kwargs = (  # type: ignore
            evaluator_kwargs if evaluator_kwargs is not None else self.EVALUATOR_KWARGS  # type: ignore
        )
        self.system_instruction = system_instruction

        self._load_evaluator_client(self.evaluator_kwargs)  # type: ignore

    def _load_evaluator_client(self, kwargs: Dict[str, Any]) -> None:  # type: ignore
        """
        Load the evaluator for the benchmark.
        This method is called by the base class to set up the evaluator.
        """
        self.evaluator_client = ChatCompletionClient.load_component(kwargs)  # type: ignore

    def download_dataset(self) -> None:
        """
        Download the dataset for the benchmark.
        """
        assert (
            self.data_dir is not None
        ), "data_dir must be provided for SimpleQABenchmark"
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir, exist_ok=True)

        logging.info(
            f"[SimpleQABenchmark] Downloading dataset into '{self.data_dir}'..."
        )

        # download the dataset
        if not os.path.exists(self.file_path):  # type: ignore
            response = requests.get(self.DATASET_URL)
            if response.status_code == 200:
                with open(self.file_path, "wb") as f:  # type: ignore
                    f.write(response.content)
                logging.info(
                    "[SimpleQABenchmark] Dataset downloaded successfully. Skipping..."
                )
            else:
                logging.error(
                    f"[SimpleQABenchmark] Failed to download dataset: {response.status_code}"
                )

    def load_dataset(self) -> None:
        """Load the dataset"""
        assert (
            self.data_dir is not None
        ), "data_dir must be provided for SimpleQABenchmark"
        if not os.path.isfile(self.file_path):  # type: ignore
            dataset = pd.read_csv(self.DATASET_URL)  # type: ignore
        else:
            dataset = pd.read_csv(self.file_path)  # type: ignore

        if self.num_instances is not None:  # type: ignore
            dataset = dataset.head(self.num_instances)

        logging.info(
            f"[SimpleQABenchmark] Dataset with {len(dataset)} loaded successfully."
        )

        instances = [row.to_dict() for _, row in dataset.iterrows()]  # type: ignore
        # The dataset does not have IDs with each row, so we generate them
        ids = map(get_id_for_str, map(str, instances))  # type: ignore

        tasks = dict(zip(ids, instances))  # type: ignore

        for id, instance in tasks.items():  # type: ignore
            formatted_question, formatted_ground_truth, metadata = (
                self._format_instance(instance)  # type: ignore
            )
            task = SimpleQATask(
                id=id,
                question=formatted_question,
                ground_truth=formatted_ground_truth,
                set="test",
                metadata=metadata,
                system_instruction=self.system_instruction,
            )
            self.tasks[id] = task

    def _format_instance(self, task: Dict[str, Any]) -> Tuple[str, str, Dict[str, str]]:
        """Format the instance into a string for the benchmark

        Args:
            task (dict): The task instance from the dataset.

        Returns:
            Tuple[str, str, Dict[str, str]]: A tuple containing the formatted question,
            ground truth answer, and metadata.
        """

        question: str = task["problem"].strip()  # type: ignore
        ground_truth: str = task["answer"].strip()  # type: ignore
        metadata = task.get("metadata", {})  # type: ignore
        if isinstance(metadata, str):
            metadata = {"metadata": ast.literal_eval(metadata.strip())}

        return question, ground_truth, metadata

    def get_split_tasks(self, split: str) -> List[str]:
        """
        Returns task IDs for the specified set (e.g. 'dev' or 'test').
        Since SimpleQA only has a test set, we return all tasks.
        """
        if split not in ["test"]:
            raise ValueError("split must be 'test'")
        return list(self.tasks.keys())

    def evaluator(
        self, task: AllTaskTypes, candidate: AllCandidateTypes
    ) -> SimpleQAEvalResult:
        if isinstance(task, Dict):
            task = SimpleQATask(**task)  # type: ignore
        if isinstance(candidate, Dict):
            candidate = SimpleQACandidate(**candidate)  # type: ignore

        eval_prompt = self.EVALUATOR_INSTRUCTION.format(
            question=task.question, target=task.ground_truth, answer=candidate.answer
        )

        evaluator_response = asyncio.run(
            self.evaluator_client.create(
                UserMessage(content=eval_prompt, source="user")  # type: ignore
            )
        )

        match = re.search(r"(A|B|C)", evaluator_response.content)  # type: ignore
        llm_answer = match.group(1) if match else "C"  # type: ignore

        score = int(llm_answer == "A")  # type: ignore
        metadata = {
            "is_correct": score == 1,
            "is_incorrect": int(llm_answer == "B"),  # type: ignore
            "is_not_attempted": int(llm_answer == "C"),  # type: ignore
        }

        return SimpleQAEvalResult(score=score, metadata=metadata)
