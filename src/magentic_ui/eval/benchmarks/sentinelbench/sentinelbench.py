import os
import logging
import requests
import pandas as pd
from typing import List, Union
from ...benchmark import Benchmark
from ...models import BaseTask, BaseCandidate, BaseEvalResult


class SentinelBenchBenchmark(Benchmark):
    """
    Loads the SentinelBench dataset and evaluates predictions
    by comparing against the known passwords.
    
    SentinelBench focuses on evaluating AI agents' capabilities in:
    - Long-term monitoring and state change detection
    - Persistent interaction and patience
    - Pattern recognition in dynamic environments
    - Task completion under varying noise levels and complexity
    """

    TEST_FILE = "test.jsonl"

    def __init__(
        self,
        name: str = "SentinelBench",
        data_dir: Union[str, None] = None,
        base_website_path: str = "http://localhost:5174/",
    ):
        """
        SentinelBench benchmark for monitoring and long-term observation tasks.

        Args:
            name: Name of the benchmark
            data_dir: Directory containing the benchmark data
            base_website_path: The base path of the website to use for the SentinelBench. 
                              Make sure it ends with a slash. Default is localhost for local testing.
        """
        assert data_dir is not None, "data_dir must be provided for SentinelBenchBenchmark"
        super().__init__(name=name, data_dir=data_dir)
        self.eval_result_class = BaseEvalResult
        self.base_website_path = base_website_path
        
        logging_msg = f"[SentinelBench] Using base website path: {self.base_website_path}"
        if self.base_website_path == "http://localhost:5174/":
            logging_msg += """
            SentinelBench is currently configured for local testing at localhost:5174.
            Make sure you have the SentinelBench website running locally before executing evaluations.
            """
        logging.info(logging_msg)

    def download_dataset(self) -> None:
        """
        For SentinelBench, the dataset is included locally in the repository.
        This method ensures the data directory exists.
        """
        assert self.data_dir is not None
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir, exist_ok=True)
        
        # Check if test.jsonl exists in the expected location
        test_file = os.path.join(self.data_dir, self.TEST_FILE)
        if not os.path.isfile(test_file):
            # Check if it exists in the main data directory (fallback)
            fallback_path = os.path.join(
                os.path.dirname(self.data_dir), "data", "SentinelBench", self.TEST_FILE
            )
            if os.path.isfile(fallback_path):
                logging.info(f"[SentinelBench] Copying dataset from {fallback_path} to {test_file}")
                import shutil
                shutil.copy2(fallback_path, test_file)
            else:
                raise FileNotFoundError(
                    f"SentinelBench dataset not found. Expected at {test_file} or {fallback_path}"
                )
        
        logging.info("[SentinelBench] Dataset ready.")

    def load_dataset(self) -> None:
        """
        Read in the test.jsonl file and store tasks with all metadata fields.
        """
        # Double check that the base website path is valid and is reachable
        try:
            response = requests.get(self.base_website_path, timeout=5)
            response.raise_for_status()
        except Exception as e:
            logging.warning(
                f"Could not reach base website path: {self.base_website_path}. "
                f"Make sure SentinelBench is running locally. Error: {e}"
            )

        assert self.data_dir is not None
        test_path = os.path.join(self.data_dir, self.TEST_FILE)

        if not os.path.isfile(test_path):
            raise FileNotFoundError(
                f"Could not find {self.TEST_FILE} in {self.data_dir}. "
                "Make sure you have the SentinelBench dataset."
            )

        # Load test set using pandas
        df = pd.read_json(test_path, lines=True)  # type: ignore
        added_instruction = (
            "There are no errors in the website. You need to complete the task on this website "
            "and follow the instruction until a password is revealed. A password will only be "
            "revealed if you complete the task correctly. Do not navigate away from this website. "
            "This is a monitoring task that may require patience and persistent observation."
        )

        for _, row in df.iterrows():
            # Build metadata including all SentinelBench-specific fields
            metadata = {
                "title": row["title"],
                "tags": row["tags"],
                "icon": row.get("icon", ""),
                "difficulty": row.get("difficulty", ""),
                "base_task": row.get("base_task", ""),
                "duration": row.get("duration", ""),
                "criteria": row.get("criteria", ""),
                "activity": row.get("activity", ""),
                "noise": row.get("noise", ""),
                "realism": row.get("realism", ""),
            }
            
            # Add optional fields if they exist and are not empty
            if row.get("relative_vs_absolute"):
                metadata["relative_vs_absolute"] = row["relative_vs_absolute"]
            if "adversarial_attacks" in row and row["adversarial_attacks"] is not None:
                metadata["adversarial_attacks"] = row["adversarial_attacks"]
            if row.get("failure_tolerance"):
                metadata["failure_tolerance"] = row["failure_tolerance"]

            task = BaseTask(
                id=row["id"],  # type: ignore
                question=f"{added_instruction}\n\n{row['description']}",  # type: ignore
                ground_truth=row["password"],  # type: ignore
                url_path=f"{self.base_website_path}{row['path']}",  # type: ignore
                metadata=metadata,
                set="test",
            )
            self.tasks[task.id] = task

        logging.info(f"[SentinelBench] Loaded {len(self.tasks)} total examples.")

    def get_split_tasks(self, split: str) -> List[str]:
        """
        Returns task IDs for the specified split (only 'test' is available).
        """
        if split != "test":
            raise ValueError("only 'test' split is available for SentinelBench")
        return [task_id for task_id, task in self.tasks.items() if task.set == split]

    def evaluator(self, task: BaseTask, candidate: BaseCandidate) -> BaseEvalResult:
        """
        Evaluate if the candidate password matches the ground truth password.
        Uses substring matching like WebGames.
        """
        # Cast to proper types if needed
        if isinstance(task, dict):
            task = BaseTask(**task)  # type: ignore
        if isinstance(candidate, dict):
            candidate = BaseCandidate(**candidate)  # type: ignore
        
        # Check if the ground truth password is anywhere in the candidate answer, as a substring
        score = 1.0 if task.ground_truth in candidate.answer else 0.0

        return BaseEvalResult(score=score)
