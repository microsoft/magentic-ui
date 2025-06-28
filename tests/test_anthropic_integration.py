import pytest
import os
from unittest.mock import patch, MagicMock, AsyncMock
from autogen_core import ComponentModel
from autogen_ext.models.anthropic import AnthropicChatCompletionClient


class TestAnthropicIntegration:
    """Integration tests for Anthropic provider."""

    @pytest.fixture
    def anthropic_config(self):
        """Basic Anthropic configuration for testing."""
        return {
            "provider": "autogen_ext.models.anthropic.AnthropicChatCompletionClient",
            "config": {
                "model": "claude-4-sonnet-20251114",
                "api_key": "test-api-key-12345",
                "max_retries": 3
            }
        }

    @pytest.fixture
    def component_model(self, anthropic_config):
        """Create a ComponentModel from Anthropic config."""
        return ComponentModel(**anthropic_config)

    def test_anthropic_client_import(self):
        """Test that AnthropicChatCompletionClient can be imported."""
        try:
            from autogen_ext.models.anthropic import AnthropicChatCompletionClient
            assert AnthropicChatCompletionClient is not None
        except ImportError:
            pytest.fail("AnthropicChatCompletionClient could not be imported")

    def test_anthropic_component_model_creation(self, anthropic_config):
        """Test creating ComponentModel with Anthropic config."""
        model = ComponentModel(**anthropic_config)
        assert model.provider == "autogen_ext.models.anthropic.AnthropicChatCompletionClient"
        assert model.config["model"] == "claude-4-sonnet-20251114"
        assert model.config["api_key"] == "test-api-key-12345"

    @pytest.mark.skipif(
        "ANTHROPIC_API_KEY" not in os.environ,
        reason="ANTHROPIC_API_KEY environment variable not set"
    )
    def test_anthropic_client_initialization_with_real_key(self):
        """Test Anthropic client initialization with real API key (if available)."""
        config = ComponentModel(
            provider="autogen_ext.models.anthropic.AnthropicChatCompletionClient",
            config={
                "model": "claude-4-sonnet-20251114",
                "api_key": os.environ["ANTHROPIC_API_KEY"]
            }
        )
        
        try:
            client = AnthropicChatCompletionClient.load_component(config)
            assert client is not None
        except Exception as e:
            pytest.fail(f"Failed to initialize Anthropic client with real API key: {e}")

    def test_anthropic_client_load_component(self, component_model):
        """Test loading Anthropic component."""
        # Just test that load_component doesn't raise an exception
        # The actual loading would require a real API key
        try:
            AnthropicChatCompletionClient.load_component(component_model)
        except Exception as e:
            # Expected to fail without real API key, but should not crash
            assert "api_key" in str(e).lower() or "authentication" in str(e).lower() or "unauthorized" in str(e).lower()

    def test_anthropic_config_with_base_url(self):
        """Test Anthropic configuration with custom base URL."""
        config = ComponentModel(
            provider="autogen_ext.models.anthropic.AnthropicChatCompletionClient",
            config={
                "model": "claude-4-sonnet-20251114",
                "api_key": "test-key",
                "base_url": "https://custom-anthropic-endpoint.com"
            }
        )
        
        assert config.config["base_url"] == "https://custom-anthropic-endpoint.com"

    def test_anthropic_config_validation_missing_model(self):
        """Test that missing model is handled gracefully."""
        # ComponentModel itself doesn't validate config contents
        # That's done by the validation service
        config = ComponentModel(
            provider="autogen_ext.models.anthropic.AnthropicChatCompletionClient",
            config={
                "api_key": "test-key"
                # Missing model field - this should be caught by validation service
            }
        )
        assert config.config["api_key"] == "test-key"

    @pytest.mark.parametrize("model_name", [
        "claude-4-sonnet-20251114",
        "claude-3-5-sonnet-20241022", 
        "claude-3-5-haiku-20241022",
        "claude-3-opus-20240229",
        "gpt-4",  # Should still work, just not an Anthropic model
    ])
    def test_anthropic_model_names(self, model_name):
        """Test various model names with Anthropic provider."""
        config = ComponentModel(
            provider="autogen_ext.models.anthropic.AnthropicChatCompletionClient",
            config={
                "model": model_name,
                "api_key": "test-key"
            }
        )
        assert config.config["model"] == model_name


