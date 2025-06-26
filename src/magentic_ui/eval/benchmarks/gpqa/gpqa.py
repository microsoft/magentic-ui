import re
import os
import logging
import pandas as pd
from ..baseqa import BaseQABenchmark
from ...models import (
    GPQACandidate,
    GPQATask,
    GPQAEvalResult,
    AllTaskTypes,
)
from typing import Dict, List, Union, Optional

from huggingface_hub import snapshot_download  # type: ignore


class GPQABenchmark(BaseQABenchmark):
    DATASET_URL = "hf://datasets/Idavidrein/gpqa/"
    DATASET_REPO_ID = "Idavidrein/gpqa"
    SPLITS = ["diamond", "extended", "main"]
    SYSTEM_INSTRUCTION = (
        "You are a helpful assistant that answers multiple-choice questions. "
        "Return your answer in the format: Answer: X, where X is a single uppercase letter (A, B, C, or D)."
    )

    def __init__(
        self,
        name: str,
        data_dir: Union[str, None] = None,
        tasks: Optional[Dict[str, AllTaskTypes]] = None,
        num_instances: Optional[int] = None,
        system_instruction: str = SYSTEM_INSTRUCTION,
    ):
        super().__init__(name, data_dir, tasks, num_instances)

        self.system_instruction = system_instruction

    def download_dataset(self) -> None:
        """
        Download the dataset into self.data_dir using huggingface_hub.snapshot_download().
        """
        assert self.data_dir is not None, "data_dir must be provided for GPQABenchmark"
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir, exist_ok=True)

        logging.info(f"[GPQABenchmark] Downloading dataset into '{self.data_dir}'...")
        snapshot_download(
            repo_id=self.DATASET_REPO_ID,
            repo_type="dataset",
            local_dir=self.data_dir,
            local_dir_use_symlinks=True,
        )
        logging.info("[GPQABenchmark] Dataset downloaded.")

    def load_dataset(self) -> None:
        """
        Read all the split csvs from the dataset
        """

        split_paths = {  # type: ignore
            split: os.path.join(self.data_dir, f"gpqa_{split}.csv")  # type: ignore
            for split in self.SPLITS
        }

        for split_name, split_path in split_paths.items():  # type: ignore
            if not os.path.exists(split_path):  # type: ignore
                raise FileNotFoundError(f"Dataset file {split_path} does not exist.")

            df = pd.read_csv(split_path)  # type: ignore
            for _, row in df.iterrows():
                self.tasks[row["Record ID"]] = GPQATask(  # type: ignore
                    id=row["Record ID"],  # type: ignore
                    question=row["Question"],  # type: ignore
                    ground_truth=row["Correct Answer"],  # type: ignore
                    options=[  # type: ignore
                        row["Correct Answer"],
                        row["Incorrect Answer 1"],
                        row["Incorrect Answer 2"],
                        row["Incorrect Answer 3"],
                    ],
                    set=split_name,
                    metadata=row.to_dict(),  # type: ignore
                    system_instruction=self.system_instruction,  # type: ignore
                )

        logging.info(
            f"[GPQABenchmark] Loaded {len(self.tasks)} tasks from {self.SPLITS} splits from the dataset."
        )

    def get_split_tasks(self, split: str) -> List[str]:
        assert (
            split in self.SPLITS
        ), f"Invalid split: {split}. Must be one of {self.SPLITS}."
        return [task.id for task in self.tasks.values() if task.set == split]

    def evaluator(self, task: GPQATask, candidate: GPQACandidate) -> GPQAEvalResult:  # type: ignore
        if isinstance(task, Dict):
            task = GPQATask(**task)  # type: ignore
        if isinstance(candidate, Dict):
            candidate = GPQACandidate(**candidate)  # type: ignore

        answer_search_by_format = re.search(
            r"(?i)Answer[ \t]*:[ \t]*\$?([A-D])\$?", candidate.answer
        )
        extracted_answer = (
            answer_search_by_format.group(1) if answer_search_by_format else None
        )

        # Find the correct letter (A/B/C/D) for the ground truth answer
        options = task.options
        ground_truth = task.ground_truth
        try:
            correct_index = options.index(ground_truth)
            correct_letter = "ABCD"[correct_index]
        except (ValueError, IndexError):
            correct_letter = None
            raise ValueError(
                f"Ground truth answer {ground_truth} not found in options {options}"
            )

        score = correct_letter == extracted_answer  # type: ignore
        return GPQAEvalResult(  # type: ignore
            score=score,  # type: ignore
            metadata={
                "ground_truth_answer": task.ground_truth,
                "extracted_answer": extracted_answer,
                "llm_response": candidate.answer,
                "task_id": task.id,
            },
        )
