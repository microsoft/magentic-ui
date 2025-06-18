import os
import json
import logging
import zipfile
import requests
from typing import List, Dict
from ...benchmark import Benchmark
from ...models import (
    BaseTask,
    BaseEvalResult,
    AllTaskTypes,
    AllCandidateTypes,
    AllEvalResultTypes,
)


class BearcubsBenchmark(Benchmark):
    """
    Loads the Bearcubs dataset from bear-cubs.github.io, stores it locally.
    Benchmark paper: https://arxiv.org/abs/2503.07919
    This benchmark has no evaluation since there are no ground truth answers.
    """

    DATASET_URL = "https://bear-cubs.github.io/BearCubs_20250310.json.zip"
    DATASET_FILE = "BearCubs_20250310.json"

    def __init__(self, name: str = "Bearcubs", data_dir: str | None = None):
        assert data_dir is not None, "data_dir must be provided for Bearcubs"
        super().__init__(name=name, data_dir=data_dir)
        self.eval_result_class = BaseEvalResult

    def download_dataset(self) -> None:
        """
        Download and unzip the dataset into self.data_dir
        """
        assert self.data_dir is not None
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir, exist_ok=True)

        zip_path = os.path.join(self.data_dir, "bearcubs.zip")
        json_path = os.path.join(self.data_dir, self.DATASET_FILE)

        # Skip if json already exists
        if os.path.exists(json_path):
            logging.info(f"[Bearcubs] Dataset already exists at '{json_path}'")
            return

        # Download zip file
        logging.info(f"[Bearcubs] Downloading dataset from '{self.DATASET_URL}'...")
        response = requests.get(self.DATASET_URL)
        response.raise_for_status()

        # Save zip file
        with open(zip_path, "wb") as f:
            f.write(response.content)

        # Extract zip file
        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            zip_ref.extractall(self.data_dir)

        # Remove zip file
        os.remove(zip_path)
        logging.info("[Bearcubs] Dataset downloaded and extracted.")

    def load_dataset(self) -> None:
        """
        Read in the json file and store tasks in self.tasks
        """
        assert self.data_dir is not None
        json_path = os.path.join(self.data_dir, self.DATASET_FILE)

        if not os.path.exists(json_path):
            raise FileNotFoundError(
                f"Could not find {self.DATASET_FILE} in {self.data_dir}. "
                "Make sure you have downloaded the dataset."
            )

        # Load json file
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Create tasks
        self.tasks: Dict[str, BaseTask] = {}
        for id_, item in data.items():
            task = BaseTask(
                id=id_,
                question=item["question"],
                ground_truth="",  # No ground truth answers
                set="test",  # Single test split
            )
            self.tasks[task.id] = task

        logging.info(f"[Bearcubs] Loaded {len(self.tasks)} examples.")

    def get_split_tasks(self, split: str) -> List[str]:
        """
        Returns task IDs for the specified split. Only 'test' split is available.
        """
        if split != "test":
            raise ValueError("Only 'test' split is available for Bearcubs")
        return [task_id for task_id, task in self.tasks.items() if task.set == split]

    def evaluator(
        self, task: AllTaskTypes, candidate: AllCandidateTypes
    ) -> AllEvalResultTypes:
        """
        Raises error since evaluation is not supported for this benchmark.
        """
        raise NotImplementedError(
            "Evaluation is not supported for Bearcubs benchmark as there are no ground truth answers"
        )
