from .benchmark import Benchmark


class BaseQABenchmark(Benchmark):
    """Base class for Question-Answering benchmarks."""

    def __init__(self, name, data_dir=None, tasks=None, num_instances: int = None):
        super().__init__(name, data_dir, tasks)

        self.num_instances = num_instances

    def format_instance(self) -> str:
        """
        Format the task for the benchmark.
        This method can be overridden by subclasses to customize the task formatting.
        """
        raise NotImplementedError("Subclasses must implement _format_task method.")
