import pytest
from unittest.mock import patch, MagicMock
from magentic_ui.backend.web.routes.validation import ValidationService, ValidationError
from autogen_core import ComponentModel


class TestAnthropicValidation:
    """Test Anthropic provider validation functionality."""

    def test_anthropic_provider_mapping(self):
        """Test that Anthropic provider aliases are correctly mapped."""
        component = {
            "provider": "anthropic_chat_completion_client",
            "component_type": "autogen_ext.models.anthropic.AnthropicChatCompletionClient",
            "config": {
                "model": "claude-4-sonnet-20251114",
                "api_key": "test-key"
            }
        }
        
        with patch('magentic_ui.backend.web.routes.validation.importlib.import_module') as mock_import:
            with patch('magentic_ui.backend.web.routes.validation.getattr') as mock_getattr:
                with patch('magentic_ui.backend.web.routes.validation.is_component_class') as mock_is_component:
                    # Setup mocks
                    mock_component_class = MagicMock()
                    mock_import.return_value = MagicMock()
                    mock_getattr.return_value = mock_component_class
                    mock_is_component.return_value = True
                    
                    # Test provider validation
                    error = ValidationService.validate_provider(component["provider"])
                    
                    # Verify mapping occurred
                    mock_import.assert_called_with("autogen_ext.models.anthropic")
                    mock_getattr.assert_called_with(mock_import.return_value, "AnthropicChatCompletionClient")
                    assert error is None

    def test_anthropic_provider_alias_mapping(self):
        """Test AnthropicChatCompletionClient alias mapping."""
        component = {
            "provider": "AnthropicChatCompletionClient",
            "component_type": "autogen_ext.models.anthropic.AnthropicChatCompletionClient",
            "config": {
                "model": "claude-4-sonnet-20251114"
            }
        }
        
        with patch('magentic_ui.backend.web.routes.validation.importlib.import_module') as mock_import:
            with patch('magentic_ui.backend.web.routes.validation.getattr') as mock_getattr:
                with patch('magentic_ui.backend.web.routes.validation.is_component_class') as mock_is_component:
                    mock_component_class = MagicMock()
                    mock_import.return_value = MagicMock()
                    mock_getattr.return_value = mock_component_class
                    mock_is_component.return_value = True
                    
                    error = ValidationService.validate_provider(component["provider"])
                    
                    mock_import.assert_called_with("autogen_ext.models.anthropic")
                    mock_getattr.assert_called_with(mock_import.return_value, "AnthropicChatCompletionClient")
                    assert error is None

    def test_anthropic_full_provider_path(self):
        """Test full Anthropic provider path validation."""
        component = {
            "provider": "autogen_ext.models.anthropic.AnthropicChatCompletionClient",
            "component_type": "autogen_ext.models.anthropic.AnthropicChatCompletionClient",
            "config": {
                "model": "claude-4-sonnet-20251114"
            }
        }
        
        with patch('magentic_ui.backend.web.routes.validation.importlib.import_module') as mock_import:
            with patch('magentic_ui.backend.web.routes.validation.getattr') as mock_getattr:
                with patch('magentic_ui.backend.web.routes.validation.is_component_class') as mock_is_component:
                    mock_component_class = MagicMock()
                    mock_import.return_value = MagicMock()
                    mock_getattr.return_value = mock_component_class
                    mock_is_component.return_value = True
                    
                    error = ValidationService.validate_provider(component["provider"])
                    
                    mock_import.assert_called_with("autogen_ext.models.anthropic")
                    mock_getattr.assert_called_with(mock_import.return_value, "AnthropicChatCompletionClient")
                    assert error is None

    def test_anthropic_provider_import_error(self):
        """Test handling of Anthropic provider import errors."""
        component = {
            "provider": "anthropic_chat_completion_client",
            "component_type": "autogen_ext.models.anthropic.AnthropicChatCompletionClient",
            "config": {
                "model": "claude-4-sonnet-20251114"
            }
        }
        
        with patch('src.magentic_ui.backend.web.routes.validation.importlib.import_module') as mock_import:
            mock_import.side_effect = ImportError("Module not found")
            
            error = ValidationService.validate_provider(component["provider"])
            
            assert error is not None
            assert isinstance(error, ValidationError)
            assert "Could not import provider" in error.error
            assert "autogen_ext.models.anthropic.AnthropicChatCompletionClient" in error.error

    def test_anthropic_config_validation(self):
        """Test Anthropic configuration validation."""
        component = {
            "provider": "autogen_ext.models.anthropic.AnthropicChatCompletionClient",
            "component_type": "autogen_ext.models.anthropic.AnthropicChatCompletionClient",
            "config": {
                "model": "claude-4-sonnet-20251114",
                "api_key": "test-key",
                "max_retries": 5
            }
        }
        
        with patch('magentic_ui.backend.web.routes.validation.ValidationService.validate_provider') as mock_validate_provider:
            with patch('magentic_ui.backend.web.routes.validation.ValidationService.validate_component_type') as mock_validate_type:
                with patch('magentic_ui.backend.web.routes.validation.ValidationService.validate_config_schema') as mock_validate_schema:
                    with patch('magentic_ui.backend.web.routes.validation.ValidationService.validate_instantiation') as mock_validate_inst:
                        # Setup mocks to return no errors
                        mock_validate_provider.return_value = None
                        mock_validate_type.return_value = None
                        mock_validate_schema.return_value = []
                        mock_validate_inst.return_value = None
                        
                        result = ValidationService.validate(component)
                        
                        assert result.is_valid is True
                        assert len(result.errors) == 0

    def test_anthropic_invalid_config(self):
        """Test validation with invalid Anthropic configuration."""
        component = {
            "provider": "autogen_ext.models.anthropic.AnthropicChatCompletionClient",
            "component_type": "autogen_ext.models.anthropic.AnthropicChatCompletionClient",
            "config": {
                # Missing required model field
                "api_key": "test-key"
            }
        }
        
        with patch('magentic_ui.backend.web.routes.validation.ValidationService.validate_provider') as mock_validate_provider:
            with patch('magentic_ui.backend.web.routes.validation.ValidationService.validate_component_type') as mock_validate_type:
                with patch('magentic_ui.backend.web.routes.validation.ValidationService.validate_config_schema') as mock_validate_schema:
                    mock_validate_provider.return_value = None
                    mock_validate_type.return_value = None
                    mock_validate_schema.return_value = [
                        ValidationError(
                            field="config.model",
                            error="Model field is required",
                            suggestion="Add a model field to the configuration"
                        )
                    ]
                    
                    result = ValidationService.validate(component)
                    
                    assert result.is_valid is False
                    assert len(result.errors) == 1
                    assert result.errors[0].field == "config.model"


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
                "model": model_name,
                "api_key": "test-key"
            }
        }
        
        with patch('magentic_ui.backend.web.routes.validation.ValidationService.validate_provider') as mock_validate_provider:
            with patch('magentic_ui.backend.web.routes.validation.ValidationService.validate_component_type') as mock_validate_type:
                with patch('magentic_ui.backend.web.routes.validation.ValidationService.validate_config_schema') as mock_validate_schema:
                    with patch('magentic_ui.backend.web.routes.validation.ValidationService.validate_instantiation') as mock_validate_inst:
                        mock_validate_provider.return_value = None
                        mock_validate_type.return_value = None
                        mock_validate_schema.return_value = []
                        mock_validate_inst.return_value = None
                        
                        result = ValidationService.validate(component)
                        
                        assert result.is_valid is True
                        assert len(result.errors) == 0

    def test_anthropic_with_optional_config(self):
        """Test Anthropic configuration with optional parameters."""
        component = {
            "provider": "autogen_ext.models.anthropic.AnthropicChatCompletionClient",
            "component_type": "autogen_ext.models.anthropic.AnthropicChatCompletionClient",
            "config": {
                "model": "claude-4-sonnet-20251114",
                "api_key": "test-key",
                "base_url": "https://api.anthropic.com",
                "max_retries": 3,
                "timeout": 30
            }
        }
        
        with patch('magentic_ui.backend.web.routes.validation.ValidationService.validate_provider') as mock_validate_provider:
            with patch('magentic_ui.backend.web.routes.validation.ValidationService.validate_component_type') as mock_validate_type:
                with patch('magentic_ui.backend.web.routes.validation.ValidationService.validate_config_schema') as mock_validate_schema:
                    with patch('magentic_ui.backend.web.routes.validation.ValidationService.validate_instantiation') as mock_validate_inst:
                        mock_validate_provider.return_value = None
                        mock_validate_type.return_value = None
                        mock_validate_schema.return_value = []
                        mock_validate_inst.return_value = None
                        
                        result = ValidationService.validate(component)
                        
                        assert result.is_valid is True
                        assert len(result.errors) == 0