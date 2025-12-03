"""Tests for onboarding route helpers."""

from magentic_ui.backend.web.routes.onboarding import (
    ModelEndpointInput,
    _build_client_dict,
    API_KEY_MASKED,
    _is_onboarding_complete,
    _required_roles,
    _resolve_masked_key,
    _mask_client_dict,
)
from magentic_ui.magentic_ui_config import AgentMode, ROLE_DEFAULTS


class TestBuildClientDict:
    """Tests for _build_client_dict — merges user input with role defaults."""

    def test_orchestrator_basic_fields(self):
        """User-provided fields are set correctly."""
        d = _build_client_dict(
            ModelEndpointInput(
                base_url="http://localhost:6000/v1",
                model="omniagent-v1",
                api_key="my-key",
            ),
            role="orchestrator",
        )
        assert d["config"]["base_url"] == "http://localhost:6000/v1"
        assert d["config"]["model"] == "omniagent-v1"
        assert d["config"]["api_key"] == "my-key"

    def test_web_surfer_basic_fields(self):
        """User-provided fields are set correctly for web_surfer."""
        d = _build_client_dict(
            ModelEndpointInput(
                base_url="http://localhost:5000/v1",
                model="fara-v1",
                api_key="ws-key",
            ),
            role="web_surfer",
        )
        assert d["config"]["base_url"] == "http://localhost:5000/v1"
        assert d["config"]["model"] == "fara-v1"
        assert d["config"]["api_key"] == "ws-key"

    def test_empty_api_key_stays_empty(self):
        """Empty api_key stays empty (no sentinel)."""
        d = _build_client_dict(
            ModelEndpointInput(
                base_url="http://localhost:6000/v1",
                model="omniagent-v1",
                api_key="",
            ),
            role="orchestrator",
        )
        assert d["config"]["api_key"] == ""

    def test_provider_from_defaults(self):
        """Provider comes from role defaults, not user input."""
        d = _build_client_dict(
            ModelEndpointInput(base_url="http://x", model="m"),
            role="orchestrator",
        )
        assert d["provider"] == "OpenAIChatCompletionClient"

    def test_max_retries_from_defaults(self):
        """max_retries comes from role defaults."""
        d = _build_client_dict(
            ModelEndpointInput(base_url="http://x", model="m"),
            role="orchestrator",
        )
        assert d["config"]["max_retries"] == 3

    def test_orchestrator_vision_false(self):
        """Orchestrator model_info has vision=False."""
        d = _build_client_dict(
            ModelEndpointInput(base_url="http://x", model="m"),
            role="orchestrator",
        )
        assert d["config"]["model_info"]["vision"] is False

    def test_web_surfer_vision_true(self):
        """Web surfer model_info has vision=True."""
        d = _build_client_dict(
            ModelEndpointInput(base_url="http://x", model="m"),
            role="web_surfer",
        )
        assert d["config"]["model_info"]["vision"] is True

    def test_model_info_is_independent_copy(self):
        """Each call returns an independent model_info (not shared reference)."""
        d1 = _build_client_dict(
            ModelEndpointInput(base_url="http://x", model="m1"),
            role="orchestrator",
        )
        d2 = _build_client_dict(
            ModelEndpointInput(base_url="http://y", model="m2"),
            role="orchestrator",
        )
        d1["config"]["model_info"]["vision"] = True
        assert d2["config"]["model_info"]["vision"] is False
        assert ROLE_DEFAULTS["orchestrator"]["model_info"]["vision"] is False


class TestRoleDefaults:
    """Tests for ROLE_DEFAULTS configuration."""

    def test_both_roles_defined(self):
        assert "orchestrator" in ROLE_DEFAULTS
        assert "web_surfer" in ROLE_DEFAULTS

    def test_orchestrator_defaults(self):
        d = ROLE_DEFAULTS["orchestrator"]
        assert d["provider"] == "OpenAIChatCompletionClient"
        assert d["model_info"]["vision"] is False

    def test_web_surfer_defaults(self):
        d = ROLE_DEFAULTS["web_surfer"]
        assert d["provider"] == "OpenAIChatCompletionClient"
        assert d["model_info"]["vision"] is True


