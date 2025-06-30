from typing import Union, Optional, Dict
from ..benchmark import Benchmark
from ..models import AllTaskTypes


class BaseQABenchmark(Benchmark):
    """Base class for Question-Answering benchmarks."""

    def __init__(
        self,
        name: str,
        data_dir: Union[str, None] = None,
        tasks: Optional[Dict[str, AllTaskTypes]] = None,
        num_instances: Optional[int] = None,
    ):
        super().__init__(name, data_dir, tasks)

        self.num_instances = num_instances
