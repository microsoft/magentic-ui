import asyncio
import unittest
from unittest.mock import patch, MagicMock, call

from src.magentic_ui.magentic_ui_config import MagenticUIConfig, ModelClientConfigs
from src.magentic_ui.task_team import get_task_team
from src.magentic_ui.types import RunPaths
from autogen_core import ComponentModel

# A dummy component model for testing when a ComponentModel is needed instead of a dict
class DummyComponentModel(ComponentModel):
    provider: str
    config: dict
    max_retries: int

class TestOllamaModelClientConfigs(unittest.TestCase):

    def test_ollama_config_in_model_client_configs_dict(self):
        """Test ModelClientConfigs with ollama as dict."""
        ollama_config_dict = {
            "provider": "OllamaChatCompletionClient",
            "config": {"model": "test_ollama_model", "api_base": "http://localhost:11434/api"},
            "max_retries": 3
        }
        configs = ModelClientConfigs(ollama=ollama_config_dict)
        self.assertIsInstance(configs.ollama, ComponentModel)
        # Check that the essential parts of the original dict are in the ComponentModel's dump
        dumped_config = configs.ollama.model_dump(exclude_none=True)
        self.assertEqual(dumped_config['provider'], ollama_config_dict['provider'])
        self.assertEqual(dumped_config['config'], ollama_config_dict['config'])
        if 'max_retries' in dumped_config or 'max_retries' in ollama_config_dict : # Check if the key is expected or present
            self.assertEqual(dumped_config.get('max_retries'), ollama_config_dict.get('max_retries'))


    def test_ollama_config_in_model_client_configs_component_model(self):
        """Test ModelClientConfigs with ollama as ComponentModel instance."""
        ollama_component_model = DummyComponentModel(
            provider="OllamaChatCompletionClient",
            config={"model": "test_ollama_model_component", "api_base": "http://localhost:11434/api"},
            max_retries=5
        )
        configs_component = ModelClientConfigs(ollama=ollama_component_model)
        self.assertEqual(configs_component.ollama, ollama_component_model)


    def test_get_default_ollama_client_config(self):
        """Test ModelClientConfigs.get_default_ollama_client_config() returns expected default."""
        expected_default = {
            "provider": "OllamaChatCompletionClient",
            "config": {
                "model": "llama2",
                "api_base": "http://localhost:11434/api",
            },
            "max_retries": 3,
        }
        self.assertEqual(ModelClientConfigs.get_default_ollama_client_config(), expected_default)


