from typing import List, Dict, Any, Type, Optional, Union
from .models import (
    AllTaskTypes,
    AllCandidateTypes,
    AllEvalResultTypes,
)
import importlib
from abc import ABC, abstractmethod


class Benchmark(ABC):
    """
    Base benchmark class for Task, Candidate and EvalResult.
    Arguments to the constructor must be serializable by Pydantic.
    Benchmark is assumed to be stateless.

    Attributes:
        name (str): The name of the benchmark
        data_dir (str): The directory where the dataset is stored
        tasks (List[AllTaskTypes]): List of typed task objects
    """

    def __init__(
        self,
        name: str,
        data_dir: Union[str, None] = None,
        tasks: Optional[Dict[str, AllTaskTypes]] = None,
    ):
        self.name = name
        self.data_dir = data_dir
        self.tasks = tasks if tasks is not None else {}
        self.eval_result_class: Optional[Type[AllEvalResultTypes]] = None

    def download_dataset(self) -> None:
        """Download or load the dataset into data/<benchmark_name>/."""
        raise NotImplementedError("Implement dataset downloading/loading.")

    def load_dataset(self) -> None:
        """Loads the previously downloaded dataset from self.data_dir into self.tasks."""
        raise NotImplementedError("Implement dataset loading from disk.")

    def load_task_by_id(self, id: str) -> Union[AllTaskTypes, None]:
        """Load and returns a task by its id. Can do any preprocessing here (setting up environment, etc.)."""
        return self.tasks.get(id)

    def get_split_tasks(self, split: str) -> List[str]:
        """Return task ids for the specified split."""
        raise NotImplementedError("Implement subsetting .tasks based on split")

    @abstractmethod
    def evaluator(
        self, task: AllTaskTypes, candidate: AllCandidateTypes
    ) -> AllEvalResultTypes:
        """Implement the evaluator logic here for a single example."""
        pass

    def compute_aggregate_metrics(
        self, scores: List[AllEvalResultTypes]
    ) -> Dict[str, Any]:
        """
        Compute aggregate metrics (e.g. average score).
        Receives a list of evaluator outputs.
        Must produce a dictionary.

        You can override this method to compute custom metrics.

        Args:
            scores (List[AllEvalResultTypes]): A list of scores.

        Returns:
            Dict[str, Any]: A dictionary containing the aggregate metrics.
        """
        if not scores:
            raise ValueError("No scores provided for aggregation.")

        if isinstance(scores[0].score, dict):
            for s in scores:
                assert isinstance(s.score, dict), "Each score must be a dictionary."
                assert all(
                    isinstance(k, str) for k in s.score.keys()
                ), "Each score key must be a string."
                assert all(
                    isinstance(v, float) for v in s.score.values()
                ), "Each score value must be a float."

            dict_scores = [s.score for s in scores if isinstance(s.score, dict)]

            score_sums: Dict[str, float] = {}
            score_counts: Dict[str, int] = {}

            for dict_score in dict_scores:
                for key, value in dict_score.items():
                    if key not in score_sums:
                        score_sums[key] = 0
                        score_counts[key] = 0
                    score_sums[key] += value
                    score_counts[key] += 1

            mean_scores = {
                f"mean_score_{key}": (score_sums[key] / score_counts[key])
                if score_counts[key] > 0
                else 0.0
                for key in score_sums
            }

            max_scores = {
                f"max_score_{key}": max([dict_score[key] for dict_score in dict_scores])
                for key in score_sums
            }
            return {**mean_scores, **max_scores, "num_tasks": len(scores)}
        else:
            assert all(
                isinstance(s.score, float) for s in scores
            ), "Each score must be a float."

            float_scores = [s.score for s in scores if isinstance(s.score, float)]

            mean_score = sum(float_scores) / len(float_scores) if scores else 0.0

            max_score = max(float_scores) if scores else 0.0

            return {
                "mean_score": mean_score,
                "max_score": max_score,
                "num_tasks": len(float_scores),
            }

    def compute_aggregate_metrics_multiple_runs(
        self,
        all_scores: List[List[AllEvalResultTypes]],
        all_durations: List[List[float]],
    ) -> Dict[str, Any]:
        """
        Compute aggregate metrics for multiple runs.

        Args:
            all_scores (List[List[AllEvalResultTypes]]): A list of score lists from multiple runs.
                                    Each inner list contains AllEvalResultTypes objects from one complete run.
            all_durations (List[List[float]]): A list of duration lists from multiple runs.

        Returns:
            Dict[str, Any]: A dictionary containing the aggregate metrics across all runs.
        """
        if not all_scores or not all_durations:
            raise ValueError("No scores provided for aggregation.")
        if len(all_scores) != len(all_durations):
            raise ValueError("All_scores and all_durations must have the same length.")
        if len(all_scores) <= 1 or len(all_durations) <= 1:
            raise ValueError(
                "All_scores and all_durations must have at least two runs."
            )

        # Compute metrics for each run
        run_metrics = [
            self.compute_aggregate_metrics(run_scores) for run_scores in all_scores
        ]

        # Combine metrics across runs appropriately
        combined_metrics = {}
        for key in run_metrics[0].keys():
            values = [metrics[key] for metrics in run_metrics]
            if key.startswith("mean_"):
                # Average the mean scores across runs
                combined_metrics[key] = sum(values) / len(values)
            elif key.startswith("max_"):
                # Take the maximum of max scores across runs
                combined_metrics[key] = max(values)
            else:
                # For other metrics (like num_tasks), take the average
                combined_metrics[key] = sum(values) / len(values)

        # Calculate average time across all runs
        total_time: float = sum(sum(durations) for durations in all_durations)
        num_runs: int = len(all_durations)
        avg_time: float = total_time / num_runs

        return {**combined_metrics, "average_time": avg_time}


def load_benchmark_class(benchmark_name: str) -> Type[Benchmark]:
    """
    Dynamically load a benchmark class based on the benchmark name.

    Args:
        benchmark_name (str): The name of the benchmark.

    Returns:
        Type[Benchmark]: The benchmark class.
    """
    module_name = "magentic_ui.eval.benchmarks"
    class_name = f"{benchmark_name}Benchmark"
    module = importlib.import_module(module_name)
    benchmark_class = getattr(module, class_name)
    return benchmark_class
