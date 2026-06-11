"""Unit tests for FaraQwen3Agent and FaraQwen3NextAgent core agents.

No browser or LLM required — uses mock BrowserEnvironment.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from magentic_ui.agents.web_surfer.fara._fara_qwen3 import (
    FaraQwen3Agent,
    FaraQwen3AgentConfig,
    FaraQwen3AgentState,
    _merge_chat_template_kwargs,
)
from magentic_ui.agents.web_surfer.fara._fara_qwen3_next import (
    FaraQwen3NextAgent,
    FaraQwen3NextAgentConfig,
)
from magentic_ui.agents.web_surfer.fara._fara_web_surfer import FaraWebSurfer
from magentic_ui.agents.web_surfer.fara._types import (
    BrowserEnvironment,
    ImageObj,
    LLMMessage,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_mock_env() -> AsyncMock:
    """Create a mock BrowserEnvironment with all methods as AsyncMock."""
    env = AsyncMock(spec=BrowserEnvironment)
    # get_screenshot returns PNG-like bytes (1x1 white pixel PNG)
    env.get_screenshot.return_value = _minimal_png()
    env.get_url.return_value = "https://www.bing.com"
    env.goto.return_value = None
    return env


def _minimal_png() -> bytes:
    """A small test PNG (100x100 white)."""
    from PIL import Image
    import io

    buf = io.BytesIO()
    Image.new("RGB", (100, 100), "white").save(buf, format="PNG")
    return buf.getvalue()


# ===========================================================================
# FaraQwen3AgentConfig tests
# ===========================================================================


class TestFaraQwen3AgentConfig:
    def test_defaults(self):
        config = FaraQwen3AgentConfig()
        assert config.name == "fara"
        assert config.max_rounds == 10
        assert config.max_n_images == 3
        assert config.fn_call_template == "fara-qwen35vl"
        assert config.viewport_width == 1440
        assert config.viewport_height == 900
        assert config.min_pixels == 3136
        assert config.max_pixels == 12845056

    def test_override(self):
        config = FaraQwen3AgentConfig(name="test", max_rounds=5)
        assert config.name == "test"
        assert config.max_rounds == 5

    def test_client_config(self):
        config = FaraQwen3AgentConfig(
            client_config={"api_key": "test", "base_url": "http://localhost:5000/v1"}
        )
        assert config.client_config is not None
        assert config.client_config["api_key"] == "test"

    def test_disable_thinking_default_true(self):
        assert FaraQwen3AgentConfig().disable_thinking is True


# ===========================================================================
# _make_model_call wiring (stop token + chat_template_kwargs injection)
# ===========================================================================


def _agent_with_mock_create() -> tuple[FaraQwen3Agent, AsyncMock]:
    """Build a FaraQwen3Agent whose chat.completions.create is an AsyncMock."""
    agent = FaraQwen3Agent(
        client_config={
            "api_key": "test-key",
            "base_url": "http://test-endpoint/v1",
            "model": "test/mock-model",
        }
    )
    response = type(
        "R",
        (),
        {"choices": [type("C", (), {"message": type("M", (), {"content": "ok"})()})()]},
    )()
    create = AsyncMock(return_value=response)
    agent._client = type(  # type: ignore[assignment]
        "Client",
        (),
        {
            "chat": type(
                "Ch", (), {"completions": type("Co", (), {"create": create})()}
            )()
        },
    )()
    agent._model = "test/mock-model"
    return agent, create


class TestMakeModelCall:
    @pytest.mark.asyncio
    async def test_injects_stop_and_enable_thinking_by_default(self):
        agent, create = _agent_with_mock_create()
        await agent._make_model_call([])
        kwargs = create.call_args.kwargs
        assert kwargs["stop"] == ["</tool_call>"]
        assert kwargs["extra_body"]["chat_template_kwargs"] == {
            "enable_thinking": False
        }

    @pytest.mark.asyncio
    async def test_skips_extra_body_when_disable_thinking_off(self):
        agent, create = _agent_with_mock_create()
        agent.config.disable_thinking = False
        await agent._make_model_call([])
        assert "extra_body" not in create.call_args.kwargs

    @pytest.mark.asyncio
    async def test_does_not_mutate_caller_args_and_preserves_extra_body(self):
        agent, create = _agent_with_mock_create()
        caller_args: dict = {"extra_body": {"guided_json": {"x": 1}}}
        snapshot = {"extra_body": {"guided_json": {"x": 1}}}
        await agent._make_model_call([], extra_create_args=caller_args)
        assert caller_args == snapshot
        extra_body = create.call_args.kwargs["extra_body"]
        assert extra_body["guided_json"] == {"x": 1}
        assert extra_body["chat_template_kwargs"] == {"enable_thinking": False}


def _terminate_response() -> str:
    return (
        "done\n<tool_call>\n"
        '{"arguments":{"action":"terminate","answer":"done"}}'
        "\n</tool_call>"
    )


class TestGenerateModelCallHistoryMutation:
    @pytest.fixture
    def agent(self) -> FaraQwen3Agent:
        a = FaraQwen3Agent(client_config={"api_key": "test", "base_url": "http://x"})
        a._state = FaraQwen3AgentState(
            chat_history=[LLMMessage(role="user", content="previous turn")],
            mlm_width=100,
            mlm_height=100,
        )
        return a

    @pytest.mark.asyncio
    async def test_failed_continuation_does_not_append_user_message(self, agent):
        from PIL import Image

        env = _make_mock_env()
        agent._get_scaled_screenshot = AsyncMock(  # type: ignore[method-assign]
            return_value=Image.new("RGB", (100, 100), "white")
        )
        agent._get_system_message = lambda screenshot: (  # type: ignore[method-assign]
            [LLMMessage(role="system", content="system")],
            screenshot,
        )
        agent._make_model_call = AsyncMock(  # type: ignore[method-assign]
            side_effect=RuntimeError("Error code: 500")
        )

        with pytest.raises(RuntimeError, match="500"):
            await agent._generate_model_call(
                env,
                is_first_round=False,
                user_response="continue",
            )

        assert agent._state is not None
        assert agent._state.chat_history == [
            LLMMessage(role="user", content="previous turn")
        ]

    @pytest.mark.asyncio
    async def test_successful_continuation_appends_user_then_assistant(self, agent):
        from PIL import Image

        env = _make_mock_env()
        agent._get_scaled_screenshot = AsyncMock(  # type: ignore[method-assign]
            return_value=Image.new("RGB", (100, 100), "white")
        )
        agent._get_system_message = lambda screenshot: (  # type: ignore[method-assign]
            [LLMMessage(role="system", content="system")],
            screenshot,
        )
        agent._make_model_call = AsyncMock(  # type: ignore[method-assign]
            return_value=_terminate_response()
        )

        await agent._generate_model_call(
            env,
            is_first_round=False,
            user_response="continue",
        )

        assert agent._state is not None
        assert [m.role for m in agent._state.chat_history] == [
            "user",
            "user",
            "assistant",
        ]
        resumed_user = agent._state.chat_history[1]
        assert isinstance(resumed_user.content, list)
        assert resumed_user.content[1] == "Current URL: https://www.bing.com\ncontinue"


class TestMergeChatTemplateKwargs:
    def test_caller_chat_template_kwargs_win_on_conflict(self):
        result = _merge_chat_template_kwargs(
            {"chat_template_kwargs": {"enable_thinking": True, "extra": 1}},
            {"enable_thinking": False},
        )
        assert result["chat_template_kwargs"] == {"enable_thinking": True, "extra": 1}


# ===========================================================================
# FaraQwen3Agent init / lifecycle tests
# ===========================================================================


class TestFaraQwen3AgentInit:
    def test_init_with_config(self):
        config = FaraQwen3AgentConfig(
            client_config={"api_key": "test", "base_url": "http://localhost:5000/v1"}
        )
        agent = FaraQwen3Agent(config)
        assert agent.config.name == "fara"
        assert agent._client is None
        assert agent._state is None

    def test_init_with_dict(self):
        agent = FaraQwen3Agent(
            config={"client_config": {"api_key": "k", "base_url": "http://x"}}
        )
        assert isinstance(agent.config, FaraQwen3AgentConfig)

    def test_init_with_kwargs(self):
        agent = FaraQwen3Agent(
            client_config={"api_key": "k", "base_url": "http://x"},
            max_rounds=5,
        )
        assert agent.config.max_rounds == 5

    @pytest.mark.asyncio
    async def test_initialize_uses_default_model_when_unset(self):
        agent = FaraQwen3Agent(
            client_config={"api_key": "test", "base_url": "http://localhost:5000/v1"}
        )
        await agent.initialize()
        assert agent._state is not None
        assert agent._client is not None
        assert agent._model == "microsoft/Fara-7B"
        assert agent._state.mlm_width == 1440
        assert agent._state.mlm_height == 900

    @pytest.mark.asyncio
    async def test_initialize_honors_configured_values(self):
        agent = FaraQwen3Agent(
            client_config={
                "api_key": "configured-key",
                "base_url": "http://my-vllm.test:9999/v1",
                "model": "custom/model-name",
            }
        )
        await agent.initialize()
        assert agent._model == "custom/model-name"
        assert agent._client is not None
        assert agent._client.api_key == "configured-key"
        assert str(agent._client.base_url).rstrip("/") == "http://my-vllm.test:9999/v1"

    @pytest.mark.asyncio
    async def test_initialize_with_empty_api_key(self, monkeypatch):
        # Onboarding stores api_key="" when the user leaves the field
        # blank (e.g. local vLLM endpoint that needs no key). The shared
        # create_openai_client helper falls back to OPENAI_API_KEY, then
        # to a placeholder, so initialize() must not raise.
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        agent = FaraQwen3Agent(
            client_config={"api_key": "", "base_url": "http://my-vllm.test:9999/v1"}
        )
        await agent.initialize()
        assert agent._client is not None
        assert agent._client.api_key == "not-needed"

    @pytest.mark.asyncio
    async def test_initialize_requires_client_config(self):
        agent = FaraQwen3Agent(config=FaraQwen3AgentConfig())
        with pytest.raises(ValueError, match="client_config must be provided"):
            await agent.initialize()

    @pytest.mark.asyncio
    async def test_close_clears_state(self):
        agent = FaraQwen3Agent(
            client_config={"api_key": "test", "base_url": "http://localhost:5000/v1"}
        )
        await agent.initialize()
        await agent.close()
        assert agent._state is None
        assert agent._client is None
        assert agent._model is None


# ===========================================================================
# Parsing tests
# ===========================================================================


class TestParseThoughtsAndAction:
    @pytest.fixture
    def agent(self) -> FaraQwen3Agent:
        return FaraQwen3Agent(client_config={"api_key": "test", "base_url": "http://x"})

    def test_parse_valid_visit_url(self, agent):
        message = """I need to navigate to GitHub.
