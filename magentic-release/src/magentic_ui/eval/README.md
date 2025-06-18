# How to use

See the test file for examples in [samples/test_eval.py](samples/test_eval.py).

# How to implement a new benchmark

1. Add a folder in [src/magentic_ui/eval/benchmarks](src/magentic_ui/eval/benchmarks) with the name of your benchmark.

2. Add a script in this folder with the name of your benchmark.

3. Define your benchmark-specific models in `models.py`. Each benchmark typically needs three model classes:
```python
from pydantic import BaseModel, Field
from ...models import BaseTask, BaseCandidate, BaseEvalResult

class MyBenchmarkTask(BaseTask):
    # Add any additional fields specific to your task
    difficulty: str = ""
    context: str = ""
    
class MyBenchmarkCandidate(BaseCandidate):
    # Add any additional fields beyond the base 'answer' field
    confidence: float = 0.0
    
class MyBenchmarkEvalResult(BaseEvalResult):
    # Add any additional evaluation metrics beyond the base 'score' field
    accuracy: float = 0.0
```

4. Your benchmark class should follow this structure:
```python
from ...benchmark import Benchmark
from ...models import MyBenchmarkTask, MyBenchmarkCandidate, MyBenchmarkEvalResult

class MyBenchmark(Benchmark[MyBenchmarkTask, MyBenchmarkCandidate, MyBenchmarkEvalResult]):
    """
    Description of what your benchmark evaluates
    """
    def __init__(self, data_dir: str):
        super().__init__(name="MyBenchmark", data_dir=data_dir)
        self.eval_result_class = MyBenchmarkEvalResult

    def download_dataset(self) -> None:
        """
        Download or fetch your dataset. Common approaches:
        - Download from Hugging Face using snapshot_download()
        - Download from a URL using requests
        - Load from local files
        """
        pass

    def load_dataset(self) -> None:
        """
        Load the downloaded dataset into self.tasks.
        Typically involves:
        - Reading files (json, csv, etc.)
        - Converting data into MyBenchmarkTask objects
        - Appending tasks to self.tasks
        """
        pass

    def get_split_tasks(self, split: str) -> List[MyBenchmarkTask]:
        """
        Return tasks for a specific split (e.g., 'train', 'dev', 'test').
        Example:
        return [task for task in self.tasks if task.set == split]
        """
        pass

    def evaluator(self, task: MyBenchmarkTask, candidate: MyBenchmarkCandidate) -> MyBenchmarkEvalResult:
        """
        Implement the evaluation logic for a single example.
        Compare the candidate's answer against the task's ground truth.
        Return an evaluation result with appropriate scores.
        """
        pass

    def compute_aggregate_metrics(self, scores: List[MyBenchmarkEvalResult]) -> Dict[str, Any]:
        """
        Optional: Override this method to compute custom aggregate metrics.
        The default implementation handles basic score averaging.
        """
        return super().compute_aggregate_metrics(scores)
```

5. Add import to your benchmark in [src/magentic_ui/eval/benchmarks/__init__.py](src/magentic_ui/eval/benchmarks/__init__.py):
```python
from .mybenchmark.mybenchmark import MyBenchmark
```

6. Test your benchmark implementation:
- Create test cases for each method
- Verify the evaluation logic works as expected
- Test with sample tasks and candidates

# How to implement a new system

Systems should live in the `magentic_ui/eval/systems` directory. Each system must implement the BaseSystem interface.

1. Create a new file in `src/magentic_ui/eval/systems/` for your system (e.g., `my_system.py`)

2. Your system should implement this interface:
```python
from ..basesystem import BaseSystem
from ..models import BaseTask, BaseCandidate

class MySystem(BaseSystem):
    """
    Description of what your system does
    """
    def __init__(self, name: str):
        super().__init__("MySystem")
        # Must set the candidate class that this system produces
        self.candidate_class = BaseCandidate  # or your custom candidate class

    def get_answer(self, task_id: str, task: BaseTask, output_dir: str) -> BaseCandidate:
        """
        Generate or retrieve an answer for the given task.
        
        Args:
            task_id (str): The ID of the task
            task (BaseTask): The task data containing the question/prompt
            output_dir (str): Directory to save any intermediate outputs
            
        Returns:
            BaseCandidate: The system's answer wrapped in a candidate object
        """
        # Implement your system's logic here
        answer = "Your system's answer"
        candidate = self.candidate_class(answer=answer)
        
        # Save the answer to disk (recommended)
        self.save_answer_to_disk(task_id, candidate, output_dir)
        
        return candidate

    def load_answer_from_disk(self, task_id: str, output_dir: str) -> Optional[BaseCandidate]:
        """
        Optional: Override this if you need custom loading logic.
        The default implementation loads JSON files saved by save_answer_to_disk.
        """
        return super().load_answer_from_disk(task_id, output_dir)

    def save_answer_to_disk(self, task_id: str, answer: BaseCandidate, output_dir: str) -> None:
        """
        Optional: Override this if you need custom saving logic.
        The default implementation saves answers as JSON files.
        """
        super().save_answer_to_disk(task_id, answer, output_dir)
```

3. Key implementation notes:
- Always set `self.candidate_class` in `__init__`
- Use `save_answer_to_disk()` to persist answers
- Handle any cleanup in your implementation (e.g., closing connections)
- Consider implementing caching using `load_answer_from_disk()`

4. Example system implementation:
```python
class SimpleSystem(BaseSystem):
    def __init__(self, name: str):
        super().__init__("SimpleSystem")
        self.candidate_class = BaseCandidate
        self.model = load_my_model()  # Your system initialization

    def get_answer(self, task_id: str, task: BaseTask, output_dir: str) -> BaseCandidate:
        # Check if we already have an answer saved
        cached = self.load_answer_from_disk(task_id, output_dir)
        if cached is not None:
            return cached

        # Generate new answer
        response = self.model.generate(task.question)
        answer = self.candidate_class(answer=response)
        
        # Save for future use
        self.save_answer_to_disk(task_id, answer, output_dir)
        return answer
```

5. Add your system to `src/magentic_ui/eval/systems/__init__.py`:
```python
from .my_system import MySystem
```

# Roadmap

- mind2web-live
- add agentharm
- add webagentbench
- add docker