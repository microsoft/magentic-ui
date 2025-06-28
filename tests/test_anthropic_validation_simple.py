import pytest
from magentic_ui.backend.web.routes.validation import ValidationService, ValidationError
from autogen_core import ComponentModel


class TestAnthropicValidation:
    """Test Anthropic provider validation functionality."""

    def test_anthropic_provider_validation_real(self):
        """Test that Anthropic provider can be validated."""
        # Test with full provider path
        error = ValidationService.validate_provider("autogen_ext.models.anthropic.AnthropicChatCompletionClient")
        assert error is None  # Should pass since we have anthropic installed

    def test_anthropic_alias_validation(self):
        """Test Anthropic provider aliases."""
        # Test anthropic_chat_completion_client alias
        error = ValidationService.validate_provider("anthropic_chat_completion_client")
        assert error is None
        
        # Test AnthropicChatCompletionClient alias
        error = ValidationService.validate_provider("AnthropicChatCompletionClient")
        assert error is None

    def test_invalid_provider_validation(self):
        """Test validation with invalid provider."""
        error = ValidationService.validate_provider("NonExistentProvider")
        assert error is not None
        assert isinstance(error, ValidationError)
        assert "Error validating provider" in error.error

    def test_anthropic_component_validation(self):
        """Test full Anthropic component validation."""
        component = {
            "provider": "autogen_ext.models.anthropic.AnthropicChatCompletionClient",
            "component_type": "autogen_ext.models.anthropic.AnthropicChatCompletionClient",
            "config": {
                "model": "claude-4-sonnet-20251114"
            }
        }
        
        result = ValidationService.validate(component)
        # May have warnings but should be valid
        assert result.is_valid is True


class TestAnthropicModels:
    """Test Anthropic model configurations."""

    @pytest.mark.parametrize("model_name", [
        "claude-4-sonnet-20251114",
        "claude-3-5-sonnet-20241022", 
        "claude-3-5-haiku-20241022",
        "claude-3-opus-20240229"
    ])
    def test_supported_anthropic_models(self, model_name):
        """Test that various Anthropic models are properly configured."""
        component = {
            "provider": "autogen_ext.models.anthropic.AnthropicChatCompletionClient",
            "component_type": "autogen_ext.models.anthropic.AnthropicChatCompletionClient",
            "config": {
                "model": model_name
            }
        }
        
        result = ValidationService.validate(component)
        assert result.is_valid is True

    def test_anthropic_with_optional_config(self):
        """Test Anthropic configuration with optional parameters."""
        component = {
            "provider": "autogen_ext.models.anthropic.AnthropicChatCompletionClient",
            "component_type": "autogen_ext.models.anthropic.AnthropicChatCompletionClient",
            "config": {
                "model": "claude-4-sonnet-20251114",
                "api_key": "test-key",
                "base_url": "https://api.anthropic.com",
                "max_retries": 3
            }
        }
        
        result = ValidationService.validate(component)
        assert result.is_valid is True