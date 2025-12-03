"""Tests for config_file_loader — YAML config partial merge into DB."""

from pathlib import Path
from unittest.mock import MagicMock
from typing import Any

from magentic_ui.backend.database.config_file_loader import (
    _deep_merge,
    _merge_yaml_into_db,
    load_config_file,
)
from magentic_ui.backend.datamodel import Settings
from magentic_ui.magentic_ui_config import MagenticUIConfig


# =============================================================================
# _deep_merge
# =============================================================================


class TestDeepMerge:
    """Tests for _deep_merge — recursive dict merge."""

    def test_simple_override(self):
        base = {"a": 1, "b": 2}
        override = {"b": 3}
        assert _deep_merge(base, override) == {"a": 1, "b": 3}

    def test_nested_merge(self):
        base = {"x": {"a": 1, "b": 2}}
        override = {"x": {"b": 3}}
        assert _deep_merge(base, override) == {"x": {"a": 1, "b": 3}}

    def test_new_key(self):
        base = {"a": 1}
        override = {"b": 2}
        assert _deep_merge(base, override) == {"a": 1, "b": 2}

    def test_override_replaces_non_dict_with_dict(self):
        base = {"a": 1}
        override = {"a": {"nested": True}}
        result = _deep_merge(base, override)
        assert result == {"a": {"nested": True}}

    def test_does_not_mutate_base(self):
        base = {"a": {"b": 1}}
        override = {"a": {"b": 2}}
        _deep_merge(base, override)
        assert base["a"]["b"] == 1


# =============================================================================
# load_config_file
# =============================================================================


def _make_mock_db(existing_settings: Settings | None = None) -> MagicMock:
    """Create a mock DatabaseManager with get/upsert."""
    db = MagicMock()

    get_response = MagicMock()
    if existing_settings:
        get_response.status = True
        get_response.data = [existing_settings]
    else:
        get_response.status = True
        get_response.data = []
    db.get.return_value = get_response

    upsert_response = MagicMock()
    upsert_response.status = True
    db.upsert.return_value = upsert_response

    return db


def _make_raw(**kwargs: Any) -> dict[str, Any]:
    """Create a raw YAML dict for testing."""
    return kwargs


SAMPLE_ROLE = {
    "provider": "OpenAIChatCompletionClient",
    "config": {
        "model": "test-model",
        "api_key": "test-key",
        "base_url": "http://localhost:5000/v1",
    },
}