<tool_call>
{"name": "computer_use", "arguments": {"action": "visit_url", "url": "https://github.com"}}
</tool_call>"""
        thoughts, action = agent._parse_thoughts_and_action(message)
        assert thoughts == "I need to navigate to GitHub."
        assert action["arguments"]["action"] == "visit_url"
        assert action["arguments"]["url"] == "https://github.com"

    def test_parse_valid_click(self, agent):
        message = """I will click the button.
<tool_call>
{"name": "computer_use", "arguments": {"action": "click", "coordinate": [500, 300]}}
</tool_call>"""
        thoughts, action = agent._parse_thoughts_and_action(message)
        assert thoughts == "I will click the button."
        assert action["arguments"]["coordinate"] == [500, 300]

    def test_parse_multiline_thoughts(self, agent):
        message = """Looking at the page:
1. A search box
2. Login button

I'll click login.
<tool_call>
{"name": "computer_use", "arguments": {"action": "click", "coordinate": [100, 50]}}
</tool_call>"""
        thoughts, action = agent._parse_thoughts_and_action(message)
        assert "Looking at the page" in thoughts
        assert "I'll click login." in thoughts

    def test_parse_python_dict_fallback(self, agent):
        message = """Clicking.
<tool_call>
{'name': 'computer_use', 'arguments': {'action': 'click', 'coordinate': [100, 200]}}
</tool_call>"""
        thoughts, action = agent._parse_thoughts_and_action(message)
        assert action["arguments"]["action"] == "click"

    def test_parse_missing_tool_call_raises(self, agent):
        with pytest.raises(Exception):
            agent._parse_thoughts_and_action("No tool call here")


# ===========================================================================
# Coordinate scaling tests
# ===========================================================================


class TestProcCoords:
    @pytest.fixture
    def agent(self) -> FaraQwen3Agent:
        return FaraQwen3Agent(client_config={"api_key": "test", "base_url": "http://x"})

    def test_display_to_viewport(self, agent):
        """DISPLAY_SIZE=1000 → viewport 1440x900."""
        coords = agent.proc_coords([500, 500], 1000, 1000, 1440, 900)
        assert coords == [720.0, 450.0]

    def test_same_size(self, agent):
        coords = agent.proc_coords([100, 200], 1000, 1000, 1000, 1000)
        assert coords == [100.0, 200.0]

    def test_none_returns_none(self, agent):
        assert agent.proc_coords(None, 1000, 1000) is None

    def test_empty_returns_empty(self, agent):
        assert agent.proc_coords([], 1000, 1000) == []

    def test_origin_corner(self, agent):
        """Origin (0,0) stays at (0,0) regardless of scaling."""
        coords = agent.proc_coords([0, 0], 1000, 1000, 1440, 900)
        assert coords == [0.0, 0.0]

    def test_bottom_right_corner(self, agent):
        """Bottom-right of DISPLAY_SIZE maps to bottom-right of viewport."""
        coords = agent.proc_coords([1000, 1000], 1000, 1000, 1440, 900)
        assert coords == [1440.0, 900.0]


# ===========================================================================
# Screenshot management tests
# ===========================================================================


class TestMaybeRemoveOldScreenshots:
    @pytest.fixture
    def agent(self) -> FaraQwen3Agent:
        return FaraQwen3Agent(
            client_config={"api_key": "test", "base_url": "http://x"},
            max_n_images=3,
        )

    def _msg_with_image(
        self, text: str = "msg", is_original: bool = False
    ) -> LLMMessage:
        from PIL import Image

        img = Image.new("RGB", (10, 10))
        metadata = {"is_original": True} if is_original else None
        return LLMMessage(
            role="user",
            content=[ImageObj.from_pil(img), text],
            metadata=metadata,
        )

    def _msg_text_only(self, text: str = "assistant response") -> LLMMessage:
        return LLMMessage(role="assistant", content=text)

    def test_under_limit_keeps_all(self, agent):
        history = [self._msg_with_image(), self._msg_text_only()]
        result = agent.maybe_remove_old_screenshots(history)
        assert len(result) == 2

    def test_over_limit_strips_oldest(self, agent):
        history = [
            self._msg_with_image("1"),
            self._msg_text_only(),
            self._msg_with_image("2"),
            self._msg_text_only(),
            self._msg_with_image("3"),
            self._msg_text_only(),
            self._msg_with_image("4"),
        ]
        result = agent.maybe_remove_old_screenshots(history)
        # max_n_images=3, includes_current=False → keep 2 images
        image_msgs = [
            m
            for m in result
            if isinstance(m.content, list)
            and any(isinstance(c, ImageObj) for c in m.content)
        ]
        assert len(image_msgs) <= 3

    def test_preserves_original_text(self, agent):
        history = [
            self._msg_with_image("task instruction", is_original=True),
            self._msg_text_only(),
            self._msg_with_image("2"),
            self._msg_text_only(),
            self._msg_with_image("3"),
            self._msg_text_only(),
            self._msg_with_image("4"),
        ]
        result = agent.maybe_remove_old_screenshots(history)
        # Original message text should be preserved even if image stripped
        first = result[0]
        if isinstance(first.content, list):
            texts = [c for c in first.content if isinstance(c, str)]
            assert any("task instruction" in t for t in texts)
        elif isinstance(first.content, str):
            assert "task instruction" in first.content

    def test_text_only_messages_always_kept(self, agent):
        history = [
            self._msg_with_image("1"),
            self._msg_text_only("response1"),
            self._msg_with_image("2"),
            self._msg_text_only("response2"),
            self._msg_with_image("3"),
            self._msg_text_only("response3"),
            self._msg_with_image("4"),
            self._msg_text_only("response4"),
        ]
        result = agent.maybe_remove_old_screenshots(history)
        text_msgs = [m for m in result if isinstance(m.content, str)]
        assert len(text_msgs) == 4

    def test_first_message_keeps_text_without_mutating_source(self, agent):
        history = [
            self._msg_with_image("old observation"),
            self._msg_text_only("response1"),
            self._msg_with_image("newer observation"),
            self._msg_text_only("response2"),
            self._msg_with_image("current observation"),
        ]

        result = agent.maybe_remove_old_screenshots(history)

        assert isinstance(history[0].content, list)
        assert any(isinstance(c, ImageObj) for c in history[0].content)
        assert isinstance(result[0].content, list)
        assert result[0].content == ["old observation"]


class TestFaraWebSurferResumeState:
    def _surfer_with_restored_history(
        self,
        side_effect,
        *,
        max_rounds: int = 3,
    ) -> tuple[FaraWebSurfer, FaraQwen3Agent]:
        surfer = FaraWebSurfer(
            model_client_config={"api_key": "test", "base_url": "http://x"}
        )
        agent = FaraQwen3Agent(
            client_config={"api_key": "test", "base_url": "http://x"},
            max_rounds=max_rounds,
        )
        agent._state = FaraQwen3AgentState(
            chat_history=[LLMMessage(role="user", content="previous task")]
        )
        agent._generate_model_call = AsyncMock(  # type: ignore[method-assign]
            side_effect=side_effect
        )
        surfer._agent = agent
        surfer._env = _make_mock_env()
        surfer._lazy_init = AsyncMock(return_value=None)  # type: ignore[method-assign]
        return surfer, agent

    @pytest.mark.asyncio
    async def test_restored_run_uses_task_as_continuation(self):
        action = {
            "arguments": {
                "action": "terminate",
                "answer": "done",
                "thoughts": "done",
            }
        }
        surfer, agent = self._surfer_with_restored_history([(action, "raw")])

        updates = [update async for update in surfer.run_stream("continue")]

        assert updates
        call = agent._generate_model_call.call_args  # type: ignore[attr-defined]
        assert call.args[1] is False
        assert call.args[2] is None
        assert call.kwargs["user_response"] == "continue"
        assert agent._state is not None
        assert agent._state.chat_history == [
            LLMMessage(role="user", content="previous task")
        ]

    @pytest.mark.asyncio
    async def test_model_api_error_is_not_injected_into_retry_prompt(self):
        action = {
            "arguments": {
                "action": "terminate",
                "answer": "done",
                "thoughts": "done",
            }
        }
        surfer, agent = self._surfer_with_restored_history(
            [RuntimeError("Error code: 500"), (action, "raw")],
            max_rounds=2,
        )

        updates = [update async for update in surfer.run_stream("continue")]

        # Ignore the transient ``calling_model`` agent_state signals emitted
        # before each model call; only the two substantive updates matter.
        content_updates = [
            u
            for u in updates
            if (u.additional_properties or {}).get("type") != "agent_state"
        ]
        assert len(content_updates) == 2
        calls = agent._generate_model_call.call_args_list  # type: ignore[attr-defined]
        assert calls[0].kwargs["user_response"] == "continue"
        assert calls[1].kwargs["user_response"] == "continue"


class TestFaraWebSurferUserInbox:
    """Mid-run user messages queued on the shared PauseController are
    drained at the top of Fara's action loop and joined into the next
    _generate_model_call's user_response."""

    def _surfer(
        self,
        side_effect,
        pause_controller,
        *,
        max_rounds: int = 3,
    ) -> tuple[FaraWebSurfer, FaraQwen3Agent]:
        from magentic_ui.types import PauseController as _PC  # noqa: F401

        surfer = FaraWebSurfer(
            model_client_config={"api_key": "test", "base_url": "http://x"},
            pause_controller=pause_controller,
        )
        agent = FaraQwen3Agent(
            client_config={"api_key": "test", "base_url": "http://x"},
            max_rounds=max_rounds,
        )
        # Restored history avoids the first-round screenshot path that
        # requires a real BrowserEnvironment screenshot pipeline.
        agent._state = FaraQwen3AgentState(
            chat_history=[LLMMessage(role="user", content="previous task")]
        )
        agent._generate_model_call = AsyncMock(  # type: ignore[method-assign]
            side_effect=side_effect
        )
        surfer._agent = agent
        surfer._env = _make_mock_env()
        surfer._lazy_init = AsyncMock(return_value=None)  # type: ignore[method-assign]
        return surfer, agent

    @pytest.mark.asyncio
    async def test_queued_message_joined_into_next_user_response(self):
        from magentic_ui.types import PauseController

        action = {
            "arguments": {
                "action": "terminate",
                "answer": "done",
                "thoughts": "done",
            }
        }
        pc = PauseController()
        # Queue the message before the run starts so the very first round
        # picks it up via the drain at the top of the loop.
        pc.queue_message("also note: skip step 3")
        surfer, agent = self._surfer([(action, "raw")], pc)

        async for _ in surfer.run_stream("continue"):
            pass

        call = agent._generate_model_call.call_args  # type: ignore[attr-defined]
        # restored-history path sets _pending_user_response = task ("continue").
        # Drain joins queued messages after, so user_response carries both.
        assert "continue" in call.kwargs["user_response"]
        assert "also note: skip step 3" in call.kwargs["user_response"]
        # Existing task comes before the mailbox addition (chronological order).
        assert call.kwargs["user_response"].index("continue") < call.kwargs[
            "user_response"
        ].index("also note: skip step 3")
        # Inbox drained.
        assert pc.has_queued_messages is False

    @pytest.mark.asyncio
    async def test_multiple_queued_messages_joined_with_newlines(self):
        from magentic_ui.types import PauseController

        action = {
            "arguments": {
                "action": "terminate",
                "answer": "done",
                "thoughts": "done",
            }
        }
        pc = PauseController()
        pc.queue_message("first")
        pc.queue_message("second")
        surfer, agent = self._surfer([(action, "raw")], pc)

        async for _ in surfer.run_stream("continue"):
            pass

        user_response = agent._generate_model_call.call_args.kwargs[  # type: ignore[attr-defined]
            "user_response"
        ]
        assert "first\nsecond" in user_response

    @pytest.mark.asyncio
    async def test_empty_inbox_leaves_user_response_unchanged(self):
        """Without any queued message, behavior matches the existing
        restored-history flow (user_response == task)."""
        from magentic_ui.types import PauseController

        action = {
            "arguments": {
                "action": "terminate",
                "answer": "done",
                "thoughts": "done",
            }
        }
        pc = PauseController()
        surfer, agent = self._surfer([(action, "raw")], pc)

        async for _ in surfer.run_stream("continue"):
            pass

        assert (
            agent._generate_model_call.call_args.kwargs[  # type: ignore[attr-defined]
                "user_response"
            ]
            == "continue"
        )