class TestAnthropicConfigSerialization:
    """Test Anthropic configuration serialization/deserialization."""

    def test_anthropic_config_yaml_serialization(self):
        """Test Anthropic configuration can be serialized to/from YAML."""
        import yaml
        from magentic_ui.magentic_ui_config import MagenticUIConfig, ModelClientConfigs
        
        config_dict = {
            "model_client_configs": {
                "orchestrator": {
                    "provider": "autogen_ext.models.anthropic.AnthropicChatCompletionClient",
                    "config": {
                        "model": "claude-4-sonnet-20251114",
                        "api_key": "test-key",
                        "max_retries": 5
                    }
                }
            }
        }
        
        # Test serialization
        yaml_str = yaml.safe_dump(config_dict)
        assert "claude-4-sonnet-20251114" in yaml_str
        assert "AnthropicChatCompletionClient" in yaml_str
        
        # Test deserialization  
        loaded_dict = yaml.safe_load(yaml_str)
        config = MagenticUIConfig(**loaded_dict)
        
        assert config.model_client_configs.orchestrator.provider == "autogen_ext.models.anthropic.AnthropicChatCompletionClient"
        assert config.model_client_configs.orchestrator.config["model"] == "claude-4-sonnet-20251114"

    def test_anthropic_config_json_serialization(self):
        """Test Anthropic configuration can be serialized to/from JSON."""
        import json
        from magentic_ui.magentic_ui_config import MagenticUIConfig
        
        config_dict = {
            "model_client_configs": {
                "web_surfer": {
                    "provider": "autogen_ext.models.anthropic.AnthropicChatCompletionClient",
                    "config": {
                        "model": "claude-3-5-sonnet-20241022",
                        "api_key": "test-key"
                    }
                }
            }
        }
        
        # Test JSON round-trip
        json_str = json.dumps(config_dict)
        loaded_dict = json.loads(json_str)
        config = MagenticUIConfig(**loaded_dict)
        
        assert config.model_client_configs.web_surfer.provider == "autogen_ext.models.anthropic.AnthropicChatCompletionClient"
        assert config.model_client_configs.web_surfer.config["model"] == "claude-3-5-sonnet-20241022"

    def test_mixed_providers_config(self):
        """Test configuration with both OpenAI and Anthropic providers."""
        from magentic_ui.magentic_ui_config import MagenticUIConfig
        
        config_dict = {
            "model_client_configs": {
                "orchestrator": {
                    "provider": "OpenAIChatCompletionClient",
                    "config": {
                        "model": "gpt-4o-2024-08-06",
                        "api_key": "openai-key"
                    }
                },
                "web_surfer": {
                    "provider": "autogen_ext.models.anthropic.AnthropicChatCompletionClient",
                    "config": {
                        "model": "claude-4-sonnet-20251114", 
                        "api_key": "anthropic-key"
                    }
                }
            }
        }
        
        config = MagenticUIConfig(**config_dict)
        
        # Verify mixed providers work
        assert config.model_client_configs.orchestrator.provider == "OpenAIChatCompletionClient"
        assert config.model_client_configs.web_surfer.provider == "autogen_ext.models.anthropic.AnthropicChatCompletionClient"
        
        # Verify model assignments
        assert config.model_client_configs.orchestrator.config["model"] == "gpt-4o-2024-08-06"
        assert config.model_client_configs.web_surfer.config["model"] == "claude-4-sonnet-20251114"


class TestAnthropicErrorHandling:
    """Test error handling for Anthropic integration."""

    def test_anthropic_import_error_handling(self):
        """Test graceful handling when Anthropic extension is not available."""
        # This test is tricky because we actually have Anthropic installed
        # Instead, test with a non-existent provider
        from magentic_ui.backend.web.routes.validation import ValidationService
        
        error = ValidationService.validate_provider("autogen_ext.models.nonexistent.NonExistentClient")
        assert error is not None
        assert "Could not import provider" in error.error or "Error validating provider" in error.error

    def test_anthropic_invalid_api_key_format(self):
        """Test handling of invalid API key formats."""
        config = ComponentModel(
            provider="autogen_ext.models.anthropic.AnthropicChatCompletionClient",
            config={
                "model": "claude-4-sonnet-20251114",
                "api_key": "invalid-key-format"  # Should be sk-ant-xxx format
            }
        )
        
        # This should not raise an exception at config creation time
        # API key validation happens at runtime
        assert config.config["api_key"] == "invalid-key-format"

    def test_anthropic_missing_required_fields(self):
        """Test handling when required fields are missing."""
        # ComponentModel doesn't validate required fields - that's done by validation service
        config = ComponentModel(
            provider="autogen_ext.models.anthropic.AnthropicChatCompletionClient",
            config={}  # Missing model and api_key
        )
        assert config.config == {}