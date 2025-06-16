from ..basesystem import BaseSystem
from ..models import BaseTask, BaseCandidate


class ExampleSystem(BaseSystem):
    """
    A toy system that returns a stub answer.
    """

    def __init__(self, system_name: str):
        super().__init__(system_name)
        self.candidate_class = BaseCandidate

    def get_answer(
        self, task_id: str, task: BaseTask, output_dir: str
    ) -> BaseCandidate:
        # For demonstration, produce a trivial answer
        answer = BaseCandidate(
            answer=f"CrossFit East River Avea Pilates {task.question}"
        )
        self.save_answer_to_disk(task_id, answer, output_dir)
        return answer
