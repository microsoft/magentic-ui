import os
import json
import re
import logging
from typing import Union, List, Dict
from huggingface_hub import snapshot_download  # type: ignore
from ...benchmark import Benchmark
from ...models import (
    GaiaTask,
    GaiaCandidate,
    GaiaEvalResult,
    AllTaskTypes,
    AllCandidateTypes,
    AllEvalResultTypes,
)


def normalize_answer(a: str) -> str:
    # ...existing code...
    norm_answer = ", ".join(a.strip().lower().split(","))
    norm_answer = re.sub(r"[\.\!\?]+$", "", re.sub(r"\s+", " ", norm_answer))
    return norm_answer


def gaia_evaluator(expected_answer: str, final_answer: str) -> float:
    n_ex = normalize_answer(expected_answer)
    n_final = normalize_answer(final_answer)
    return 1.0 if n_ex != "" and n_ex == n_final else 0.0


class GaiaBenchmark(Benchmark):
    """
    Loads the GAIA dataset from Hugging Face, stores it locally,
    and evaluates predictions using the gaia_evaluator function.
    """

    DATASET_REPO_ID = "gaia-benchmark/GAIA"
    VALIDATION_FILE = "2023/validation/metadata.jsonl"
    TEST_FILE = "2023/test/metadata.jsonl"

    def __init__(
        self,
        name: str = "Gaia",
        data_dir: Union[str, None] = None,
        add_file_name_to_task: bool = True,
    ):
        assert data_dir is not None, "data_dir must be provided for GaiaBenchmark"
        super().__init__(name=name, data_dir=data_dir)
        self.eval_result_class = GaiaEvalResult
        # if true, add the file_name to the task question string
        self.add_file_name_to_task = add_file_name_to_task

    def download_dataset(self):
        """
        Download the dataset into self.data_dir using huggingface_hub.snapshot_download().
        """
        assert self.data_dir is not None
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir, exist_ok=True)
        logging.info(f"[GAIA] Downloading dataset into '{self.data_dir}'...")
        snapshot_download(
            repo_id=self.DATASET_REPO_ID,
            repo_type="dataset",
            local_dir=self.data_dir,
            local_dir_use_symlinks=True,
        )
        logging.info("[GAIA] Dataset downloaded.")

    def load_dataset(self):
        """
        Read in the validation/test .jsonl files and store them in self.tasks.
        """
        assert self.data_dir is not None
        validation_path = os.path.join(self.data_dir, self.VALIDATION_FILE)
        test_path = os.path.join(self.data_dir, self.TEST_FILE)

        if not os.path.isfile(validation_path) or not os.path.isfile(test_path):
            raise FileNotFoundError(
                f"Could not find {self.VALIDATION_FILE} or {self.TEST_FILE} in {self.data_dir}. "
                "Make sure you have downloaded the dataset."
            )

        self.tasks: Dict[str, GaiaTask] = {}

        # Load validation set
        with open(validation_path, "r", encoding="utf-8") as f:
            for line in f:
                example = json.loads(line)
                if self.add_file_name_to_task and example.get("file_name", "") != "":
                    question: str = f"{example['Question']}\nAttached file name in current directory: {example['file_name']}"
                else:
                    question: str = example["Question"]
                file_name: str = ""
                if example.get("file_name", "") != "":
                    file_name = os.path.join(
                        self.data_dir,
                        "2023/validation",
                        example["file_name"],
                    )
                task = GaiaTask(
                    id=example["task_id"],
                    question=question,
                    ground_truth=example.get("Final answer", ""),
                    difficulty=str(example.get("Level", "")),
                    metadata=dict(example.get("Annotator Metadata", {})),
                    file_name=file_name,
                    set=f"validation-{example['Level']}",
                )
                self.tasks[task.id] = task

        # Load test set
        with open(test_path, "r", encoding="utf-8") as f:
            for line in f:
                example = json.loads(line)
                if self.add_file_name_to_task and example.get("file_name", "") != "":
                    question: str = f"{example['Question']}\nAttached file name in current directory: {example['file_name']}"
                else:
                    question: str = example["Question"]
                file_name: str = ""
                if example.get("file_name", "") != "":
                    file_name = os.path.join(
                        self.data_dir,
                        "2023/test",
                        example["file_name"],
                    )
                task = GaiaTask(
                    id=example["task_id"],
                    question=question,
                    ground_truth=example.get("Final answer", ""),
                    difficulty=str(example.get("Level", "")),
                    metadata=dict(example.get("Annotator Metadata", {})),
                    file_name=file_name,
                    set=f"test-{example['Level']}",
                )
                self.tasks[task.id] = task

        logging.info(f"[GAIA] Loaded {len(self.tasks)} total tasks.")

    def get_split_tasks(self, split: str) -> List[str]:
        """
        Returns task IDs for the specified set.
        """
        if split not in [
            "validation-1",
            "validation-2",
            "validation-3",
            "validation",
            "test",
            "test-1",
            "test-2",
            "test-3",
        ]:
            raise ValueError(
                "split must be one of 'validation-1', 'validation-2', 'validation-3', 'test-1', 'test-2', 'test-3', 'validation', 'test'"
            )

        if split == "validation":
            split_tasks = [
                "validation-1",
                "validation-2",
                "validation-3",
            ]
        elif split == "test":
            split_tasks = [
                "test-1",
                "test-2",
                "test-3",
            ]
        else:
            split_tasks = [split]

        return [
            task_id for task_id, task in self.tasks.items() if task.set in split_tasks
        ]

    def evaluator(
        self, task: AllTaskTypes, candidate: AllCandidateTypes
    ) -> AllEvalResultTypes:
        """
        Evaluate how 'correct' the candidate answer is relative to the gold_answer.
        """
        # cast to GaiaTask and GaiaCandidate if dicts
        if isinstance(task, dict):
            task = GaiaTask(**task)  # type: ignore
        if isinstance(candidate, dict):
            candidate = GaiaCandidate(**candidate)  # type: ignore
        score = gaia_evaluator(
            expected_answer=task.ground_truth, final_answer=candidate.answer
        )
        return GaiaEvalResult(score=score)
