"""
SimpleQA: Measuring short-form factuality in large language models
Authors: Jason Wei, Nguyen Karina, Hyung Won Chung, Yunxin Joy Jiao, Spencer Papay, Amelia Glaese, John Schulman, William Fedus
https://cdn.openai.com/papers/simpleqa.pdf
"""

import json
import ast
import os
import logging
import pandas as pd
import requests
from ...baseqa import BaseQABenchmark
from ...utils import get_id_for_str
from ...evaluators import llm_evaluate_candidate_answer
from ...models import (
    SimpleQATask,
    SimpleQACandidate,
    SimpleQAEvalResult,
    AllTaskTypes,
    AllCandidateTypes,
)
from typing import Dict, List, Tuple

import openai


class SimpleQABenchmark(BaseQABenchmark):
    CHOICES = ["A", "B", "C"]
    DATASET_URL = (
        "https://openaipublic.blob.core.windows.net/simple-evals/simple_qa_test_set.csv"
    )
    FILE_NAME = "simple_qa_test_set.csv"
    SYSTEM_INSTRUCTION = """You are a helpful assistant that answers questions."""

    def __init__(
        self,
        name,
        data_dir=None,
        tasks=None,
        num_instances=None,
        evaluator_kwargs: Dict = None,
        system_instruction: str = SYSTEM_INSTRUCTION,
    ):
        super().__init__(name, data_dir, tasks, num_instances)

        self.file_path = (
            os.path.join(self.data_dir, self.FILE_NAME) if data_dir else self.FILE_NAME
        )
        self.evaluator_kwargs = evaluator_kwargs if evaluator_kwargs is not None else {}
        self.system_instruction = system_instruction

        self._load_evaluator_client(**self.evaluator_kwargs)

    def _load_evaluator_client(self, **kwargs) -> None:
        """
        Load the evaluator for the benchmark.
        This method is called by the base class to set up the evaluator.
        """
        self.evaluator_client = openai.OpenAI(**kwargs)

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
        if not os.path.exists(self.file_path):
            response = requests.get(self.DATASET_URL)
            if response.status_code == 200:
                with open(self.file_path, "wb") as f:
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
        if not os.path.isfile(self.file_path):
            dataset = pd.read_csv(self.DATASET_URL)
        else:
            dataset = pd.read_csv(self.file_path)

        if self.num_instances is not None:
            dataset = dataset.head(self.num_instances)

        logging.info(
            f"[SimpleQABenchmark] Dataset with {len(dataset)} loaded successfully."
        )

        instances = [row.to_dict() for _, row in dataset.iterrows()]
        # The dataset does not have IDs with each row, so we generate them
        ids = map(get_id_for_str, map(str, instances))

        tasks = dict(zip(ids, instances))

        for id, instance in tasks.items():
            formatted_question, formatted_ground_truth, metadata = self.format_instance(
                instance
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

    def format_instance(self, task: Dict) -> Tuple[str, str, Dict[str, str]]:
        """Format the instance into a string for the benchmark

        Args:
            task (dict): The task instance from the dataset.

        Returns:
            Tuple[str, str, Dict[str, str]]: A tuple containing the formatted question,
            ground truth answer, and metadata.
        """

        question: str = task["problem"].strip()
        ground_truth: str = task["answer"].strip()
        metadata = task.get("metadata", {})
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
            task = SimpleQATask(**task)
        if isinstance(candidate, Dict):
            candidate = SimpleQACandidate(**candidate)

        score = llm_evaluate_candidate_answer(
            prediction=candidate.answer,
            ground_truth=task.ground_truth,
            model_client=self.evaluator_client,
        )

        return SimpleQAEvalResult(score=score, metadata={})
