import os
import pandas as pd
from typing import Union, List, Dict, Any
from autogen_core.models import ChatCompletionClient
from ...benchmark import Benchmark
from ..assistantbench.evaluate_utils.assistantbench_evaluator import ab_question_scorer  # type: ignore
from ...evaluators import are_urls_equal, llm_evaluate_candidate_answer
from ...models import (
    CustomTask,
    CustomCandidate,
    CustomEvalResult,
    AllTaskTypes,
    AllCandidateTypes,
    AllEvalResultTypes,
)


class CustomBenchmark(Benchmark):
    """
    A custom benchmark that either uses a CSV file or a pandas DataFrame as data source.

    The CSV or DataFrame is expected to have columns:
        - id
        - question
        - answer
        - url
        - metadata
        - target_final_url
        - intermediate_url_list
    """

    def __init__(
        self,
        name: str,
        data_dir: Union[str, None] = None,
        df: Union[pd.DataFrame, None] = None,
        answer_evaluator: str = "ab",
        model_client: Union[ChatCompletionClient, None] = None,
    ):
        """
        :param data_dir: Either the path to a CSV file OR any string identifier
                         (unused if df is provided).
        :param df: Optional pandas DataFrame with the columns
                   [id, question, answer, url, metadata, target_final_url, intermediate_url_list].
        """
        assert (
            df is not None or data_dir is not None
        ), "Either df or data_dir must be provided"
        super().__init__(name=name, data_dir=data_dir)
        if answer_evaluator not in ["ab", "llm"]:
            raise ValueError("answer_evaluator must be either 'ab' or 'llm'")
        if answer_evaluator == "llm" and model_client is None:
            raise ValueError(
                "model_client must be provided if answer_evaluator is 'llm'"
            )
        self.answer_evaluator = answer_evaluator
        self.model_client = model_client
        self.df: Union[pd.DataFrame, None] = df  # type: ignore
        self.eval_result_class = CustomEvalResult

    def download_dataset(self):
        """
        If your dataset were remote, you could download it here.
        In this simple custom benchmark, no download step is needed.
        """
        pass

    def load_dataset(self):
        """
        Loads the dataset into self.tasks.

        If self.df is not already provided, attempts to read a CSV file located
        at self.data_dir. The CSV must have columns: [id, question, answer, url, metadata, target_final_url, intermediate_url_list].
        """
        # If df is not provided, assume data_dir is a path to a CSV
        assert self.data_dir is not None
        if self.df is None:
            if not os.path.isfile(self.data_dir):
                raise FileNotFoundError(f"No CSV file found at: {self.data_dir}")
            self.df: pd.DataFrame = pd.read_csv(self.data_dir)  # type: ignore

        self.tasks: Dict[str, CustomTask] = {}
        for _, row in self.df.iterrows():
            # Safely handle metadata if it might be missing or is not a dict
            metadata_value = row.get("metadata", {})  # type: ignore
            # If metadata might be a string of JSON, parse it. Otherwise store as is.
            if isinstance(metadata_value, str):
                try:
                    import json

                    metadata_value = json.loads(metadata_value)
                except Exception:
                    # Not valid JSON, fallback to storing the raw string
                    pass

            task = CustomTask(
                id=str(row["id"]),  # type: ignore
                question=str(row["question"]),  # type: ignore
                ground_truth=str(row["answer"]),  # type: ignore
                url=str(row["url"]),  # type: ignore
                metadata=metadata_value,  # type: ignore
                target_final_url=str(row.get("target_final_url", "")),  # type: ignore
                intermediate_url_list=list(row.get("intermediate_url_list", [])),  # type: ignore
                set="custom",
            )
            self.tasks[task.id] = task

    def get_split_tasks(self, split: str) -> List[str]:
        """Returns task IDs since this benchmark doesn't have splits"""
        if split not in ["all"]:
            raise ValueError("split must be 'all'")
        return list(self.tasks.keys())

    def evaluator(
        self, task: AllTaskTypes, candidate: AllCandidateTypes
    ) -> AllEvalResultTypes:
        """
        Evaluates the candidate answer against the task's ground truth.
        Returns scores for answer correctness, target URL match, and intermediate URL sequence.
        """
        # cast to CustomTask and CustomCandidate if dicts
        if isinstance(task, dict):
            task = CustomTask(**task)  # type: ignore
        if isinstance(candidate, dict):
            candidate = CustomCandidate(**candidate)  # type: ignore
        scores_dict: Dict[str, Any] = {}

        if task.ground_truth:
            if self.answer_evaluator == "llm":
                assert self.model_client is not None
                scores_dict["answer"] = llm_evaluate_candidate_answer(
                    task_question=task.question,
                    candidate_answer=candidate.answer,
                    model_client=self.model_client,
                )["score"]
            else:
                scores_dict["answer"] = ab_question_scorer(
                    prediction=candidate.answer, gold_answer=task.ground_truth
                )
        assert isinstance(task, CustomTask)
        if task.target_final_url:
            assert isinstance(candidate, CustomCandidate)
            scores_dict["target_final_url"] = are_urls_equal(
                candidate.target_final_url, task.target_final_url
            )

        def remove_consecutive_duplicates(urls: List[str]) -> List[str]:
            deduped: List[str] = []
            for url in urls:
                if not deduped or deduped[-1] != url:
                    deduped.append(url)
            return deduped

        def lcs(seq1: List[str], seq2: List[str]) -> int:
            """
            Computes the length of the Longest Common Subsequence (LCS) between two sequences.
            This function returns an integer score, where each matching URL (in order) gives one point.
            """
            m, n = len(seq1), len(seq2)
            dp = [[0] * (n + 1) for _ in range(m + 1)]
            for i in range(1, m + 1):
                for j in range(1, n + 1):
                    if seq1[i - 1] == seq2[j - 1]:
                        dp[i][j] = dp[i - 1][j - 1] + 1
                    else:
                        dp[i][j] = max(dp[i - 1][j], dp[i][j - 1])
            return dp[m][n]

        if task.intermediate_url_list:
            assert isinstance(candidate, CustomCandidate)
            processed_candidate = remove_consecutive_duplicates(
                candidate.intermediate_url_list
            )
            processed_gold = remove_consecutive_duplicates(task.intermediate_url_list)

            scores_dict["intermediate_url_list"] = lcs(
                processed_gold, processed_candidate
            )

        return CustomEvalResult(score=scores_dict)