class TestCoderAgentOllamaIntegration(unittest.IsolatedAsyncioTestCase):

    def assert_model_config_loaded(self, mock_load_component, expected_config_dict):
        """Helper to assert ChatCompletionClient.load_component was called with expected config."""
        found_call = False
        for call_args_obj in mock_load_component.call_args_list:
            args, _ = call_args_obj
            if args and isinstance(args[0], ComponentModel):
                loaded_config = args[0].model_dump(exclude_none=True)
                # Compare relevant parts, provider and config dict
                if (loaded_config.get("provider") == expected_config_dict["provider"] and
                        loaded_config.get("config") == expected_config_dict["config"]):
                    # Max retries is optional to check if it's part of the expected_config_dict
                    if "max_retries" in expected_config_dict:
                        if loaded_config.get("max_retries") == expected_config_dict["max_retries"]:
                            found_call = True
                            break
                    else: # If max_retries not in expected, provider and config match is enough
                        found_call = True
                        break
            elif args and isinstance(args[0], dict): # Fallback if it's a dict (should be ComponentModel)
                if (args[0].get("provider") == expected_config_dict["provider"] and
                        args[0].get("config") == expected_config_dict["config"]):
                    if "max_retries" in expected_config_dict:
                        if args[0].get("max_retries") == expected_config_dict["max_retries"]:
                            found_call = True
                            break
                    else:
                        found_call = True
                        break
        self.assertTrue(found_call, f"Expected config {expected_config_dict} not found in load_component calls. Calls: {mock_load_component.call_args_list}")


    @patch('src.magentic_ui.task_team.make_agentchat_input_func')
    @patch('src.magentic_ui.agents.UserProxyAgent')
    @patch('src.magentic_ui.agents.FileSurfer')
    @patch('src.magentic_ui.agents.CoderAgent')
    @patch('src.magentic_ui.agents.WebSurfer.from_config')
    # Removed @patch('src.magentic_ui.teams.orchestrator.Orchestrator.load_component')
    @patch('autogen_core.models.ChatCompletionClient.load_component')
    async def test_coder_agent_uses_explicit_ollama_config(
        self, mock_load_component, mock_websurfer_from_config, # mock_orchestrator_load removed
        MockCoderAgent, MockFileSurfer, MockUserProxyAgent, mock_make_input_func
    ):
        """Test CoderAgent uses explicit ollama config."""
        mock_load_component.return_value = MagicMock()
        # mock_orchestrator_load.return_value = MagicMock() # Removed
        mock_websurfer_from_config.return_value = MagicMock()
        MockCoderAgent.return_value = MagicMock()
        MockFileSurfer.return_value = MagicMock()
        MockUserProxyAgent.return_value = MagicMock()
        mock_make_input_func.return_value = MagicMock()

        ollama_config_dict = {
            "provider": "OllamaChatCompletionClient",
            "config": {"model": "explicit_ollama", "api_base": "http://custom:11434/api"},
            "max_retries": 5
        }
        
        config = MagenticUIConfig(
            model_client_configs=ModelClientConfigs(
                ollama=ollama_config_dict,
                # Provide defaults for others to ensure get_model_client doesn't use a global default
                # that might coincidentally match what we expect for coder.
                orchestrator=ModelClientConfigs.get_default_client_config(), 
                web_surfer=ModelClientConfigs.get_default_client_config(),
                file_surfer=ModelClientConfigs.get_default_client_config(),
                action_guard=ModelClientConfigs.get_default_action_guard_config()
            )
        )
        run_paths = RunPaths(internal_root_dir=".", external_root_dir=".", run_suffix="test", internal_run_dir=".", external_run_dir=".")
        
        await get_task_team(magentic_ui_config=config, paths=run_paths)
        
        self.assert_model_config_loaded(mock_load_component, ollama_config_dict)


    @patch('src.magentic_ui.task_team.make_agentchat_input_func')
    @patch('src.magentic_ui.agents.UserProxyAgent')
    @patch('src.magentic_ui.agents.FileSurfer')
    @patch('src.magentic_ui.agents.CoderAgent')
    @patch('src.magentic_ui.agents.WebSurfer.from_config')
    # Removed @patch('src.magentic_ui.teams.orchestrator.Orchestrator.load_component')
    @patch('autogen_core.models.ChatCompletionClient.load_component')
    async def test_coder_agent_fallback_to_coder_config(
        self, mock_load_component, mock_websurfer_from_config, # mock_orchestrator_load removed
        MockCoderAgent, MockFileSurfer, MockUserProxyAgent, mock_make_input_func
    ):
        """Test CoderAgent falls back to coder config if ollama config is not present."""
        mock_load_component.return_value = MagicMock()
        # mock_orchestrator_load.return_value = MagicMock() # Removed
        mock_websurfer_from_config.return_value = MagicMock()
        MockCoderAgent.return_value = MagicMock()
        MockFileSurfer.return_value = MagicMock()
        MockUserProxyAgent.return_value = MagicMock()
        mock_make_input_func.return_value = MagicMock()

        coder_specific_config = {
            "provider": "OpenAIChatCompletionClient", # Different provider
            "config": {"model": "gpt-coder", "api_key": "test_key"},
            "max_retries": 2
        }
        
        config = MagenticUIConfig(
            model_client_configs=ModelClientConfigs(
                ollama=None,
                coder=coder_specific_config,
                orchestrator=ModelClientConfigs.get_default_client_config(),
                web_surfer=ModelClientConfigs.get_default_client_config(),
                file_surfer=ModelClientConfigs.get_default_client_config(),
                action_guard=ModelClientConfigs.get_default_action_guard_config()
            )
        )
        run_paths = RunPaths(internal_root_dir=".", external_root_dir=".", run_suffix="test", internal_run_dir=".", external_run_dir=".")
        
        await get_task_team(magentic_ui_config=config, paths=run_paths)
        
        self.assert_model_config_loaded(mock_load_component, coder_specific_config)


    @patch('src.magentic_ui.task_team.make_agentchat_input_func')
    @patch('src.magentic_ui.agents.UserProxyAgent')
    @patch('src.magentic_ui.agents.FileSurfer')
    @patch('src.magentic_ui.agents.CoderAgent')
    @patch('src.magentic_ui.agents.WebSurfer.from_config')
    # Removed @patch('src.magentic_ui.teams.orchestrator.Orchestrator.load_component')
    @patch('autogen_core.models.ChatCompletionClient.load_component')
    async def test_coder_agent_defaults_to_default_ollama_config(
        self, mock_load_component, mock_websurfer_from_config, # mock_orchestrator_load removed
        MockCoderAgent, MockFileSurfer, MockUserProxyAgent, mock_make_input_func
    ):
        """Test CoderAgent defaults to default ollama config if no specific ollama or coder config."""
        mock_load_component.return_value = MagicMock()
        # mock_orchestrator_load.return_value = MagicMock() # Removed
        mock_websurfer_from_config.return_value = MagicMock()
        MockCoderAgent.return_value = MagicMock()
        MockFileSurfer.return_value = MagicMock()
        MockUserProxyAgent.return_value = MagicMock()
        mock_make_input_func.return_value = MagicMock()

        default_ollama_config = ModelClientConfigs.get_default_ollama_client_config()
        
        config = MagenticUIConfig(
            model_client_configs=ModelClientConfigs(
                ollama=None,
                coder=None,
                orchestrator=ModelClientConfigs.get_default_client_config(),
                web_surfer=ModelClientConfigs.get_default_client_config(),
                file_surfer=ModelClientConfigs.get_default_client_config(),
                action_guard=ModelClientConfigs.get_default_action_guard_config()
            )
        )
        run_paths = RunPaths(internal_root_dir=".", external_root_dir=".", run_suffix="test", internal_run_dir=".", external_run_dir=".")
        
        await get_task_team(magentic_ui_config=config, paths=run_paths)
        
        self.assert_model_config_loaded(mock_load_component, default_ollama_config)


if __name__ == '__main__':
    unittest.main()
