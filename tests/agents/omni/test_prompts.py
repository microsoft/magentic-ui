"""Tests for OmniAgent system prompt generation.

Verifies that tools and capabilities control which sections appear in the
system prompt. Filtering by agent_mode happens upstream in OmniAgent.
"""

from pathlib import Path

from magentic_ui.agents.base import Capability
from magentic_ui.sandbox._null import NullSandbox
from magentic_ui.teams.omniagent._registry import DELEGATE_CUA_DEF, TOOLS, Tool
from magentic_ui.teams.omniagent._system_prompt import build_system_prompt

_WEB_TOOLS = [Tool(name="delegate_cua", definition=DELEGATE_CUA_DEF)]


class TestGetSystemPrompt:
    def test_core_only_excludes_delegate_cua(self) -> None:
        prompt = build_system_prompt(TOOLS, "/workspace")
        assert "delegate_cua" not in prompt

    def test_core_only_excludes_web_guidelines(self) -> None:
        prompt = build_system_prompt(TOOLS, "/workspace")
        assert "Web Browsing Delegation" not in prompt
        assert "After the web agent" not in prompt

    def test_core_only_includes_core_tools(self) -> None:
        prompt = build_system_prompt(TOOLS, "/workspace")
        for tool in [
            "bash",
            "create",
            "open",
            "edit",
            "insert",
            "search_dir",
            "request_user_input",
        ]:
            assert tool in prompt

    def test_with_web_tools_includes_delegate_cua(self) -> None:
        prompt = build_system_prompt(
            TOOLS + _WEB_TOOLS,
            "/workspace",
            capabilities=frozenset({Capability.WEB_BROWSING}),
        )
        assert "delegate_cua" in prompt

    def test_web_capability_includes_web_guidelines(self) -> None:
        prompt = build_system_prompt(
            TOOLS + _WEB_TOOLS,
            "/workspace",
            capabilities=frozenset({Capability.WEB_BROWSING}),
        )
        assert "Web Browsing Delegation" in prompt
        assert "After the web agent" in prompt

    def test_working_dir_appears_in_prompt(self) -> None:
        prompt = build_system_prompt(TOOLS, "/my/dir")
        assert "/my/dir" in prompt

    def test_core_includes_followup_turns_block(self) -> None:
        prompt = build_system_prompt(TOOLS, "/workspace")
        assert "## Follow-up turns" in prompt
        assert "only record of work already done" in prompt

    def test_followup_turns_block_present_with_web_too(self) -> None:
        prompt = build_system_prompt(
            TOOLS + _WEB_TOOLS,
            "/workspace",
            capabilities=frozenset({Capability.WEB_BROWSING}),
        )
        assert "## Follow-up turns" in prompt

    def test_web_capability_includes_followup_reuse_sentence(self) -> None:
        prompt = build_system_prompt(
            TOOLS + _WEB_TOOLS,
            "/workspace",
            capabilities=frozenset({Capability.WEB_BROWSING}),
        )
        assert "never search the filesystem, transcripts, or logs" in prompt

    def test_core_only_excludes_followup_reuse_sentence(self) -> None:
        prompt = build_system_prompt(TOOLS, "/workspace")
        assert "never search the filesystem, transcripts, or logs" not in prompt

    def test_no_web_guidelines_without_capability(self) -> None:
        """Even with delegate_cua in tools, no web guidelines without capability."""
        prompt = build_system_prompt(TOOLS + _WEB_TOOLS, "/workspace")
        assert "Web Browsing Delegation" not in prompt

    def test_no_sandbox_hint_when_sandbox_none(self) -> None:
        prompt = build_system_prompt(TOOLS, "/workspace")
        assert "Workspace and User Environment" not in prompt

    def test_null_sandbox_hint_present(self, tmp_path: Path) -> None:
        prompt = build_system_prompt(
            TOOLS,
            "/workspace",
            sandbox=NullSandbox(workspace=tmp_path),
        )
        assert "Workspace and User Environment" in prompt
        assert "running directly on the user's host machine" in prompt
        # NullSandbox framing should NOT include the ephemeral-VM language.
        assert "rest of the VM is ephemeral" not in prompt

    def test_quicksand_sandbox_hint_present(self) -> None:
        # Stand-in for a non-NullSandbox: any object that isn't a NullSandbox
        # instance gets the Quicksand framing.
        class _FakeSandbox:
            pass

        prompt = build_system_prompt(
            TOOLS,
            "/workspace",
            sandbox=_FakeSandbox(),  # type: ignore[arg-type]
        )
        assert "Workspace and User Environment" in prompt
        assert "rest of the VM is ephemeral" in prompt
        # Quicksand framing should NOT include the host-machine language.
        assert "running directly on the user's host machine" not in prompt
