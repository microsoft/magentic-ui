from .assistantbench.assistantbench import AssistantBenchBenchmark
from .custom.custom import CustomBenchmark
from .gaia.gaia import GaiaBenchmark
from .webvoyager.webvoyager import WebVoyagerBenchmark
from .bearcubs.bearcubs import BearcubsBenchmark
from .webgames.webgames import WebGamesBenchmark
from .simpleqa.simpleqa import SimpleQABenchmark
from .gpqa.gpqa import GPQABenchmark

__all__ = [
    "AssistantBenchBenchmark",
    "CustomBenchmark",
    "GaiaBenchmark",
    "WebVoyagerBenchmark",
    "BearcubsBenchmark",
    "WebGamesBenchmark",
    "SimpleQABenchmark",
    "GPQABenchmark",
]
