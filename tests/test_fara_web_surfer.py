import pytest
from magentic_ui.agents.web_surfer.fara._fara_web_surfer import FaraWebSurfer


class TestParseThoughtsAndAction:
    """Tests for the _parse_thoughts_and_action method of FaraWebSurfer."""

    @pytest.fixture
    def surfer(self):
        """Create a minimal FaraWebSurfer instance for testing."""
        # We need to pass minimal required parameters
        # The method we're testing doesn't require full initialization
        surfer = object.__new__(FaraWebSurfer)
        # Initialize only what's needed for _parse_thoughts_and_action
        import logging

        surfer.logger = logging.getLogger(__name__)
        return surfer

    def test_parse_valid_message(self, surfer):
        """Test parsing a valid message with tool_call tags."""
        message = """I need to click the button.
<tool_call>
{"name": "click", "arguments": {"action": "click", "target_id": "10"}}
</tool_call>"""

        thoughts, action = surfer._parse_thoughts_and_action(message)

        assert thoughts == "I need to click the button."
        assert action["name"] == "click"
        assert action["arguments"]["action"] == "click"
        assert action["arguments"]["target_id"] == "10"

    def test_parse_empty_message_raises_error(self, surfer):
        """Test that empty message raises ValueError with helpful message."""
        with pytest.raises(ValueError) as exc_info:
            surfer._parse_thoughts_and_action("")

        assert "Empty response from model" in str(exc_info.value)
        assert "vLLM" in str(exc_info.value)

    def test_parse_whitespace_only_message_raises_error(self, surfer):
        """Test that whitespace-only message raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            surfer._parse_thoughts_and_action("   \n\t  ")

        assert "Empty response from model" in str(exc_info.value)

    def test_parse_missing_tool_call_tag_raises_error(self, surfer):
        """Test that message without tool_call tag raises ValueError."""
        message = "I want to click the button but no tool call here."

        with pytest.raises(ValueError) as exc_info:
            surfer._parse_thoughts_and_action(message)

        error_msg = str(exc_info.value)
        # Error message should contain helpful debugging info
        assert "missing required <tool_call> tag" in error_msg
        assert "Received response:" in error_msg

    def test_parse_tool_call_without_newline(self, surfer):
        """Test parsing when tool_call tag is not followed by newline."""
        message = """Thinking about action.
<tool_call>{"name": "scroll", "arguments": {"action": "scroll", "pixels": 100}}</tool_call>"""

        thoughts, action = surfer._parse_thoughts_and_action(message)

        assert thoughts == "Thinking about action."
        assert action["name"] == "scroll"
        assert action["arguments"]["action"] == "scroll"

    def test_parse_empty_tool_call_content_raises_error(self, surfer):
        """Test that empty content inside tool_call tags raises ValueError."""
        message = """Some thoughts.
<tool_call>
</tool_call>"""

        with pytest.raises(ValueError) as exc_info:
            surfer._parse_thoughts_and_action(message)

        assert "Empty tool call content" in str(exc_info.value)

    def test_parse_invalid_json_falls_back_to_ast(self, surfer):
        """Test that invalid JSON falls back to ast.literal_eval."""
        # Python dict literal syntax (single quotes instead of double)
        message = """Clicking button.
<tool_call>
{'name': 'click', 'arguments': {'action': 'click'}}
</tool_call>"""

        thoughts, action = surfer._parse_thoughts_and_action(message)

        assert thoughts == "Clicking button."
        assert action["name"] == "click"

    def test_parse_long_message_truncates_in_error(self, surfer):
        """Test that long messages are truncated in error messages."""
        long_content = "x" * 300  # More than 200 characters

        with pytest.raises(ValueError) as exc_info:
            surfer._parse_thoughts_and_action(long_content)

        error_message = str(exc_info.value)
        assert "..." in error_message
        # Verify it was truncated to around 200 chars plus the ellipsis

    def test_parse_complex_action(self, surfer):
        """Test parsing a complex action with nested arguments."""
        message = """I will navigate to the search page and enter the query.
<tool_call>
{"name": "input_text", "arguments": {"action": "input_text", "text": "hello world", "coordinate": [100, 200], "press_enter": true}}
</tool_call>"""

        thoughts, action = surfer._parse_thoughts_and_action(message)

        assert "navigate to the search page" in thoughts
        assert action["name"] == "input_text"
        assert action["arguments"]["text"] == "hello world"
        assert action["arguments"]["coordinate"] == [100, 200]
        assert action["arguments"]["press_enter"] is True

    def test_parse_terminate_action(self, surfer):
        """Test parsing a terminate/stop action."""
        message = """The task is complete. I found the answer.
<tool_call>
{"name": "terminate", "arguments": {"action": "terminate", "thoughts": "Task completed successfully"}}
</tool_call>"""

        thoughts, action = surfer._parse_thoughts_and_action(message)

        assert "task is complete" in thoughts.lower()
        assert action["arguments"]["action"] == "terminate"
