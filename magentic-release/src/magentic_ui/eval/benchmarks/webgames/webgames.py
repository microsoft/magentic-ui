import os
import logging
import requests
import pandas as pd
from typing import List, Union
from ...benchmark import Benchmark
from ...models import BaseTask, BaseCandidate, BaseEvalResult


class WebGamesBenchmark(Benchmark):
    """
    Loads the WebGames dataset from Hugging Face and evaluates predictions
    by comparing against the known passwords.
    """

    DATASET_REPO_ID = "convergence-ai/webgames"
    TEST_FILE = "test.jsonl"

    def __init__(
        self,
        name: str = "WebGames",
        data_dir: Union[str, None] = None,
        base_website_path: str = "https://webgames.convergence.ai/",
    ):
        """
        Benchmark from https://github.com/convergence-ai/webgames

        It is best to host WebGames yourself and set the base_website_path to the url of the hosted website.
        To host WebGames:
            ```bash
            git clone https://github.com/convergence-ai/webgames.git
            cd webgames
            npm install
            npm run dev
            ```
            You will find it http://localhost:5173 and you can pass base_website_path to the benchmark to use your own hosted version.

        Args:
            base_website_path: The base path of the website to use for the WebGamesBenchmark. Make sure it ends with a slash.
        """
        assert data_dir is not None, "data_dir must be provided for WebGamesBenchmark"
        super().__init__(name=name, data_dir=data_dir)
        self.eval_result_class = BaseEvalResult
        self.base_website_path = base_website_path
        logging_msg: str = (
            f"[WebGames] Using base website path: {self.base_website_path}"
        )
        if self.base_website_path == "https://webgames.convergence.ai/":
            logging_msg += """
            You can also run the benchmark with a hosted version of the website by setting the base_website_path to the url of the hosted website.
            To host WebGames:
            ```bash
            git clone https://github.com/convergence-ai/webgames.git
            cd webgames
            npm install
            npm run dev
            ```
            You will find it http://localhost:5173 and you can pass base_website_path to the benchmark to use your own hosted version.
        
            """
        logging.info(logging_msg)

    def download_dataset(self) -> None:
        """
        Download the dataset into self.data_dir using huggingface datasets.
        """
        assert self.data_dir is not None
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir, exist_ok=True)

        logging.info(f"[WebGames] Downloading dataset into '{self.data_dir}'...")

        # Use pandas to download and save the dataset
        df = pd.read_json(  # type: ignore
            f"hf://datasets/{self.DATASET_REPO_ID}/{self.TEST_FILE}", lines=True
        )
        output_path = os.path.join(self.data_dir, self.TEST_FILE)
        df.to_json(output_path, orient="records", lines=True)  # type: ignore

        logging.info("[WebGames] Dataset downloaded.")

    def load_dataset(self) -> None:
        """
        Read in the test.jsonl file and store tasks.
        """
        # Double check that the base website path is valid and is reachable
        try:
            response = requests.get(self.base_website_path)
            response.raise_for_status()
        except Exception as e:
            raise ValueError(
                f"Invalid base website path: {self.base_website_path}"
            ) from e

        assert self.data_dir is not None
        test_path = os.path.join(self.data_dir, self.TEST_FILE)

        if not os.path.isfile(test_path):
            raise FileNotFoundError(
                f"Could not find {self.TEST_FILE} in {self.data_dir}. "
                "Make sure you have downloaded the dataset."
            )

        # Load test set using pandas
        df = pd.read_json(test_path, lines=True)  # type: ignore
        added_instruction: str = "There are no errors in the website. You need to complete the task on this website and follow the instruction untill a password is revealed. A password will only be revealed if you complete the task correctly. Do not navigate away from this website."

        for _, row in df.iterrows():
            task = BaseTask(
                id=row["id"],  # type: ignore
                question=f"{added_instruction}\n\n{row['description']}",  # type: ignore
                ground_truth=row["password"],  # type: ignore
                url_path=f"{self.base_website_path}{row['path']}",  # type: ignore
                metadata={"title": row["title"], "tags": row["tags"]},  # type: ignore
                set="test",
            )
            self.tasks[task.id] = task

        logging.info(f"[WebGames] Loaded {len(self.tasks)} total examples.")

    def get_split_tasks(self, split: str) -> List[str]:
        """
        Returns task IDs for the specified split (only 'test' is available).
        """
        if split != "test":
            raise ValueError("only 'test' split is available for WebGames")
        return [task_id for task_id, task in self.tasks.items() if task.set == split]

    def evaluator(self, task: BaseTask, candidate: BaseCandidate) -> BaseEvalResult:
        """
        Evaluate if the candidate password matches the ground truth password.
        """
        # Cast to proper types if needed
        if isinstance(task, dict):
            task = BaseTask(**task)  # type: ignore
        if isinstance(candidate, dict):
            candidate = BaseCandidate(**candidate)  # type: ignore
        # check if the ground truth password is anywhere in the candidate answer, as a substring
        score = 1.0 if task.ground_truth in candidate.answer else 0.0

        return BaseEvalResult(score=score)
