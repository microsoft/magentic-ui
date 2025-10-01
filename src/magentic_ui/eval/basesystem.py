import os
import json
import time
import importlib
from typing import Optional, Type, Any
from .models import AllTaskTypes, AllCandidateTypes


class BaseSystem:
    """
    All systems should implement this interface.
    Arguments to the constructor must be serializable by Pydantic.
    System is assumed to be stateless.

    Subclasses must set self.candidate_class in their __init__ method.
    """

    def __init__(self, system_name: str):
        self.system_name = system_name
        # Subclasses must set this:
        self.candidate_class = None  # Type[AllCandidateTypes]

    def get_answer(
        self, task_id: str, task: AllTaskTypes, output_dir: str
    ) -> Optional[AllCandidateTypes]:
        """
        Return an answer for the question. Should use save_answer_to_disk to save the answer.

        Args:
            task_id (str): The ID of the task.
            task (AllTaskTypes): The typed task data.
            output_dir (str): The directory to save the output.

        Returns:
            Optional[AllCandidateTypes]: The typed candidate answer.
        """
        raise NotImplementedError("Implement your system's logic here.")

    def load_answer_from_disk(
        self, task_id: str, output_dir: str
    ) -> Optional[AllCandidateTypes]:
        """
        Helper to load an answer from disk if it exists.

        Args:
            task_id (str): The ID of the task.
            output_dir (str): The directory to load the answer from.

        Returns:
            Optional[AllCandidateTypes]: The loaded answer, or None if it doesn't exist.
        """
        if self.candidate_class is None:
            raise ValueError("Subclass must set self.candidate_class in __init__")

        # Sanitize task_id for filename (replace / with _) to match save_answer_to_disk
        safe_task_id = task_id.replace("/", "_")
        answer_path = os.path.join(output_dir, f"{safe_task_id}_answer.json")
        if not os.path.exists(answer_path):
            return None
        with open(answer_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return self.candidate_class.model_validate(data)

    def save_answer_to_disk(
        self, task_id: str, answer: AllCandidateTypes, output_dir: str
    ) -> None:
        """
        Save the answer to disk using Pydantic's json() method.

        Args:
            task_id (str): The ID of the task.
            answer (AllCandidateTypes): The typed candidate answer.
            output_dir (str): The directory to save the answer in.
        """
        os.makedirs(output_dir, exist_ok=True)
        safe_task_id = task_id.replace("/", "_")
        answer_path = os.path.join(output_dir, f"{safe_task_id}_answer.json")
        with open(answer_path, "w", encoding="utf-8") as f:
            f.write(answer.model_dump_json(indent=2))

    def save_partial_state(self, task_id: str, output_dir: str, **kwargs: Any) -> None:
        """
        Save partial state information for interrupted runs.
        Subclasses can override this to save system-specific partial state.

        Args:
            task_id (str): The ID of the task.
            output_dir (str): The directory to save partial state in.
            **kwargs: Additional state information to save.
        """
        os.makedirs(output_dir, exist_ok=True)
        safe_task_id = task_id.replace("/", "_")
        partial_state_path = os.path.join(
            output_dir, f"{safe_task_id}_partial_state.json"
        )

        state_data = {
            "task_id": task_id,
            "timestamp": json.dumps(time.time()),
            "status": "interrupted",
            **kwargs,
        }

        with open(partial_state_path, "w", encoding="utf-8") as f:
            json.dump(state_data, f, indent=2)


def load_system_class(system_name: str) -> Type[BaseSystem]:
    """
    Dynamically load a system class based on the system name.

    Args:
        system_name (str): The name of the system.

    Returns:
        Type[BaseSystem]: The loaded system class.
    """
    module_name = "magentic_ui.eval.systems"
    class_name = f"{system_name}System"
    module = importlib.import_module(module_name)
    system_class = getattr(module, class_name)
    return system_class
