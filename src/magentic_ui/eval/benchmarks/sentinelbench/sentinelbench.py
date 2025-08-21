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
        base_website_path: str = "http://172.25.159.193:5173/",
        task_variants: dict = None,
    ):
        """
        SentinelBench benchmark for monitoring and long-term observation tasks.

        Args:
            name: Name of the benchmark
            data_dir: Directory containing the benchmark data
            base_website_path: The base path of the website to use for the SentinelBench. 
                              Make sure it ends with a slash. Default is 172.25.159.193 for local testing.
            task_variants: Dict of task_id -> list of parameter values. 
                          E.g., {"reactor-easy": [60, 120, 3600]} for different duration values
        """
        assert data_dir is not None, "data_dir must be provided for SentinelBenchBenchmark"
        super().__init__(name=name, data_dir=data_dir)
        self.eval_result_class = BaseEvalResult
        self.base_website_path = base_website_path
        self.task_variants = task_variants or {}
        
        # Default parameter values for known parameterizable tasks
        self.default_params = {
            "reactor-easy": {"duration": 30},  # Default 30s
            # Add other parameterizable SentinelBench tasks here
        }
        
        logging_msg = f"[SentinelBench] Using base website path: {self.base_website_path}"
        if self.base_website_path == "http://172.25.159.193:5173/":
            logging_msg += """
            SentinelBench is currently configured for local testing at 172.25.159.193:5173.
            Make sure you have the SentinelBench website running locally with 'npm run dev -- --host 0.0.0.0' before executing evaluations.
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
            task_id = row["id"]  # type: ignore
            base_url = f"{self.base_website_path}{row['path']}"  # type: ignore
            
            # Build base metadata including all SentinelBench-specific fields
            base_metadata = {
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
                base_metadata["relative_vs_absolute"] = row["relative_vs_absolute"]
            if "adversarial_attacks" in row and row["adversarial_attacks"] is not None:
                base_metadata["adversarial_attacks"] = row["adversarial_attacks"]
            if row.get("failure_tolerance"):
                base_metadata["failure_tolerance"] = row["failure_tolerance"]

            # Check if this task has variants
            if task_id in self.task_variants:
                # Create multiple variants with different parameters
                for param_value in self.task_variants[task_id]:
                    variant_id = f"{task_id}/{param_value}"
                    variant_url = self._build_parameterized_url(base_url, task_id, param_value)
                    
                    # Create variant metadata
                    variant_metadata = base_metadata.copy()
                    variant_metadata["base_task_id"] = task_id
                    variant_metadata["parameter_value"] = param_value
                    
                    # Create the prompt with parameter info
                    prompt = (
                        f"Go to {variant_url} and {row['description']} (Parameter: {param_value}). "
                        "Upon successful completion you may get a password or a code which you should extract."
                    )
                    
                    task = BaseTask(
                        id=variant_id,
                        question=prompt,
                        ground_truth=row["password"],  # type: ignore
                        url_path=variant_url,
                        metadata=variant_metadata,
                        set="test",
                    )
                    self.tasks[variant_id] = task
            else:
                # Create default task (possibly with default parameters)
                if task_id in self.default_params:
                    # Use default parameter value
                    default_value = list(self.default_params[task_id].values())[0]
                    variant_id = f"{task_id}/{default_value}"
                    variant_url = self._build_parameterized_url(base_url, task_id, default_value)
                    
                    # Create variant metadata
                    variant_metadata = base_metadata.copy()
                    variant_metadata["base_task_id"] = task_id
                    variant_metadata["parameter_value"] = default_value
                    
                    prompt = (
                        f"Go to {variant_url} and {row['description']}. "
                        "Upon successful completion you may get a password or a code which you should extract."
                    )
                else:
                    # No parameters, use original
                    variant_id = task_id
                    variant_url = base_url
                    variant_metadata = base_metadata.copy()
                    
                    prompt = (
                        f"Go to {variant_url} and {row['description']}. "
                        "Upon successful completion you may get a password or a code which you should extract."
                    )
                
                task = BaseTask(
                    id=variant_id,
                    question=prompt,
                    ground_truth=row["password"],  # type: ignore
                    url_path=variant_url,
                    metadata=variant_metadata,
                    set="test",
                )
                self.tasks[variant_id] = task

        logging.info(f"[SentinelBench] Loaded {len(self.tasks)} total examples.")

    def _build_parameterized_url(self, base_url: str, task_id: str, param_value) -> str:
        """
        Build URL with parameters for specific SentinelBench tasks.
        """
        if task_id == "reactor-easy":
            return f"{base_url}?duration={param_value}"
        # Add other parameterizable SentinelBench tasks here
        # elif task_id == "monitoring-task":
        #     return f"{base_url}?interval={param_value}"
        else:
            return base_url

    def get_split_tasks(self, split: str, task_id: str = None, base_task: str = None, difficulty: str = None) -> List[str]:
        """
        Returns task IDs for the specified split (only 'test' is available).
        
        Args:
            split: The dataset split (currently only 'test' is available for SentinelBench)
            task_id: Filter to a specific task ID (e.g., 'reactor-easy')
            base_task: Filter to all variants of a base task (e.g., 'reactor')
            difficulty: Filter by difficulty level ('easy', 'medium', 'hard')
        """
        if split != "test":
            raise ValueError("only 'test' split is available for SentinelBench")
        
        filtered_tasks = []
        for task_id_key, task in self.tasks.items():
            if task.set != split:
                continue
                
            # Apply task_id filter (exact match)
            if task_id is not None and task_id_key != task_id:
                continue
                
            # Apply base_task filter (check metadata)
            if base_task is not None and task.metadata.get("base_task") != base_task:
                continue
                
            # Apply difficulty filter (check metadata)
            if difficulty is not None and task.metadata.get("difficulty") != difficulty:
                continue
                
            filtered_tasks.append(task_id_key)
        
        return filtered_tasks

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