class TestFaraWebSurferAgentState:
    """FaraWebSurfer emits a transient ``calling_model`` agent_state signal
    before each (non-streaming) model call so the UI can show
    "Waiting for model…". FARA never streams tokens, so it does not emit
    ``thinking``."""

    def _surfer(
        self, side_effect, *, max_rounds: int = 3
    ) -> tuple[FaraWebSurfer, FaraQwen3Agent]:
        surfer = FaraWebSurfer(
            model_client_config={"api_key": "test", "base_url": "http://x"},
        )
        agent = FaraQwen3Agent(
            client_config={"api_key": "test", "base_url": "http://x"},
            max_rounds=max_rounds,
        )
        agent._state = FaraQwen3AgentState(
            chat_history=[LLMMessage(role="user", content="previous task")]
        )
        agent._generate_model_call = AsyncMock(  # type: ignore[method-assign]
            side_effect=side_effect
        )
        surfer._agent = agent
        surfer._env = _make_mock_env()
        surfer._lazy_init = AsyncMock(return_value=None)  # type: ignore[method-assign]
        return surfer, agent

    @pytest.mark.asyncio
    async def test_emits_calling_model_before_model_call(self):
        action = {
            "arguments": {
                "action": "terminate",
                "answer": "done",
                "thoughts": "done",
            }
        }
        surfer, _ = self._surfer([(action, "raw")])

        events = [evt async for evt in surfer.run_stream("go")]

        states = [
            (evt.additional_properties or {}).get("state")
            for evt in events
            if (evt.additional_properties or {}).get("type") == "agent_state"
        ]
        # calling_model is emitted (at least once, before the model call);
        # generating is never emitted because FARA does not stream tokens.
        assert "calling_model" in states
        assert "generating" not in states


