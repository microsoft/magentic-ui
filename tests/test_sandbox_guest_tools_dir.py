"""Sandbox.guest_tools_dir wiring — each backend exposes a path that the
agent shell can use to locate magui_tools and scripts/search.sh."""

from __future__ import annotations

from pathlib import Path

import pytest

from magentic_ui.sandbox._null import NullSandbox


class TestNullSandboxGuestToolsDir:
    def test_points_at_host_source_dir_with_magui_tools(self, tmp_path: Path) -> None:
        sb = NullSandbox(workspace=tmp_path)
        tools_dir = Path(sb.guest_tools_dir)

        # Must be an absolute, existing directory on the host.
        assert tools_dir.is_absolute()
        assert tools_dir.is_dir(), f"NullSandbox.guest_tools_dir not a dir: {tools_dir}"

        # Must contain both pieces _registry.py invokes:
        # 1. magui_tools/ package (loaded via PYTHONPATH=...)
        # 2. scripts/search.sh (sourced for search_dir/search_file/find_file)
        assert (tools_dir / "magui_tools" / "__init__.py").is_file()
        assert (tools_dir / "scripts" / "search.sh").is_file()


class TestQuicksandSandboxGuestToolsDir:
    def test_matches_in_vm_mount_point(self) -> None:
        # The quicksand third-party package is only installed via the
        # `setup-sandbox` poe task, not by `uv sync` — skip when absent
        # (e.g. CI's python-test job).
        pytest.importorskip("quicksand")
        from magentic_ui.sandbox._quicksand import QuicksandSandbox

        sb = QuicksandSandbox()
        # QuicksandSandbox advertises the in-VM mount path; the actual
        # mount happens in __aenter__ which we don't run here.
        assert sb.guest_tools_dir == "/usr/local/lib/magui"
