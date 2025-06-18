from autogen_core.models import ChatCompletionClient
from systems import MagenticUIAutonomousSystem
from systems.magentic_one_system import MagenticOneSystem
from magentic_ui.eval.benchmarks import WebVoyagerBenchmark
import os

def test_magentic_ui_system():
    default_client_config = {
        "provider": "OpenAIChatCompletionClient",
        "config": {
            "model": "gpt-4o-2024-08-06",
        },
        "max_retries": 10,
    }

    system = MagenticUIAutonomousSystem(
        endpoint_config_orch=default_client_config,
        endpoint_config_websurfer=default_client_config,
        endpoint_config_coder=default_client_config,
        endpoint_config_file_surfer=default_client_config,
        use_local_browser=True,
        web_surfer_only=True,
    )

    client = ChatCompletionClient.load_component(default_client_config)

    benchmark = WebVoyagerBenchmark(
        data_dir="WebVoyager",
        eval_method="gpt_eval",
        model_client=client,
    )
    benchmark.download_dataset()
    benchmark.load_dataset()
    test_task = benchmark.tasks["Allrecipes--0"]
    print(test_task)
    os.makedirs("test_output_magentic_ui", exist_ok=True)
    answer = system.get_answer(
        task_id="Allrecipes--0",
        task=test_task,
        output_dir="test_output_magentic_ui",
    )
    print(answer)
    score = benchmark.evaluator(test_task, answer)
    print(score)


def test_magentic_one_system():
    default_client_config = {
        "provider": "OpenAIChatCompletionClient",
        "config": {
            "model": "gpt-4o-2024-08-06",
        },
        "max_retries": 10,
    }

    system = MagenticOneSystem(
        model_client_config=default_client_config,
        web_surfer_only=True,
    )

    client = ChatCompletionClient.load_component(default_client_config)

    benchmark = WebVoyagerBenchmark(
        data_dir="WebVoyager",
        eval_method="gpt_eval",
        model_client=client,
    )
    benchmark.download_dataset()
    benchmark.load_dataset()
    test_task = benchmark.tasks["Allrecipes--0"]
    print(test_task)
    os.makedirs("test_output_magentic_one", exist_ok=True)
    answer = system.get_answer(
        task_id="Allrecipes--0",
        task=test_task,
        output_dir="test_output_magentic_one",
    )
    print(answer)
    score = benchmark.evaluator(test_task, answer)
    print(score)


if __name__ == "__main__":
    test_magentic_one_system()
