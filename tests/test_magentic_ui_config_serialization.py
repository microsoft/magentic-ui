import json

import pytest
import yaml
from magentic_ui.magentic_ui_config import MagenticUIConfig

YAML_CONFIG = """
model_client_configs:
  orchestrator:
    provider: OpenAIChatCompletionClient
    config:
      model: gpt-4o
    max_retries: 10
  web_surfer:
    provider: OpenAIChatCompletionClient
    config:
      model: gpt-4o
    max_retries: 10

sandbox:
  type: quicksand
  memory: "4G"
  cpus: 2
  pool_size: 5

agent_mode: all
final_answer_prompt: null
user_proxy_type: null
"""

YAML_CONFIG_WITH_HARNESS = """
harness_config:
  orchestrator:
    approval_policy: auto_approve
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
    assert config.agent_mode == "all"
    assert config.sandbox.type == "quicksand"


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
    assert config.sandbox.type == "quicksand"


def test_quicksand_sandbox_default() -> None:
    config = MagenticUIConfig()
    assert config.sandbox.type == "quicksand"


def test_from_yaml(tmp_path: object) -> None:
    from pathlib import Path

    p = Path(str(tmp_path)) / "config.yaml"
    p.write_text(YAML_CONFIG)
    config = MagenticUIConfig.from_yaml(p)
    assert config.sandbox.type == "quicksand"
    assert config.model_client_configs.orchestrator is not None


def test_harness_config_default() -> None:
    config = MagenticUIConfig()
    assert (
        config.harness_config.orchestrator.approval_policy
        == "require_approval_untrusted"
    )
    assert config.harness_config.orchestrator.temperature == 0.6


def test_harness_config_temperature_default_when_omitted() -> None:
    yaml_text = """
harness_config:
  orchestrator:
    approval_policy: auto_approve
"""
    data = yaml.safe_load(yaml_text)
    config = MagenticUIConfig(**data)
    assert config.harness_config.orchestrator.temperature == 0.6


def test_harness_config_temperature_from_yaml() -> None:
    yaml_text = """
harness_config:
  orchestrator:
    temperature: 0.2
"""
    data = yaml.safe_load(yaml_text)
    config = MagenticUIConfig(**data)
    assert config.harness_config.orchestrator.temperature == 0.2


def test_harness_config_temperature_roundtrip() -> None:
    yaml_text = """
harness_config:
  orchestrator:
    temperature: 0.9
"""
    data = yaml.safe_load(yaml_text)
    config = MagenticUIConfig(**data)
    as_dict = config.model_dump(mode="json")
    config2 = MagenticUIConfig(**as_dict)
    assert (
        config2.harness_config.orchestrator.temperature
        == config.harness_config.orchestrator.temperature
        == 0.9
    )


def test_harness_config_from_yaml() -> None:
    data = yaml.safe_load(YAML_CONFIG_WITH_HARNESS)
    config = MagenticUIConfig(**data)
    assert config.harness_config.orchestrator.approval_policy == "auto_approve"


def test_harness_config_roundtrip() -> None:
    data = yaml.safe_load(YAML_CONFIG_WITH_HARNESS)
    config = MagenticUIConfig(**data)
    as_dict = config.model_dump(mode="json")
    config2 = MagenticUIConfig(**as_dict)
    assert (
        config2.harness_config.orchestrator.approval_policy
        == config.harness_config.orchestrator.approval_policy
    )


def test_harness_config_all_policies() -> None:
    for policy in [
        "auto_approve",
        "require_approval_untrusted",
        "require_approval_all",
    ]:
        yaml_text = f"""
harness_config:
  orchestrator:
    approval_policy: {policy}
"""
        data = yaml.safe_load(yaml_text)
        config = MagenticUIConfig(**data)
        assert config.harness_config.orchestrator.approval_policy == policy


def test_web_surfer_max_rounds_default() -> None:
    config = MagenticUIConfig()
    assert config.harness_config.web_surfer.max_rounds == 100


def test_web_surfer_max_rounds_from_yaml() -> None:
    yaml_text = """
harness_config:
  web_surfer:
    max_rounds: 250
"""
    data = yaml.safe_load(yaml_text)
    config = MagenticUIConfig(**data)
    assert config.harness_config.web_surfer.max_rounds == 250
    # Defaults for orchestrator subsection still apply
    assert config.harness_config.orchestrator.temperature == 0.6


def test_web_surfer_max_rounds_roundtrip() -> None:
    yaml_text = """
harness_config:
  web_surfer:
    max_rounds: 42
"""
    data = yaml.safe_load(yaml_text)
    config = MagenticUIConfig(**data)
    as_dict = config.model_dump(mode="json")
    config2 = MagenticUIConfig(**as_dict)
    assert config2.harness_config.web_surfer.max_rounds == 42


def test_web_surfer_max_rounds_validation_bounds() -> None:
    """``max_rounds`` is constrained to [1, 1000]; out-of-range raises."""
    with pytest.raises(Exception):  # pydantic ValidationError
        MagenticUIConfig(
            **yaml.safe_load("harness_config:\n  web_surfer:\n    max_rounds: 0\n")
        )
    with pytest.raises(Exception):
        MagenticUIConfig(
            **yaml.safe_load("harness_config:\n  web_surfer:\n    max_rounds: 1001\n")
        )


def test_orchestrator_max_rounds_default() -> None:
    config = MagenticUIConfig()
    assert config.harness_config.orchestrator.max_rounds == 100


def test_orchestrator_max_rounds_from_yaml() -> None:
    yaml_text = """
harness_config:
  orchestrator:
    max_rounds: 75
"""
    data = yaml.safe_load(yaml_text)
    config = MagenticUIConfig(**data)
    assert config.harness_config.orchestrator.max_rounds == 75
    # Other orchestrator defaults still apply
    assert config.harness_config.orchestrator.temperature == 0.6


def test_orchestrator_max_rounds_roundtrip() -> None:
    yaml_text = """
harness_config:
  orchestrator:
    max_rounds: 17
"""
    data = yaml.safe_load(yaml_text)
    config = MagenticUIConfig(**data)
    as_dict = config.model_dump(mode="json")
    config2 = MagenticUIConfig(**as_dict)
    assert config2.harness_config.orchestrator.max_rounds == 17


def test_orchestrator_max_rounds_validation_bounds() -> None:
    """``max_rounds`` is constrained to [1, 1000]; out-of-range raises."""
    with pytest.raises(Exception):
        MagenticUIConfig(
            **yaml.safe_load("harness_config:\n  orchestrator:\n    max_rounds: 0\n")
        )
    with pytest.raises(Exception):
        MagenticUIConfig(
            **yaml.safe_load("harness_config:\n  orchestrator:\n    max_rounds: 1001\n")
        )