# ===========================================================================
# Action execution tests (mock BrowserEnvironment)
# ===========================================================================


class TestExecuteAction:
    @pytest.fixture
    def agent(self) -> FaraQwen3Agent:
        a = FaraQwen3Agent(client_config={"api_key": "test", "base_url": "http://x"})
        # Manually set state (bypass initialize which needs real OpenAI)
        a._state = FaraQwen3AgentState(mlm_width=1440, mlm_height=900)
        return a

    @pytest.mark.asyncio
    async def test_visit_url(self, agent):
        env = _make_mock_env()
        is_stop, desc = await agent._execute_action(
            env, {"action": "visit_url", "url": "https://example.com"}
        )
        assert is_stop is False
        assert desc == "I typed 'https://example.com' into the browser address bar."
        env.goto.assert_called_once_with("https://example.com")

    @pytest.mark.asyncio
    async def test_visit_url_adds_https(self, agent):
        env = _make_mock_env()
        await agent._execute_action(env, {"action": "visit_url", "url": "example.com"})
        env.goto.assert_called_once_with("https://example.com")

    @pytest.mark.asyncio
    async def test_visit_url_search_query(self, agent):
        env = _make_mock_env()
        await agent._execute_action(
            env, {"action": "visit_url", "url": "python tutorial"}
        )
        call_url = env.goto.call_args[0][0]
        assert "bing.com/search" in call_url
        assert "python+tutorial" in call_url

    @pytest.mark.asyncio
    async def test_history_back(self, agent):
        env = _make_mock_env()
        is_stop, desc = await agent._execute_action(env, {"action": "history_back"})
        assert is_stop is False
        env.back.assert_called_once()

    @pytest.mark.asyncio
    async def test_web_search(self, agent):
        env = _make_mock_env()
        await agent._execute_action(
            env, {"action": "web_search", "query": "pytest docs"}
        )
        call_url = env.goto.call_args[0][0]
        assert "bing.com/search" in call_url
        assert "pytest+docs" in call_url

    @pytest.mark.asyncio
    async def test_scroll_up(self, agent):
        env = _make_mock_env()
        is_stop, desc = await agent._execute_action(
            env, {"action": "scroll", "pixels": 300}
        )
        assert "scrolled up" in desc
        env.scroll_up.assert_called_once()

    @pytest.mark.asyncio
    async def test_scroll_down(self, agent):
        env = _make_mock_env()
        await agent._execute_action(env, {"action": "scroll", "pixels": -300})
        env.scroll_down.assert_called_once()

    @pytest.mark.asyncio
    async def test_click(self, agent):
        env = _make_mock_env()
        # Coords in DISPLAY_SIZE (1000) → scaled to viewport (1440x900)
        await agent._execute_action(
            env, {"action": "left_click", "coordinate": [500, 500]}
        )
        env.left_click.assert_called_once_with(720.0, 450.0)

    @pytest.mark.asyncio
    async def test_type_text(self, agent):
        env = _make_mock_env()
        await agent._execute_action(
            env,
            {
                "action": "type",
                "text": "hello",
                "coordinate": [500, 500],
                "press_enter": False,
            },
        )
        env.type_text.assert_called_once_with(
            720.0, 450.0, "hello", press_enter=False, clear_first=False
        )

    @pytest.mark.asyncio
    async def test_key(self, agent):
        env = _make_mock_env()
        await agent._execute_action(env, {"action": "key", "keys": ["Enter"]})
        env.key.assert_called_once_with(["Enter"])

    @pytest.mark.asyncio
    async def test_terminate(self, agent):
        env = _make_mock_env()
        is_stop, desc = await agent._execute_action(
            env, {"action": "terminate", "thoughts": "Done"}
        )
        assert is_stop is True
        assert desc == "Done"

    @pytest.mark.asyncio
    async def test_memorize_fact(self, agent):
        env = _make_mock_env()
        await agent._execute_action(
            env, {"action": "pause_and_memorize_fact", "fact": "Price is $10"}
        )
        assert "Price is $10" in agent._state.facts

    @pytest.mark.asyncio
    async def test_unknown_action_raises(self, agent):
        env = _make_mock_env()
        with pytest.raises(ValueError, match="Unknown action"):
            await agent._execute_action(env, {"action": "fly_to_moon"})


