import os
import json
import importlib
from typing import Optional, Type
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
        raise NotImplementedError("Implement your system's logic here.")

    def load_answer_from_disk(
        self, task_id: str, output_dir: str
    ) -> Optional[AllCandidateTypes]:
        if self.candidate_class is None:
            raise ValueError("Subclass must set self.candidate_class in __init__")

        answer_path = os.path.join(output_dir, f"{task_id}_answer.json")
        if not os.path.exists(answer_path):
            return None

        try:
            with open(answer_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return self.candidate_class.model_validate(data)
        except json.JSONDecodeError as e:
            print(f"[ERROR] Failed to decode JSON for {task_id}: {e}")
        except Exception as e:
            print(f"[ERROR] Unexpected error loading answer for {task_id}: {e}")
        return None

    def save_answer_to_disk(
        self, task_id: str, answer: AllCandidateTypes, output_dir: str
    ) -> None:
        os.makedirs(output_dir, exist_ok=True)
        answer_path = os.path.join(output_dir, f"{task_id}_answer.json")
        try:
            with open(answer_path, "w", encoding="utf-8") as f:
                f.write(answer.model_dump_json(indent=2))
        except Exception as e:
            print(f"[ERROR] Failed to save answer for {task_id}: {e}")
            raise


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

    try:
        module = importlib.import_module(module_name)
    except ImportError as e:
        raise ImportError(f"[ERROR] Could not import module '{module_name}': {e}")

    try:
        system_class = getattr(module, class_name)
    except AttributeError:
        raise ImportError(f"[ERROR] Class '{class_name}' not found in module '{module_name}'")

    if not issubclass(system_class, BaseSystem):
        raise TypeError(f"[ERROR] {class_name} is not a subclass of BaseSystem")

    return system_class
