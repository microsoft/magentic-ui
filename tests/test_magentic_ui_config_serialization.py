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
  orchestrator: *default_client
  web_surfer: *default_client
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