# ===========================================================================
# FaraQwen3NextAgent tests
# ===========================================================================


class TestFaraQwen3NextAgentConfig:
    def test_defaults(self):
        config = FaraQwen3NextAgentConfig()
        assert config.name == "fara_next"
        assert config.tools == ["BROWSER_TOOLS_CORE"]
        # Inherits parent defaults
        assert config.fn_call_template == "fara-qwen35vl"

    def test_inherits_parent(self):
        assert issubclass(FaraQwen3NextAgentConfig, FaraQwen3AgentConfig)


class TestFaraQwen3NextAgentInit:
    def test_inherits_parent(self):
        assert issubclass(FaraQwen3NextAgent, FaraQwen3Agent)

    def test_init(self):
        agent = FaraQwen3NextAgent(
            client_config={"api_key": "test", "base_url": "http://x"}
        )
        assert agent._computer_use_mode == "fara_next_browser"
        assert agent._cursor_x == 0.0
        assert agent._cursor_y == 0.0

    @pytest.mark.asyncio
    async def test_initialize_sets_mode(self):
        agent = FaraQwen3NextAgent(
            client_config={"api_key": "test", "base_url": "http://x"},
            tools=["BROWSER_TOOLS_CORE"],
        )
        await agent.initialize()
        assert agent._computer_use_mode == "fara_next_browser"

    def test_get_final_answer_returns_description(self):
        agent = FaraQwen3NextAgent(
            client_config={"api_key": "test", "base_url": "http://x"}
        )
        result = agent._get_final_answer("my thoughts", "the answer is 42")
        assert result == "the answer is 42"


