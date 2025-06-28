import json

import pytest
import yaml
from magentic_ui.magentic_ui_config import MagenticUIConfig

YAML_CONFIG = """
model_client_configs:
  default: &default_client
    provider: OpenAIChatCompletionClient
    config:
      model: gpt-4.1-2025-04-14
    max_retries: 10
  anthropic_client: &anthropic_client
    provider: autogen_ext.models.anthropic.AnthropicChatCompletionClient
    config:
      model: claude-4-sonnet-20251114
      api_key: test-key
    max_retries: 5
  orchestrator: *default_client
  web_surfer: *anthropic_client
  coder: *default_client
  file_surfer: *default_client
  action_guard:
    provider: OpenAIChatCompletionClient
    config:
      model: gpt-4.1-nano-2025-04-14
    max_retries: 10

mcp_agent_configs:
  - name: mcp_agent
    description: "Test MCP Agent"
    reflect_on_tool_use: false
    tool_call_summary_format: "{tool_name}({arguments}): {result}"
    model_client: *default_client
    mcp_servers:
      - server_name: server1
        server_params:
          type: StdioServerParams
          command: npx
          args:
            - -y
            - "@modelcontextprotocol/server-everything"
      - server_name: server2
        server_params:
          type: SseServerParams
          url: http://localhost:3001/sse

cooperative_planning: true
autonomous_execution: false
allowed_websites: []
max_actions_per_step: 5
multiple_tools_per_call: false
max_turns: 20
plan: null
approval_policy: auto-conservative
allow_for_replans: true
do_bing_search: false
websurfer_loop: false
retrieve_relevant_plans: never
memory_controller_key: null
model_context_token_limit: 110000
allow_follow_up_input: true
final_answer_prompt: null
playwright_port: -1
novnc_port: -1
user_proxy_type: null
task: "What tools are available?"
hints: null
answer: null
inside_docker: false
"""


@pytest.fixture
def yaml_config_text() -> str:
    return YAML_CONFIG


@pytest.fixture
def config_obj(yaml_config_text: str) -> MagenticUIConfig:
    data = yaml.safe_load(yaml_config_text)
    return MagenticUIConfig(**data)


def test_yaml_deserialize(yaml_config_text: str) -> None:
    data = yaml.safe_load(yaml_config_text)
    config = MagenticUIConfig(**data)
    assert isinstance(config, MagenticUIConfig)
    assert config.task == "What tools are available?"
    assert config.mcp_agent_configs[0].name == "mcp_agent"
    assert config.mcp_agent_configs[0].reflect_on_tool_use is False
    assert (
        config.mcp_agent_configs[0].tool_call_summary_format
        == "{tool_name}({arguments}): {result}"
    )


def test_yaml_serialize_roundtrip(config_obj: MagenticUIConfig) -> None:
    as_dict = config_obj.model_dump(mode="json")
    yaml_text = yaml.safe_dump(as_dict)
    loaded = yaml.safe_load(yaml_text)
    config2 = MagenticUIConfig(**loaded)
    assert config2 == config_obj


def test_json_serialize_roundtrip(config_obj: MagenticUIConfig) -> None:
    as_dict = config_obj.model_dump(mode="json")
    json_text = json.dumps(as_dict)
    loaded = json.loads(json_text)
    config2 = MagenticUIConfig(**loaded)
    assert config2 == config_obj


def test_json_and_yaml_equivalence(yaml_config_text: str) -> None:
    data = yaml.safe_load(yaml_config_text)
    json_text = json.dumps(data)
    loaded = json.loads(json_text)
    config = MagenticUIConfig(**loaded)
    assert config.task == "What tools are available?"
    assert config.mcp_agent_configs[0].name == "mcp_agent"


