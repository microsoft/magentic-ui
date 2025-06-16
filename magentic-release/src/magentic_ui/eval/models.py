from typing import Dict, Any, List, Optional, Union
from pydantic import BaseModel, Field


class BaseTask(BaseModel):
    """Base task model that all benchmark-specific tasks inherit from"""

    id: str
    question: str
    ground_truth: str = ""
    set: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    url_path: str = ""
    file_name: str = ""
    file_dir: str = ""


class BaseCandidate(BaseModel):
    """Base candidate model that all benchmark-specific candidates inherit from"""

    answer: str


class BaseEvalResult(BaseModel):
    """Base evaluation result model that all benchmark-specific results inherit from"""

    score: Union[float, Dict[str, float]]
    metadata: Dict[str, Any] = Field(default_factory=dict)


# AssistantBench specific models
class AssistantBenchTask(BaseTask):
    difficulty: str = ""
    explanation: str = ""
    gold_url: str = ""


class AssistantBenchCandidate(BaseCandidate):
    pass  # Uses base answer field only


class AssistantBenchEvalResult(BaseEvalResult):
    pass  # Uses base score field only


# GAIA specific models
class GaiaTask(BaseTask):
    difficulty: str = ""
    file_name: str = ""


class GaiaCandidate(BaseCandidate):
    pass  # Uses base answer field only


class GaiaEvalResult(BaseEvalResult):
    pass  # Uses base score field only


# WebVoyager specific models
class WebVoyagerTask(BaseTask):
    web_name: str = ""
    web: str = ""
    answer_type: Optional[str] = None


class WebVoyagerCandidate(BaseCandidate):
    screenshots: List[str] = Field(default_factory=list)


class WebVoyagerEvalResult(BaseEvalResult):
    reasoning: str = ""
    pass  # Uses base score field only


# Custom benchmark specific models
class CustomTask(BaseTask):
    url: str = ""
    target_final_url: str = ""
    intermediate_url_list: List[str] = Field(default_factory=list)


class CustomCandidate(BaseCandidate):
    target_final_url: str = ""
    intermediate_url_list: List[str] = Field(default_factory=list)


class CustomEvalResult(BaseEvalResult):
    pass


# Union types for all tasks, candidates, and eval results
AllTaskTypes = Union[BaseTask, AssistantBenchTask, GaiaTask, WebVoyagerTask, CustomTask]

AllCandidateTypes = Union[
    BaseCandidate,
    AssistantBenchCandidate,
    GaiaCandidate,
    WebVoyagerCandidate,
    CustomCandidate,
]

AllEvalResultTypes = Union[
    BaseEvalResult,
    AssistantBenchEvalResult,
    GaiaEvalResult,
    WebVoyagerEvalResult,
    CustomEvalResult,
]