class TestMergeYamlIntoDb:
    """Tests for _merge_yaml_into_db — partial merge into DB (the core logic)."""

    def test_empty_yaml_returns_false(self):
        """Empty YAML does nothing."""
        db = _make_mock_db()
        raw = _make_raw()
        assert _merge_yaml_into_db(db, raw_yaml=raw, user_id="user1") is False
        db.upsert.assert_not_called()

    def test_both_models_writes_to_db(self):
        db = _make_mock_db()
        raw = _make_raw(
            model_client_configs={
                "orchestrator": SAMPLE_ROLE,
                "web_surfer": SAMPLE_ROLE,
            }
        )
        assert _merge_yaml_into_db(db, raw_yaml=raw, user_id="user1") is True
        db.upsert.assert_called_once()

    def test_sets_onboarding_completed_when_both_models(self):
        db = _make_mock_db()
        raw = _make_raw(
            model_client_configs={
                "orchestrator": SAMPLE_ROLE,
                "web_surfer": SAMPLE_ROLE,
            }
        )
        _merge_yaml_into_db(db, raw_yaml=raw, user_id="user1")
        settings_row = db.upsert.call_args[0][0]
        assert settings_row.onboarding_completed is True

    def test_omniagent_only_with_orchestrator_marks_complete(self):
        """YAML setting agent_mode=omniagent_only + orchestrator only → complete."""
        db = _make_mock_db()
        raw = _make_raw(
            agent_mode="omniagent_only",
            model_client_configs={"orchestrator": SAMPLE_ROLE},
        )
        _merge_yaml_into_db(db, raw_yaml=raw, user_id="user1")
        settings_row = db.upsert.call_args[0][0]
        assert settings_row.onboarding_completed is True
        assert settings_row.config["agent_mode"] == "omniagent_only"

    def test_websurfer_only_with_web_surfer_marks_complete(self):
        """YAML setting agent_mode=websurfer_only + web_surfer only → complete."""
        db = _make_mock_db()
        raw = _make_raw(
            agent_mode="websurfer_only",
            model_client_configs={"web_surfer": SAMPLE_ROLE},
        )
        _merge_yaml_into_db(db, raw_yaml=raw, user_id="user1")
        settings_row = db.upsert.call_args[0][0]
        assert settings_row.onboarding_completed is True

    def test_all_mode_with_only_orchestrator_marks_incomplete(self):
        """YAML with agent_mode=all but only orchestrator → incomplete (bounce-back)."""
        existing_config = MagenticUIConfig(
            agent_mode="omniagent_only",
            model_client_configs={"orchestrator": SAMPLE_ROLE, "web_surfer": None},
        ).model_dump()
        existing = Settings(user_id="user1", config=existing_config)  # pyright: ignore[reportCallIssue]
        existing.onboarding_completed = True
        db = _make_mock_db(existing_settings=existing)

        raw = _make_raw(agent_mode="all")
        _merge_yaml_into_db(db, raw_yaml=raw, user_id="user1")
        settings_row = db.upsert.call_args[0][0]
        assert settings_row.onboarding_completed is False

    def test_partial_yaml_only_agent_mode(self):
        """YAML with only agent_mode preserves existing model configs."""
        existing_config = MagenticUIConfig(
            model_client_configs={
                "orchestrator": SAMPLE_ROLE,
                "web_surfer": SAMPLE_ROLE,
            }
        ).model_dump()
        existing = Settings(user_id="user1", config=existing_config)  # pyright: ignore[reportCallIssue]
        db = _make_mock_db(existing_settings=existing)

        raw = _make_raw(agent_mode="websurfer_only")
        _merge_yaml_into_db(db, raw_yaml=raw, user_id="user1")

        settings_row = db.upsert.call_args[0][0]
        saved = settings_row.config
        assert saved["agent_mode"] == "websurfer_only"
        assert saved["model_client_configs"]["orchestrator"] is not None
        assert saved["model_client_configs"]["web_surfer"] is not None

    def test_partial_yaml_one_model_preserves_other(self):
        """YAML with only orchestrator preserves existing web_surfer."""
        existing_config = MagenticUIConfig(
            model_client_configs={"orchestrator": None, "web_surfer": SAMPLE_ROLE}
        ).model_dump()
        existing = Settings(user_id="user1", config=existing_config)  # pyright: ignore[reportCallIssue]
        db = _make_mock_db(existing_settings=existing)

        raw = _make_raw(model_client_configs={"orchestrator": SAMPLE_ROLE})
        _merge_yaml_into_db(db, raw_yaml=raw, user_id="user1")

        settings_row = db.upsert.call_args[0][0]
        saved = settings_row.config
        assert saved["model_client_configs"]["orchestrator"] is not None
        assert saved["model_client_configs"]["web_surfer"] is not None

    def test_sandbox_override(self):
        """YAML can override sandbox settings."""
        db = _make_mock_db()
        raw = _make_raw(sandbox={"type": "quicksand", "memory": "8G", "cpus": 4})
        _merge_yaml_into_db(db, raw_yaml=raw, user_id="user1")

        settings_row = db.upsert.call_args[0][0]
        saved = settings_row.config
        assert saved["sandbox"]["memory"] == "8G"
        assert saved["sandbox"]["cpus"] == 4

    def test_sandbox_quicksand_explicit_overrides_null_db(self):
        """YAML explicitly setting quicksand should override null sandbox in DB."""
        existing_config = MagenticUIConfig(sandbox={"type": "null"}).model_dump()
        existing = Settings(user_id="user1", config=existing_config)  # pyright: ignore[reportCallIssue]
        db = _make_mock_db(existing_settings=existing)

        raw = _make_raw(sandbox={"type": "quicksand"})
        _merge_yaml_into_db(db, raw_yaml=raw, user_id="user1")

        settings_row = db.upsert.call_args[0][0]
        saved = settings_row.config
        assert saved["sandbox"]["type"] == "quicksand"

    def test_upsert_failure_returns_false(self):
        db = _make_mock_db()
        db.upsert.return_value.status = False
        db.upsert.return_value.message = "DB error"
        raw = _make_raw(agent_mode="websurfer_only")
        assert _merge_yaml_into_db(db, raw_yaml=raw, user_id="user1") is False


class TestLoadConfigFile:
    """Integration test for load_config_file — reads yaml from disk and merges."""

    def test_reads_yaml_file_and_merges(self, tmp_path: Path):
        """load_config_file reads the yaml from disk and delegates to merge."""
        db = _make_mock_db()
        yaml_path = tmp_path / "config.yaml"
        yaml_path.write_text("agent_mode: websurfer_only\n")

        assert load_config_file(db, config_path=yaml_path, user_id="user1") is True
        settings_row = db.upsert.call_args[0][0]
        assert settings_row.config["agent_mode"] == "websurfer_only"

    def test_empty_file_returns_false(self, tmp_path: Path):
        """Empty yaml file returns False without writing to DB."""
        db = _make_mock_db()
        yaml_path = tmp_path / "config.yaml"
        yaml_path.write_text("")

        assert load_config_file(db, config_path=yaml_path, user_id="user1") is False
        db.upsert.assert_not_called()