class TestResolveMaskedKey:
    """Tests for _resolve_masked_key — replaces __MASKED__ with saved DB value."""

    def _make_saved_dict(self, api_key: str) -> dict:
        return {
            "provider": "OpenAIChatCompletionClient",
            "config": {
                "model": "m",
                "api_key": api_key,
                "base_url": "http://x",
                "max_retries": 3,
                "model_info": {"vision": False},
            },
        }

    def test_masked_replaced_with_saved_key(self):
        """__MASKED__ is replaced with the real key from DB."""
        inp = ModelEndpointInput(base_url="http://x", model="m", api_key=API_KEY_MASKED)
        saved = self._make_saved_dict("real-secret-key")
        _resolve_masked_key(inp, saved)
        assert inp.api_key == "real-secret-key"

    def test_new_key_not_replaced(self):
        """A new user-provided key is kept as-is."""
        inp = ModelEndpointInput(base_url="http://x", model="m", api_key="new-key")
        saved = self._make_saved_dict("old-key")
        _resolve_masked_key(inp, saved)
        assert inp.api_key == "new-key"

    def test_empty_key_not_replaced(self):
        """Empty api_key stays empty (user intentionally cleared it)."""
        inp = ModelEndpointInput(base_url="http://x", model="m", api_key="")
        saved = self._make_saved_dict("old-key")
        _resolve_masked_key(inp, saved)
        assert inp.api_key == ""

    def test_masked_with_no_saved_endpoint(self):
        """__MASKED__ with no saved endpoint stays as-is (edge case)."""
        inp = ModelEndpointInput(base_url="http://x", model="m", api_key=API_KEY_MASKED)
        _resolve_masked_key(inp, None)
        assert inp.api_key == API_KEY_MASKED


class TestMaskClientDict:
    """Tests for _mask_client_dict."""

    def test_masks_api_key(self):
        d = {"provider": "P", "config": {"api_key": "secret", "model": "m"}}
        masked = _mask_client_dict(d)
        assert masked is not None
        assert masked["config"]["api_key"] == API_KEY_MASKED
        # Original unchanged
        assert d["config"]["api_key"] == "secret"

    def test_none_returns_none(self):
        assert _mask_client_dict(None) is None


class TestRequiredRoles:
    """Tests for _required_roles — which models a given agent_mode needs."""

    def test_all_requires_both(self):
        assert _required_roles(AgentMode.ALL) == {"orchestrator", "web_surfer"}

    def test_omniagent_only_requires_orchestrator(self):
        assert _required_roles(AgentMode.OMNIAGENT_ONLY) == {"orchestrator"}

    def test_websurfer_only_requires_web_surfer(self):
        assert _required_roles(AgentMode.WEBSURFER_ONLY) == {"web_surfer"}


SAMPLE_CLIENT = {"provider": "P", "config": {"model": "m", "base_url": "http://x"}}


class TestIsOnboardingComplete:
    """Tests for _is_onboarding_complete — agent_mode-aware completion check."""

    def test_all_with_both_models_is_complete(self):
        config = {
            "agent_mode": "all",
            "model_client_configs": {
                "orchestrator": SAMPLE_CLIENT,
                "web_surfer": SAMPLE_CLIENT,
            },
        }
        assert _is_onboarding_complete(config) is True

    def test_all_missing_web_surfer_incomplete(self):
        config = {
            "agent_mode": "all",
            "model_client_configs": {"orchestrator": SAMPLE_CLIENT, "web_surfer": None},
        }
        assert _is_onboarding_complete(config) is False

    def test_omniagent_only_with_orchestrator_is_complete(self):
        config = {
            "agent_mode": "omniagent_only",
            "model_client_configs": {
                "orchestrator": SAMPLE_CLIENT,
                "web_surfer": None,
            },
        }
        assert _is_onboarding_complete(config) is True

    def test_websurfer_only_with_web_surfer_is_complete(self):
        config = {
            "agent_mode": "websurfer_only",
            "model_client_configs": {
                "orchestrator": None,
                "web_surfer": SAMPLE_CLIENT,
            },
        }
        assert _is_onboarding_complete(config) is True

    def test_missing_agent_mode_defaults_to_all(self):
        config = {
            "model_client_configs": {
                "orchestrator": SAMPLE_CLIENT,
                "web_surfer": SAMPLE_CLIENT,
            }
        }
        assert _is_onboarding_complete(config) is True

    def test_invalid_agent_mode_falls_back_to_all(self):
        config = {
            "agent_mode": "garbage",
            "model_client_configs": {
                "orchestrator": SAMPLE_CLIENT,
                "web_surfer": None,
            },
        }
        assert _is_onboarding_complete(config) is False
