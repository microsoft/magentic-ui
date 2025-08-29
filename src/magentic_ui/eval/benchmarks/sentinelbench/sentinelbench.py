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
        base_website_path: str = "http://10.255.255.254:5173/",
        task_variants: dict = None,
    ):
        """
        SentinelBench benchmark for monitoring and long-term observation tasks.

        Args:
            name: Name of the benchmark
            data_dir: Directory containing the benchmark data
            base_website_path: The base path of the website to use for the SentinelBench. 
                              Make sure it ends with a slash. Default is http://10.255.255.254:5173/ for local testing.
            task_variants: Dict of task_id -> list of parameter values. 
                          E.g., {"reactor-easy": [60, 120, 3600]} for different duration values
        """
        assert data_dir is not None, "data_dir must be provided for SentinelBenchBenchmark"
        super().__init__(name=name, data_dir=data_dir)
        self.eval_result_class = BaseEvalResult
        self.base_website_path = base_website_path
        self.task_variants = task_variants or {}
        
        # Default parameter values for known parameterizable tasks
        # All tasks will have easy/medium/hard variants in the final dataset
        self.default_params = {
            # Time-based tasks (duration in seconds) - all variants
            "reactor-easy": {"duration": 30},
            "reactor-medium": {"duration": 30}, 
            "reactor-hard": {"duration": 30},
            "teams-monitor-easy": {"duration": 30},
            "teams-monitor-medium": {"duration": 30},
            "teams-monitor-hard": {"duration": 30},
            "linkedin-monitor-easy": {"duration": 30},
            "linkedin-monitor-medium": {"duration": 30},
            "linkedin-monitor-hard": {"duration": 30},
            "flight-monitor-easy": {"duration": 30},
            "flight-monitor-medium": {"duration": 30},
            "flight-monitor-hard": {"duration": 30},
            "news-checker-easy": {"duration": 30},
            "news-checker-medium": {"duration": 30},
            "news-checker-hard": {"duration": 30},
            "github-watcher-easy": {"duration": 30},
            "github-watcher-medium": {"duration": 30},
            "github-watcher-hard": {"duration": 30},
            
            # Count-based tasks (number of items/actions) - all variants
            # Both use same scaling: [2, 4, 8, 16, 32, 64]
            "animal-mover-easy": {"count": 2},
            "animal-mover-medium": {"count": 2},
            "animal-mover-hard": {"count": 2},
            "button-presser-easy": {"count": 2},
            "button-presser-medium": {"count": 2},
            "button-presser-hard": {"count": 2},
        }
        
        logging_msg = f"[SentinelBench] Using base website path: {self.base_website_path}"
        if self.base_website_path == "http://10.255.255.254:5173/":
            logging_msg += """
            SentinelBench is currently configured for local testing at 10.255.255.254:5173.
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
            logging.info(f"[DEBUG] Processing task from dataset: id='{task_id}', path='{row['path']}', base_task='{row.get('base_task', 'N/A')}'")  # type: ignore
            
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
                logging.info(f"[DEBUG] Task '{task_id}' has variants: {self.task_variants[task_id]}")
                # Create multiple variants with different parameters
                for param_value in self.task_variants[task_id]:
                    variant_id = f"{task_id}/{param_value}"
                    variant_url = self._build_parameterized_url(base_url, task_id, param_value)
                    logging.info(f"[DEBUG] Creating variant: id='{variant_id}', url='{variant_url}'")
                    
                    # Create variant metadata
                    variant_metadata = base_metadata.copy()
                    variant_metadata["base_task_id"] = task_id
                    variant_metadata["parameter_value"] = param_value
                    
                    # Create the prompt with parameter info
                    prompt = (
                        f"You are already on the correct page for this task. {row['description']}. "
                        "All required information and functionality is available on this current page. "
                        "Do not navigate away from this page or open new tabs. "
                        "Upon successful completion you may find a password or a code which you should return. "
                        "The password or code is not sensitive and will be only used to test your ability to complete the task."
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
                    logging.info(f"[DEBUG] Added task to self.tasks: '{variant_id}'")  
            else:
                logging.info(f"[DEBUG] Task '{task_id}' NOT in task_variants, checking default_params")
                # ALL tasks must have default parameters - use them
                if task_id in self.default_params:
                    logging.info(f"[DEBUG] Task '{task_id}' has default params: {self.default_params[task_id]}")
                    # Use default parameter value
                    default_value = list(self.default_params[task_id].values())[0]
                    variant_id = f"{task_id}/{default_value}"
                    variant_url = self._build_parameterized_url(base_url, task_id, default_value)
                    logging.info(f"[DEBUG] Creating default variant: id='{variant_id}', url='{variant_url}'")
                    
                    # Create variant metadata
                    variant_metadata = base_metadata.copy()
                    variant_metadata["base_task_id"] = task_id
                    variant_metadata["parameter_value"] = default_value
                    
                    prompt = (
                        f"You are already on the correct page for this task. {row['description']}. "
                        "All required information and functionality is available on this current page. "
                        "Do not navigate away from this page or open new tabs. "
                        "Upon successful completion you may get a password or a code which you should extract."
                    )
                else:
                    # ERROR: ALL tasks should have default params defined
                    raise ValueError(f"Task '{task_id}' has no variants and no default params defined. All tasks must have default parameters in self.default_params.")
                
                task = BaseTask(
                    id=variant_id,
                    question=prompt,
                    ground_truth=row["password"],  # type: ignore
                    url_path=variant_url,
                    metadata=variant_metadata,
                    set="test",
                )
                self.tasks[variant_id] = task
                logging.info(f"[DEBUG] Added task to self.tasks: '{variant_id}'")

        logging.info(f"[SentinelBench] Loaded {len(self.tasks)} total examples.")

    def _build_parameterized_url(self, base_url: str, task_id: str, param_value) -> str:
        """
        Build URL with parameters for specific SentinelBench tasks.
        """
        # Duration-based tasks (time in seconds) - all will have easy/medium/hard variants
        if task_id in [
            "reactor-easy", "reactor-medium", "reactor-hard",
            "teams-monitor-easy", "teams-monitor-medium", "teams-monitor-hard",
            "linkedin-monitor-easy", "linkedin-monitor-medium", "linkedin-monitor-hard",
            "flight-monitor-easy", "flight-monitor-medium", "flight-monitor-hard",
            "news-checker-easy", "news-checker-medium", "news-checker-hard",
            "github-watcher-easy", "github-watcher-medium", "github-watcher-hard"
        ]:
            return f"{base_url}?duration={param_value}"
        
        # Count-based tasks (number of items/actions) - all will have easy/medium/hard variants
        elif task_id in [
            "animal-mover-easy", "animal-mover-medium", "animal-mover-hard",
            "button-presser-easy", "button-presser-medium", "button-presser-hard"
        ]:
            return f"{base_url}?count={param_value}"
        
        # No parameters for other tasks
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
        logging.info(f"[DEBUG] get_split_tasks called with: split='{split}', task_id='{task_id}', base_task='{base_task}', difficulty='{difficulty}'")
        logging.info(f"[DEBUG] Total tasks available: {len(self.tasks)}")
        
        if split != "test":
            raise ValueError("only 'test' split is available for SentinelBench")
        
        filtered_tasks = []
        for task_id_key, task in self.tasks.items():
            logging.info(f"[DEBUG] Checking task: '{task_id_key}', set='{task.set}', metadata.base_task='{task.metadata.get('base_task')}', metadata.difficulty='{task.metadata.get('difficulty')}'")
            
            if task.set != split:
                logging.info(f"[DEBUG] Skipping '{task_id_key}' - wrong split ('{task.set}' != '{split}')")
                continue
                
            # Apply task_id filter (exact match)
            if task_id is not None and task_id_key != task_id:
                logging.info(f"[DEBUG] Skipping '{task_id_key}' - task_id filter ('{task_id_key}' != '{task_id}')")
                continue
                
            # Apply base_task filter (check metadata)
            if base_task is not None and task.metadata.get("base_task") != base_task:
                logging.info(f"[DEBUG] Skipping '{task_id_key}' - base_task filter ('{task.metadata.get('base_task')}' != '{base_task}')")
                continue
                
            # Apply difficulty filter (check metadata)
            if difficulty is not None and task.metadata.get("difficulty") != difficulty:
                logging.info(f"[DEBUG] Skipping '{task_id_key}' - difficulty filter ('{task.metadata.get('difficulty')}' != '{difficulty}')")
                continue
                
            logging.info(f"[DEBUG] Task '{task_id_key}' PASSED all filters - adding to filtered_tasks")
            filtered_tasks.append(task_id_key)
        
        logging.info(f"[DEBUG] get_split_tasks returning {len(filtered_tasks)} tasks: {filtered_tasks}")
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
        if (hasattr(task, 'metadata') and task.metadata and 
            'parameter_value' in task.metadata):
            parameter_value = task.metadata['parameter_value']
            expected_password = f"{expected_password}_{parameter_value}"
        
        # Check if the expected password is anywhere in the candidate answer, as a substring
        score = 1.0 if expected_password in candidate.answer else 0.0

        return BaseEvalResult(score=score)
