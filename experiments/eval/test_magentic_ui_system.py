from systems import MagenticUIAutonomousSystem
from magentic_ui.eval.models import BaseTask


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
    )
    test_task = BaseTask(
        id="1",
        question="who is hussein mozannar?",
        set="test"
    )
    answer = system.get_answer(
        task_id="test",
        task=test_task,
        output_dir="test_output",
    )
    print(answer)

if __name__ == "__main__":
    test_magentic_ui_system()