def test_anthropic_config_serialization(config_obj: MagenticUIConfig) -> None:
    """Test that Anthropic configuration serializes and deserializes correctly."""
    # Verify Anthropic client is present in config
    assert config_obj.model_client_configs.web_surfer is not None
    web_surfer_config = config_obj.model_client_configs.web_surfer
    assert web_surfer_config.provider == "autogen_ext.models.anthropic.AnthropicChatCompletionClient"
    assert web_surfer_config.config["model"] == "claude-4-sonnet-20251114"
    assert web_surfer_config.config["api_key"] == "test-key"
    # max_retries is handled at the ModelClientConfigs level, not ComponentModel level


def test_mixed_providers_serialization() -> None:
    """Test serialization with mixed OpenAI and Anthropic providers."""
    mixed_config = """
model_client_configs:
  orchestrator:
    provider: OpenAIChatCompletionClient
    config:
      model: gpt-4o-2024-08-06
      api_key: openai-key
    max_retries: 10
  web_surfer:
    provider: autogen_ext.models.anthropic.AnthropicChatCompletionClient
    config:
      model: claude-4-sonnet-20251114
      api_key: anthropic-key
    max_retries: 5
  coder:
    provider: autogen_ext.models.anthropic.AnthropicChatCompletionClient
    config:
      model: claude-3-5-sonnet-20241022
      api_key: anthropic-key-2
    max_retries: 3
cooperative_planning: true
autonomous_execution: false
task: "Test mixed providers"
"""
    
    data = yaml.safe_load(mixed_config)
    config = MagenticUIConfig(**data)
    
    # Verify each provider type
    assert config.model_client_configs.orchestrator.provider == "OpenAIChatCompletionClient"
    assert config.model_client_configs.orchestrator.config["model"] == "gpt-4o-2024-08-06"
    
    assert config.model_client_configs.web_surfer.provider == "autogen_ext.models.anthropic.AnthropicChatCompletionClient"
    assert config.model_client_configs.web_surfer.config["model"] == "claude-4-sonnet-20251114"
    
    assert config.model_client_configs.coder.provider == "autogen_ext.models.anthropic.AnthropicChatCompletionClient"
    assert config.model_client_configs.coder.config["model"] == "claude-3-5-sonnet-20241022"
    
    # Test round-trip serialization
    as_dict = config.model_dump(mode="json")
    yaml_text = yaml.safe_dump(as_dict)
    loaded = yaml.safe_load(yaml_text)
    config2 = MagenticUIConfig(**loaded)
    assert config2 == config


def test_anthropic_with_optional_fields() -> None:
    """Test Anthropic configuration with optional fields."""
    anthropic_config = """
model_client_configs:
  orchestrator:
    provider: autogen_ext.models.anthropic.AnthropicChatCompletionClient
    config:
      model: claude-4-sonnet-20251114
      api_key: test-key
      base_url: https://custom-anthropic-endpoint.com
      max_retries: 3
      timeout: 30
      model_info:
        vision: true
        function_calling: true
        json_output: false
        family: claude-4-sonnet
        structured_output: false
        multiple_system_messages: false
    max_retries: 5
task: "Test Anthropic with optional fields"
"""
    
    data = yaml.safe_load(anthropic_config)
    config = MagenticUIConfig(**data)
    
    orchestrator_config = config.model_client_configs.orchestrator
    assert orchestrator_config.config["base_url"] == "https://custom-anthropic-endpoint.com"
    assert orchestrator_config.config["timeout"] == 30
    assert orchestrator_config.config["model_info"]["vision"] is True
    assert orchestrator_config.config["model_info"]["family"] == "claude-4-sonnet"
    
    # Test serialization preserves optional fields
    as_dict = config.model_dump(mode="json")
    json_text = json.dumps(as_dict)
    loaded = json.loads(json_text)
    config2 = MagenticUIConfig(**loaded)
    
    orchestrator_config2 = config2.model_client_configs.orchestrator
    assert orchestrator_config2.config["base_url"] == "https://custom-anthropic-endpoint.com"
    assert orchestrator_config2.config["model_info"]["family"] == "claude-4-sonnet"
