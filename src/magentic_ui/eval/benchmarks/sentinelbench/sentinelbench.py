import os
import logging
import requests
import pandas as pd
from typing import List, Union, Dict, Optional, Any
from ...benchmark import Benchmark
from ...models import BaseTask, BaseCandidate, BaseEvalResult
from .task_variants import SENTINELBENCH_DEFAULT_PARAMS, DURATION_TASKS, COUNT_TASKS


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
        base_website_path: str = "https://sentinel-bench.vercel.app/",
        task_variants: Optional[Dict[str, List[Union[int, float]]]] = None,
    ):
        """
        SentinelBench benchmark for monitoring and long-term observation tasks.

        Args:
            name: Name of the benchmark
            data_dir: Directory containing the benchmark data
            base_website_path: The base path of the website to use for the SentinelBench.
                              Make sure it ends with a slash. Defaults to https://sentinel-bench.vercel.app/
            task_variants: Dict of task_id -> list of parameter values.
                          E.g., {"reactor-easy": [60, 120, 3600]} for different duration values
        """
        assert (
            data_dir is not None
        ), "data_dir must be provided for SentinelBenchBenchmark"
        super().__init__(name=name, data_dir=data_dir)
        self.eval_result_class = BaseEvalResult
        self.base_website_path = base_website_path
        self.task_variants = task_variants or {}
        self.default_params = SENTINELBENCH_DEFAULT_PARAMS

        logging.info(
            f"[SentinelBench] Using base website path: {self.base_website_path}"
        )
        logging.info(
            "[SentinelBench] Make sure the SentinelBench website is running and accessible at the provided URL before executing evaluations."
        )

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
                logging.info(
                    f"[SentinelBench] Copying dataset from {fallback_path} to {test_file}"
                )
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
        except requests.HTTPError as e:
            logging.warning(
                f"HTTP error when checking base website path: {self.base_website_path}. "
                f"Status code: {e.response.status_code if e.response else 'unknown'}. Error: {e}"
            )
        except (requests.ConnectionError, requests.Timeout) as e:
            logging.warning(
                f"Could not reach base website path: {self.base_website_path}. "
                f"Make sure SentinelBench is running locally. Error: {e}"
            )
        except requests.RequestException as e:
            logging.warning(
                f"Request error when checking base website path: {self.base_website_path}. "
                f"Error: {e}"
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

        for _, row in df.iterrows():
            # Cast pandas Series to dict to avoid type issues
            row_dict: Dict[str, Any] = row.to_dict()  # type: ignore
            task_id = str(row_dict["id"])
            base_url = f"{self.base_website_path}{str(row_dict['path'])}"
            logging.info(
                f"[DEBUG] Processing task from dataset: id='{task_id}', path='{str(row_dict['path'])}', base_task='{str(row_dict.get('base_task', 'N/A'))}'"
            )

            # Build base metadata including all SentinelBench-specific fields
            base_metadata: Dict[str, Any] = {
                "title": str(row_dict["title"]),
                "tags": str(row_dict["tags"]),
                "icon": str(row_dict.get("icon", "")),
                "difficulty": str(row_dict.get("difficulty", "")),
                "base_task": str(row_dict.get("base_task", "")),
                "duration": str(row_dict.get("duration", "")),
                "criteria": str(row_dict.get("criteria", "")),
                "activity": str(row_dict.get("activity", "")),
                "noise": str(row_dict.get("noise", "")),
                "realism": str(row_dict.get("realism", "")),
            }

            # Add optional fields if they exist and are not empty
            if row_dict.get("relative_vs_absolute"):
                base_metadata["relative_vs_absolute"] = str(
                    row_dict["relative_vs_absolute"]
                )
            if (
                "adversarial_attacks" in row_dict
                and row_dict["adversarial_attacks"] is not None
            ):
                base_metadata["adversarial_attacks"] = str(
                    row_dict["adversarial_attacks"]
                )
            if row_dict.get("failure_tolerance"):
                base_metadata["failure_tolerance"] = str(row_dict["failure_tolerance"])

            # Check if this task has variants
            if task_id in self.task_variants:
                logging.info(
                    f"[DEBUG] Task '{task_id}' has variants: {self.task_variants[task_id]}"
                )
                # Create multiple variants with different parameters
                for param_value in self.task_variants[task_id]:
                    variant_id = f"{task_id}/{param_value}"
                    variant_url = self._build_parameterized_url(
                        base_url, task_id, param_value
                    )
                    logging.info(
                        f"[DEBUG] Creating variant: id='{variant_id}', url='{variant_url}'"
                    )

                    # Create variant metadata
                    variant_metadata: Dict[str, Any] = base_metadata.copy()
                    variant_metadata["base_task_id"] = task_id
                    variant_metadata["parameter_value"] = param_value

                    # Create the prompt with parameter info
                    prompt = (
                        f"You are already on the correct page for this task. {str(row_dict['description'])}. "
                        "All required information and functionality is available on this current page. "
                        "Do not navigate away from this page or open new tabs. "
                        "Upon successful completion you may find a password or a code somewhere on the page, which you should return. "
                        "This password or code is not sensitive and will be only used to test your ability to complete the task."
                    )

                    task = BaseTask(
                        id=variant_id,
                        question=prompt,
                        ground_truth=str(row_dict["password"]),
                        url_path=variant_url,
                        metadata=variant_metadata,
                        set="test",
                    )
                    self.tasks[variant_id] = task
                    logging.info(f"[DEBUG] Added task to self.tasks: '{variant_id}'")
            else:
                logging.info(
                    f"[DEBUG] Task '{task_id}' NOT in task_variants, checking default_params"
                )
                # ALL tasks must have default parameters - use them
                if task_id in self.default_params:
                    logging.info(
                        f"[DEBUG] Task '{task_id}' has default params: {self.default_params[task_id]}"
                    )
                    # Use default parameter value
                    default_value = list(self.default_params[task_id].values())[0]
                    variant_id = f"{task_id}/{default_value}"
                    variant_url = self._build_parameterized_url(
                        base_url, task_id, default_value
                    )
                    logging.info(
                        f"[DEBUG] Creating default variant: id='{variant_id}', url='{variant_url}'"
                    )

                    # Create variant metadata
                    variant_metadata: Dict[str, Any] = base_metadata.copy()
                    variant_metadata["base_task_id"] = task_id
                    variant_metadata["parameter_value"] = default_value

                    prompt = (
                        f"You are already on the correct page for this task. {str(row_dict['description'])}. "
                        "All required information and functionality is available on this current page. "
                        "Do not navigate away from this page or open new tabs. "
                        "Upon successful completion you may get a password or a code which you should extract."
                    )
                else:
                    # ERROR: ALL tasks should have default params defined
                    raise ValueError(
                        f"Task '{task_id}' has no variants and no default params defined. All tasks must have default parameters in self.default_params."
                    )

                task = BaseTask(
                    id=variant_id,
                    question=prompt,
                    ground_truth=str(row_dict["password"]),
                    url_path=variant_url,
                    metadata=variant_metadata,
                    set="test",
                )
                self.tasks[variant_id] = task
                logging.info(f"[DEBUG] Added task to self.tasks: '{variant_id}'")

        logging.info(f"[SentinelBench] Loaded {len(self.tasks)} total examples.")

    def _build_parameterized_url(
        self, base_url: str, task_id: str, param_value: Union[int, float]
    ) -> str:
        """
        Build URL with parameters for specific SentinelBench tasks.
        """
        # Duration-based tasks (time in seconds)
        if task_id in DURATION_TASKS:
            return f"{base_url}?duration={param_value}"

        # Count-based tasks (number of items/actions)
        elif task_id in COUNT_TASKS:
            return f"{base_url}?count={param_value}"

        # No parameters for other tasks
        else:
            return base_url

    def get_split_tasks(
        self,
        split: str,
        task_id: Optional[str] = None,
        base_task: Optional[str] = None,
        difficulty: Optional[str] = None,
    ) -> List[str]:
        """
        Returns task IDs for the specified split (only 'test' is available).

        Args:
            split: The dataset split (currently only 'test' is available for SentinelBench)
            task_id: Filter to a specific task ID (e.g., 'reactor-easy')
            base_task: Filter to all variants of a base task (e.g., 'reactor')
            difficulty: Filter by difficulty level ('easy', 'medium', 'hard')
        """
        logging.info(
            f"[DEBUG] get_split_tasks called with: split='{split}', task_id='{task_id}', base_task='{base_task}', difficulty='{difficulty}'"
        )
        logging.info(f"[DEBUG] Total tasks available: {len(self.tasks)}")

        if split != "test":
            raise ValueError("only 'test' split is available for SentinelBench")

        filtered_tasks: List[str] = []
        for task_id_key, task in self.tasks.items():
            logging.info(
                f"[DEBUG] Checking task: '{task_id_key}', set='{task.set}', metadata.base_task='{task.metadata.get('base_task')}', metadata.difficulty='{task.metadata.get('difficulty')}'"
            )

            if task.set != split:
                logging.info(
                    f"[DEBUG] Skipping '{task_id_key}' - wrong split ('{task.set}' != '{split}')"
                )
                continue

            # Apply task_id filter (exact match)
            if task_id is not None and task_id_key != task_id:
                logging.info(
                    f"[DEBUG] Skipping '{task_id_key}' - task_id filter ('{task_id_key}' != '{task_id}')"
                )
                continue

            # Apply base_task filter (check metadata)
            if base_task is not None and task.metadata.get("base_task") != base_task:
                logging.info(
                    f"[DEBUG] Skipping '{task_id_key}' - base_task filter ('{task.metadata.get('base_task')}' != '{base_task}')"
                )
                continue

            # Apply difficulty filter (check metadata)
            if difficulty is not None and task.metadata.get("difficulty") != difficulty:
                logging.info(
                    f"[DEBUG] Skipping '{task_id_key}' - difficulty filter ('{task.metadata.get('difficulty')}' != '{difficulty}')"
                )
                continue

            logging.info(
                f"[DEBUG] Task '{task_id_key}' PASSED all filters - adding to filtered_tasks"
            )
            filtered_tasks.append(task_id_key)

        logging.info(
            f"[DEBUG] get_split_tasks returning {len(filtered_tasks)} tasks: {filtered_tasks}"
        )
        return filtered_tasks

    def evaluator(self, task: BaseTask, candidate: BaseCandidate) -> BaseEvalResult:
        """
        Evaluate if the candidate password matches the ground truth password.
        Uses substring matching like WebGames.
        For ALL tasks, appends the parameter value to the expected password.
        """
        # Cast to proper types if needed
        if isinstance(task, dict):
            task = BaseTask(**task)  # type: ignore
        if isinstance(candidate, dict):
            candidate = BaseCandidate(**candidate)  # type: ignore

        # Get the expected password
        expected_password = task.ground_truth

        # For ALL tasks, append the parameter value if available
        if (
            hasattr(task, "metadata")
            and task.metadata
            and "parameter_value" in task.metadata
        ):
            parameter_value = task.metadata["parameter_value"]
            expected_password = f"{expected_password}_{parameter_value}"

        # Check if the expected password is anywhere in the candidate answer, as a substring
        score = 1.0 if expected_password in candidate.answer else 0.0

        return BaseEvalResult(score=score)
