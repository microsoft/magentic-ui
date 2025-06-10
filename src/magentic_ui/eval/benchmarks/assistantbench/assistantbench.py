import os
import json
import logging
from typing import List, Union
from huggingface_hub import snapshot_download  # type: ignore
from ...benchmark import Benchmark
from .evaluate_utils.assistantbench_evaluator import ab_question_scorer  # type: ignore
from ...models import (
    AssistantBenchTask,
    AssistantBenchCandidate,
    AssistantBenchEvalResult,
    AllTaskTypes,
    AllCandidateTypes,
    AllEvalResultTypes,
)


class AssistantBenchBenchmark(Benchmark):
    """
    Loads the AssistantBench dataset from Hugging Face, stores it locally,
    and evaluates predictions using the question_scorer function.
    """

    DATASET_REPO_ID = "AssistantBench/AssistantBench"
    DEV_FILE = "assistant_bench_v1.0_dev.jsonl"
    TEST_FILE = "assistant_bench_v1.0_test.jsonl"

    def __init__(self, name: str = "AssistantBench", data_dir: Union[str, None] = None):
        assert (
            data_dir is not None
        ), "data_dir must be provided for AssistantBenchBenchmark"
        super().__init__(name=name, data_dir=data_dir)
        self.eval_result_class = AssistantBenchEvalResult

    def download_dataset(self) -> None:
        """
        Download the dataset into self.data_dir using huggingface_hub.snapshot_download().
        """
        assert (
            self.data_dir is not None
        ), "data_dir must be provided for AssistantBenchBenchmark"
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir, exist_ok=True)

        logging.info(f"[AssistantBench] Downloading dataset into '{self.data_dir}'...")
        snapshot_download(
            repo_id=self.DATASET_REPO_ID,
            repo_type="dataset",
            local_dir=self.data_dir,
            local_dir_use_symlinks=True,
        )
        logging.info("[AssistantBench] Dataset downloaded.")

    def load_dataset(self) -> None:
        """
        Read in the dev/test .jsonl files and store them in self.tasks.
        """
        assert self.data_dir is not None
        dev_path = os.path.join(self.data_dir, self.DEV_FILE)
        test_path = os.path.join(self.data_dir, self.TEST_FILE)

        if not os.path.isfile(dev_path) or not os.path.isfile(test_path):
            raise FileNotFoundError(
                f"Could not find {self.DEV_FILE} or {self.TEST_FILE} in {self.data_dir}. "
                "Make sure you have downloaded the dataset."
            )

        # Load dev set
        with open(dev_path, "r", encoding="utf-8") as f:
            for line in f:
                example = json.loads(line)
                task = AssistantBenchTask(
                    id=example["id"],
                    question=example["task"],
                    ground_truth=str(example.get("answer", "")),
                    difficulty=str(example.get("difficulty", "")),
                    explanation=str(example.get("explanation", "")),
                    metadata={"metadata": str(example.get("metadata", ""))},
                    gold_url=str(example.get("gold_url", "")),
                    set="dev",
                )
                self.tasks[task.id] = task

        # Load test set
        with open(test_path, "r", encoding="utf-8") as f:
            for line in f:
                example = json.loads(line)
                task = AssistantBenchTask(
                    id=example["id"],
                    question=example["task"],
                    ground_truth=str(example.get("answer", "")),
                    difficulty=str(example.get("difficulty", "")),
                    explanation=str(example.get("explanation", "")),
                    metadata={"metadata": str(example.get("metadata", ""))},
                    gold_url=str(example.get("gold_url", "")),
                    set="test",
                )
                self.tasks[task.id] = task
        logging.info(f"[AssistantBench] Loaded {len(self.tasks)} total examples.")

    def get_split_tasks(self, split: str) -> List[str]:
        """
        Returns task IDs for the specified set (e.g. 'dev' or 'test').
        """
        if split not in ["dev", "test"]:
            raise ValueError("split must be 'dev' or 'test'")
        return [task_id for task_id, task in self.tasks.items() if task.set == split]

    def evaluator(
        self, task: AllTaskTypes, candidate: AllCandidateTypes
    ) -> AllEvalResultTypes:
        """
        Evaluate how 'correct' the candidate answer is relative to the gold_answer.
        """
        if isinstance(task, dict):
            task = AssistantBenchTask(**task)  # type: ignore
        if isinstance(candidate, dict):
            candidate = AssistantBenchCandidate(**candidate)  # type: ignore

        score = ab_question_scorer(
            prediction=candidate.answer, gold_answer=task.ground_truth
        )
        assert isinstance(score, float)
        return AssistantBenchEvalResult(score=score)