class TestFaraQwen3NextExecuteAction:
    @pytest.fixture
    def agent(self) -> FaraQwen3NextAgent:
        a = FaraQwen3NextAgent(
            client_config={"api_key": "test", "base_url": "http://x"}
        )
        a._state = FaraQwen3AgentState(mlm_width=1440, mlm_height=900)
        return a

    @pytest.mark.asyncio
    async def test_double_click(self, agent):
        env = _make_mock_env()
        is_stop, desc = await agent._execute_action(
            env, {"action": "double_click", "coordinate": [500, 500]}
        )
        assert is_stop is False
        assert "double-clicked" in desc
        env.double_click.assert_called_once_with(720.0, 450.0)
        assert agent._cursor_x == 720.0
        assert agent._cursor_y == 450.0

    @pytest.mark.asyncio
    async def test_right_click(self, agent):
        env = _make_mock_env()
        await agent._execute_action(
            env, {"action": "right_click", "coordinate": [500, 500]}
        )
        env.right_click.assert_called_once_with(720.0, 450.0)

    @pytest.mark.asyncio
    async def test_triple_click(self, agent):
        env = _make_mock_env()
        await agent._execute_action(
            env, {"action": "triple_click", "coordinate": [500, 500]}
        )
        env.triple_click.assert_called_once_with(720.0, 450.0)

    @pytest.mark.asyncio
    async def test_left_click_drag(self, agent):
        env = _make_mock_env()
        await agent._execute_action(
            env, {"action": "left_click_drag", "coordinate": [500, 500]}
        )
        env.left_click_drag.assert_called_once_with(720.0, 450.0)

    @pytest.mark.asyncio
    async def test_hscroll(self, agent):
        env = _make_mock_env()
        # pixels=100 in DISPLAY_SIZE → scaled by viewport_width/DISPLAY_SIZE
        await agent._execute_action(env, {"action": "hscroll", "pixels": 100})
        expected_pixels = int(100 * 1440 / 1000)
        env.hscroll.assert_called_once_with(expected_pixels)

    @pytest.mark.asyncio
    async def test_scroll_scaled(self, agent):
        env = _make_mock_env()
        # FaraQwen3Next scales scroll pixels by viewport_height/DISPLAY_SIZE
        await agent._execute_action(env, {"action": "scroll", "pixels": -100})
        expected_amount = abs(int(-100 * 900 / 1000))
        env.scroll_down.assert_called_once_with(expected_amount)

    @pytest.mark.asyncio
    async def test_type_direct(self, agent):
        env = _make_mock_env()
        # FaraQwen3Next "type" action uses type_direct (no coordinates)
        await agent._execute_action(env, {"action": "type", "text": "hello world"})
        env.type_direct.assert_called_once_with("hello world")

    @pytest.mark.asyncio
    async def test_ask_user_question(self, agent):
        env = _make_mock_env()
        is_stop, desc = await agent._execute_action(
            env, {"action": "ask_user_question", "question": "What city?"}
        )
        assert is_stop is True
        assert "What city?" in desc

    @pytest.mark.asyncio
    async def test_run_command(self, agent):
        env = _make_mock_env()
        env.execute.return_value = "file1.txt\nfile2.txt"
        is_stop, desc = await agent._execute_action(
            env, {"action": "run_command", "command": "ls"}
        )
        assert is_stop is False
        assert "ls" in desc
        assert "file1.txt" in desc

    @pytest.mark.asyncio
    async def test_terminate_with_answer(self, agent):
        env = _make_mock_env()
        is_stop, desc = await agent._execute_action(
            env, {"action": "terminate", "answer": "The price is $42"}
        )
        assert is_stop is True
        assert desc == "The price is $42"

    @pytest.mark.asyncio
    async def test_terminate_missing_answer_raises(self, agent):
        env = _make_mock_env()
        with pytest.raises(ValueError, match="requires 'answer'"):
            await agent._execute_action(env, {"action": "terminate"})

    @pytest.mark.asyncio
    async def test_delegates_parent_actions(self, agent):
        """Actions not in _NEW_ACTIONS delegate to parent."""
        env = _make_mock_env()
        await agent._execute_action(env, {"action": "history_back"})
        env.back.assert_called_once()

    @pytest.mark.asyncio
    async def test_cursor_tracked_on_parent_actions(self, agent):
        """Cursor is tracked even for parent actions with coordinates."""
        env = _make_mock_env()
        await agent._execute_action(
            env, {"action": "left_click", "coordinate": [500, 500]}
        )
        # Parent handles left_click, but FaraQwen3Next tracks cursor
        assert agent._cursor_x == 720.0
        assert agent._cursor_y == 450.0
