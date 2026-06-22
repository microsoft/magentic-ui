"""Integration tests for guest tools (magui_tools) via sandbox.

Tests guest read/edit/insert tools running inside:
- NullSandbox (fast, identity paths, runs on host)
- QuicksandSandbox (real VM, verifies mount + guest path translation)

Also tests tool output truncation with correct guest paths.
"""

from __future__ import annotations

import json
import os
import shlex
from pathlib import Path
from typing import Any

import pytest
import pytest_asyncio

from magentic_ui.sandbox import Mount
from magentic_ui.sandbox._null import NullSandbox

# Guest tools mount point — must match _quicksand.py
_GUEST_TOOLS_MOUNT = "/usr/local/lib/magui"

# Host-side path to guest tools
_GUEST_TOOLS_DIR = (
    Path(__file__).resolve().parents[3]
    / "src"
    / "magentic_ui"
    / "teams"
    / "omniagent"
    / "tools"
    / "guest"
)


def _make_guest_cmd(module: str, args: dict[str, Any], tools_path: str) -> str:
    """Build the sandbox command to call a guest tool module."""
    encoded = shlex.quote(json.dumps(args))
    return (
        f"PYTHONPATH={tools_path}:$PYTHONPATH python3 -m magui_tools.{module} {encoded}"
    )


# ---------------------------------------------------------------------------
# NullSandbox tests (fast — no VM needed)
# ---------------------------------------------------------------------------


class TestGuestToolsNullSandbox:
    """Test guest tools via NullSandbox (host execution, identity paths)."""

    @pytest_asyncio.fixture()
    async def sandbox(self, tmp_path: Path):
        # Uses the shared session venv (see tests/agents/omni/conftest.py).
        sb = NullSandbox(workspace=tmp_path, bash_only=True)
        await sb.__aenter__()
        sb._mounts.append(Mount(_GUEST_TOOLS_DIR.resolve(), _GUEST_TOOLS_DIR.resolve()))
        yield sb
        await sb.__aexit__(None, None, None)

    @pytest.mark.asyncio
    async def test_read_text_file(self, sandbox: NullSandbox, tmp_path: Path) -> None:
        """read.py returns content and total_lines for a text file."""
        f = tmp_path / "test.py"
        f.write_text("import sys\nimport os\nprint('hello')\n")

        result = await sandbox.execute(
            _make_guest_cmd("read", {"file_path": str(f)}, str(_GUEST_TOOLS_DIR)),
            cwd=tmp_path,
        )

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["total_lines"] == 3
        assert "import sys" in data["content"]

    @pytest.mark.asyncio
    async def test_read_nonexistent_file(
        self, sandbox: NullSandbox, tmp_path: Path
    ) -> None:
        """read.py returns error for missing file."""
        result = await sandbox.execute(
            _make_guest_cmd(
                "read", {"file_path": "/tmp/does_not_exist.py"}, str(_GUEST_TOOLS_DIR)
            ),
            cwd=tmp_path,
        )

        assert result.exit_code != 0
        data = json.loads(result.stdout)
        assert "error" in data

    @pytest.mark.asyncio
    async def test_read_directory(self, sandbox: NullSandbox, tmp_path: Path) -> None:
        """read.py returns error for directories."""
        result = await sandbox.execute(
            _make_guest_cmd(
                "read", {"file_path": str(tmp_path)}, str(_GUEST_TOOLS_DIR)
            ),
            cwd=tmp_path,
        )

        assert result.exit_code != 0
        data = json.loads(result.stdout)
        assert "error" in data
        assert "directory" in data["error"].lower()

    @pytest.mark.asyncio
    async def test_read_empty_file(self, sandbox: NullSandbox, tmp_path: Path) -> None:
        """read.py handles empty files."""
        f = tmp_path / "empty.py"
        f.write_text("")

        result = await sandbox.execute(
            _make_guest_cmd("read", {"file_path": str(f)}, str(_GUEST_TOOLS_DIR)),
            cwd=tmp_path,
        )

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["total_lines"] == 0
        assert data["content"] == ""

    @pytest.mark.asyncio
    async def test_read_large_file(self, sandbox: NullSandbox, tmp_path: Path) -> None:
        """read.py handles large files."""
        f = tmp_path / "large.py"
        f.write_text("\n".join(f"line {i}" for i in range(1, 5001)) + "\n")

        result = await sandbox.execute(
            _make_guest_cmd("read", {"file_path": str(f)}, str(_GUEST_TOOLS_DIR)),
            cwd=tmp_path,
        )

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["total_lines"] == 5000

    @pytest.mark.asyncio
    async def test_read_json_file(self, sandbox: NullSandbox, tmp_path: Path) -> None:
        """read.py handles JSON files (application/json mime type)."""
        f = tmp_path / "data.json"
        f.write_text('{"key": "value"}\n')

        result = await sandbox.execute(
            _make_guest_cmd("read", {"file_path": str(f)}, str(_GUEST_TOOLS_DIR)),
            cwd=tmp_path,
        )

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert '"key"' in data["content"]

    @pytest.mark.asyncio
    async def test_edit_file(self, sandbox: NullSandbox, tmp_path: Path) -> None:
        """edit.py replaces lines correctly."""
        f = tmp_path / "test.txt"
        f.write_text("line1\nline2\nline3\nline4\n")

        result = await sandbox.execute(
            _make_guest_cmd(
                "edit",
                {
                    "file_path": str(f),
                    "start_line": 2,
                    "end_line": 3,
                    "content": "new2\nnew3\nnew_extra\n",
                },
                str(_GUEST_TOOLS_DIR),
            ),
            cwd=tmp_path,
        )

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["ok"] is True

        # Verify file content
        content = f.read_text()
        assert content == "line1\nnew2\nnew3\nnew_extra\nline4\n"

    @pytest.mark.asyncio
    async def test_edit_nonexistent_file(
        self, sandbox: NullSandbox, tmp_path: Path
    ) -> None:
        """edit.py returns error for missing file."""
        result = await sandbox.execute(
            _make_guest_cmd(
                "edit",
                {
                    "file_path": "/tmp/nope.py",
                    "start_line": 1,
                    "end_line": 1,
                    "content": "x",
                },
                str(_GUEST_TOOLS_DIR),
            ),
            cwd=tmp_path,
        )

        assert result.exit_code != 0
        data = json.loads(result.stdout)
        assert "error" in data

    @pytest.mark.asyncio
    async def test_insert_file(self, sandbox: NullSandbox, tmp_path: Path) -> None:
        """insert.py inserts lines after specified line."""
        f = tmp_path / "test.txt"
        f.write_text("line1\nline2\nline3\n")

        result = await sandbox.execute(
            _make_guest_cmd(
                "insert",
                {
                    "file_path": str(f),
                    "line": 1,
                    "content": "inserted_a\ninserted_b",
                },
                str(_GUEST_TOOLS_DIR),
            ),
            cwd=tmp_path,
        )

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["ok"] is True

        content = f.read_text()
        assert content == "line1\ninserted_a\ninserted_b\nline2\nline3\n"

    @pytest.mark.asyncio
    async def test_insert_at_beginning(
        self, sandbox: NullSandbox, tmp_path: Path
    ) -> None:
        """insert.py with line=0 inserts at beginning."""
        f = tmp_path / "test.txt"
        f.write_text("line1\nline2\n")

        result = await sandbox.execute(
            _make_guest_cmd(
                "insert",
                {
                    "file_path": str(f),
                    "line": 0,
                    "content": "header",
                },
                str(_GUEST_TOOLS_DIR),
            ),
            cwd=tmp_path,
        )

        assert result.exit_code == 0
        content = f.read_text()
        assert content == "header\nline1\nline2\n"

    @pytest.mark.asyncio
    async def test_edit_special_characters(
        self, sandbox: NullSandbox, tmp_path: Path
    ) -> None:
        """edit.py handles content with quotes, backslashes, special chars."""
        f = tmp_path / "test.py"
        f.write_text("old\n")

        special = 'print("hello \'world\'")\npath = "C:\\\\Users\\\\test"\n'
        result = await sandbox.execute(
            _make_guest_cmd(
                "edit",
                {
                    "file_path": str(f),
                    "start_line": 1,
                    "end_line": 1,
                    "content": special,
                },
                str(_GUEST_TOOLS_DIR),
            ),
            cwd=tmp_path,
        )

        assert result.exit_code == 0
        content = f.read_text()
        assert "print(\"hello 'world'\")" in content

    @pytest.mark.asyncio
    async def test_insert_nonexistent_file(
        self, sandbox: NullSandbox, tmp_path: Path
    ) -> None:
        """insert.py returns error for missing file."""
        result = await sandbox.execute(
            _make_guest_cmd(
                "insert",
                {"file_path": "/tmp/nope_xyz.py", "line": 0, "content": "x"},
                str(_GUEST_TOOLS_DIR),
            ),
            cwd=tmp_path,
        )

        assert result.exit_code != 0
        assert "error" in json.loads(result.stdout)

    @pytest.mark.asyncio
    async def test_read_csv_file(self, sandbox: NullSandbox, tmp_path: Path) -> None:
        """read.py handles CSV files."""
        f = tmp_path / "data.csv"
        f.write_text("name,age\nalice,30\nbob,25\n")

        result = await sandbox.execute(
            _make_guest_cmd("read", {"file_path": str(f)}, str(_GUEST_TOOLS_DIR)),
            cwd=tmp_path,
        )

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["total_lines"] == 3
        assert "alice" in data["content"]

    @pytest.mark.asyncio
    async def test_read_image_rejected(
        self, sandbox: NullSandbox, tmp_path: Path
    ) -> None:
        """read.py rejects image files."""
        f = tmp_path / "photo.png"
        # Write a minimal PNG header so file(1) detects it as image
        f.write_bytes(
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
            b"\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02"
            b"\x00\x00\x00\x90wS\xde\x00\x00\x00\x00IEND\xaeB`\x82"
        )

        result = await sandbox.execute(
            _make_guest_cmd("read", {"file_path": str(f)}, str(_GUEST_TOOLS_DIR)),
            cwd=tmp_path,
        )

        assert result.exit_code != 0
        data = json.loads(result.stdout)
        assert "image" in data["error"].lower()

    @pytest.mark.asyncio
    async def test_read_markdown_file(
        self, sandbox: NullSandbox, tmp_path: Path
    ) -> None:
        """read.py handles markdown files."""
        f = tmp_path / "readme.md"
        f.write_text("# Title\n\nSome content.\n")

        result = await sandbox.execute(
            _make_guest_cmd("read", {"file_path": str(f)}, str(_GUEST_TOOLS_DIR)),
            cwd=tmp_path,
        )

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert "Title" in data["content"]

    @pytest.mark.asyncio
    async def test_read_python_file_with_unicode(
        self, sandbox: NullSandbox, tmp_path: Path
    ) -> None:
        """read.py handles Python files with unicode."""
        f = tmp_path / "unicode.py"
        f.write_text('msg = "héllo wörld"\nprint(msg)\n', encoding="utf-8")

        result = await sandbox.execute(
            _make_guest_cmd("read", {"file_path": str(f)}, str(_GUEST_TOOLS_DIR)),
            cwd=tmp_path,
        )

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert "héllo" in data["content"]


# ---------------------------------------------------------------------------
# Truncation tests — format_tool_output spill-to-disk
# ---------------------------------------------------------------------------


class TestToolOutputTruncation:
    """Test format_tool_output from _harness/_format.py."""

    def test_under_budget_passes_through(self, tmp_path: Path) -> None:
        """Output under budget is returned as-is."""
        from magentic_ui.teams.omniagent._harness._format import format_tool_output

        result = format_tool_output(
            data={"output": "small output"},
            truncatable_fields=["output"],
            budget=1000,
            outputs_dir=tmp_path,
        )
        assert result == "small output"

    def test_over_budget_spills_to_disk(self, tmp_path: Path) -> None:
        """Output over budget gets head/tail split + file on disk."""
        from magentic_ui.teams.omniagent._harness._format import format_tool_output

        big_output = "\n".join(f"line {i}" for i in range(1, 501))

        result = format_tool_output(
            data={"output": big_output},
            truncatable_fields=["output"],
            budget=500,
            outputs_dir=tmp_path,
        )

        assert "output.head" in result
        assert "output.tail" in result
        assert "output.file" in result
        assert "truncated" in result.lower() or "remarks" in result.lower()

        # Verify spill file exists
        spill_files = list(tmp_path.glob("output_*"))
        assert len(spill_files) == 1
        assert spill_files[0].read_text() == big_output

    def test_guest_path_in_spill_reference(self, tmp_path: Path) -> None:
        """Spill file path uses guest path translation."""
        from magentic_ui.teams.omniagent._harness._format import format_tool_output

        big_output = "\n".join(f"line {i}" for i in range(1, 501))

        def mock_guest_path(host_path: Path) -> Path:
            return Path("/workspace/.agent/tool_outputs") / host_path.name

        result = format_tool_output(
            data={"output": big_output},
            truncatable_fields=["output"],
            budget=500,
            outputs_dir=tmp_path,
            to_guest_path=mock_guest_path,
        )

        assert "/workspace/.agent/tool_outputs/" in result

    def test_non_truncatable_field_untouched(self, tmp_path: Path) -> None:
        """Fields not in truncatable_fields are never truncated."""
        from magentic_ui.teams.omniagent._harness._format import format_tool_output

        result = format_tool_output(
            data={"exit_code": "0", "output": "small"},
            truncatable_fields=["output"],
            budget=10000,
            outputs_dir=tmp_path,
        )
        assert "exit_code: 0" in result
        assert "small" in result


# ---------------------------------------------------------------------------
# Quicksand tests (real VM — verifies mount + guest path translation)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    not _GUEST_TOOLS_DIR.exists(),
    reason="Guest tools directory not found",
)
@pytest.mark.skipif(
    os.environ.get("CI") == "true",
    reason="real-VM integration test — needs local KVM + image; no nested virtualization in CI",
)
class TestGuestToolsQuicksand:
    """Test guest tools via Quicksand (real VM with mount)."""

    @pytest_asyncio.fixture()
    async def sandbox_and_workspace(self, tmp_path: Path):
        """Spin up a fresh Quicksand VM with network, guest tools, and workspace."""
        quicksand = pytest.importorskip("quicksand")
        from quicksand_core import NetworkMode

        sb = await quicksand.Sandbox(
            image="quicksand-cua",
            memory="2G",
            cpus=1,
            network_mode=NetworkMode.FULL,
        ).__aenter__()

        # Mount guest tools
        await sb.mount(
            host=str(_GUEST_TOOLS_DIR.resolve()),
            guest=_GUEST_TOOLS_MOUNT,
            readonly=True,
        )

        # Mount workspace
        guest_workspace = "/workspace"
        await sb.mount(
            host=str(tmp_path),
            guest=guest_workspace,
            readonly=False,
        )

        yield sb, tmp_path, guest_workspace

        await sb.__aexit__(None, None, None)

    @pytest.mark.asyncio
    async def test_guest_tools_mounted(self, sandbox_and_workspace) -> None:
        """Verify guest tools are accessible at mount point."""
        sb, _, _ = sandbox_and_workspace
        result = await sb.execute(f"ls {_GUEST_TOOLS_MOUNT}/magui_tools/")
        assert "read.py" in result.stdout
        assert "edit.py" in result.stdout
        assert "insert.py" in result.stdout

    @pytest.mark.asyncio
    async def test_read_in_sandbox(self, sandbox_and_workspace) -> None:
        """read.py works inside the VM via mounted tools."""
        sb, tmp_path, guest_ws = sandbox_and_workspace

        # Create file on host (visible in sandbox via mount)
        f = tmp_path / "hello.py"
        f.write_text("import sys\nprint('hello')\n")

        args = json.dumps({"file_path": f"{guest_ws}/hello.py"})
        result = await sb.execute(
            f"PYTHONPATH={_GUEST_TOOLS_MOUNT}:$PYTHONPATH python3 -m magui_tools.read {shlex.quote(args)}",
            cwd=guest_ws,
        )

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["total_lines"] == 2
        assert "import sys" in data["content"]

    @pytest.mark.asyncio
    async def test_edit_in_sandbox(self, sandbox_and_workspace) -> None:
        """edit.py modifies files inside the VM."""
        sb, tmp_path, guest_ws = sandbox_and_workspace

        f = tmp_path / "test.py"
        f.write_text("x = 1\ny = 2\nz = 3\n")

        args = json.dumps(
            {
                "file_path": f"{guest_ws}/test.py",
                "start_line": 2,
                "end_line": 2,
                "content": "y = 42",
            }
        )
        result = await sb.execute(
            f"PYTHONPATH={_GUEST_TOOLS_MOUNT}:$PYTHONPATH python3 -m magui_tools.edit {shlex.quote(args)}",
            cwd=guest_ws,
        )

        assert result.exit_code == 0
        # Verify on host side (bidirectional mount)
        assert f.read_text() == "x = 1\ny = 42\nz = 3\n"

    @pytest.mark.asyncio
    async def test_insert_in_sandbox(self, sandbox_and_workspace) -> None:
        """insert.py inserts lines inside the VM."""
        sb, tmp_path, guest_ws = sandbox_and_workspace

        f = tmp_path / "test.py"
        f.write_text("x = 1\ny = 2\n")

        args = json.dumps(
            {
                "file_path": f"{guest_ws}/test.py",
                "line": 1,
                "content": "w = 99",
            }
        )
        result = await sb.execute(
            f"PYTHONPATH={_GUEST_TOOLS_MOUNT}:$PYTHONPATH python3 -m magui_tools.insert {shlex.quote(args)}",
            cwd=guest_ws,
        )

        assert result.exit_code == 0
        assert f.read_text() == "x = 1\nw = 99\ny = 2\n"

    @pytest.mark.asyncio
    async def test_read_tmp_file_in_sandbox(self, sandbox_and_workspace) -> None:
        """read.py can access /tmp inside the VM (not on host mount)."""
        sb, _, guest_ws = sandbox_and_workspace

        # Create a file in /tmp inside the VM
        await sb.execute("echo 'temp content' > /tmp/sandbox_test.txt")

        args = json.dumps({"file_path": "/tmp/sandbox_test.txt"})
        result = await sb.execute(
            f"PYTHONPATH={_GUEST_TOOLS_MOUNT}:$PYTHONPATH python3 -m magui_tools.read {shlex.quote(args)}",
            cwd=guest_ws,
        )

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert "temp content" in data["content"]

    @pytest.mark.asyncio
    async def test_guest_path_translation(self, sandbox_and_workspace) -> None:
        """Verify file paths inside sandbox use guest paths, not host paths."""
        sb, tmp_path, guest_ws = sandbox_and_workspace

        f = tmp_path / "pathtest.py"
        f.write_text("hello\n")

        # The guest should see the file at /workspace/pathtest.py, not at tmp_path
        args = json.dumps({"file_path": f"{guest_ws}/pathtest.py"})
        result = await sb.execute(
            f"PYTHONPATH={_GUEST_TOOLS_MOUNT}:$PYTHONPATH python3 -m magui_tools.read {shlex.quote(args)}",
            cwd=guest_ws,
        )

        assert result.exit_code == 0

        # Using the host path should NOT work inside the sandbox
        args_host = json.dumps({"file_path": str(f)})
        result_host = await sb.execute(
            f"PYTHONPATH={_GUEST_TOOLS_MOUNT}:$PYTHONPATH python3 -m magui_tools.read {shlex.quote(args_host)}",
            cwd=guest_ws,
        )

        assert result_host.exit_code != 0

    @pytest.mark.asyncio
    async def test_spill_to_disk_readable_in_sandbox(
        self, sandbox_and_workspace
    ) -> None:
        """End-to-end: large output spills to disk, model can read it in sandbox."""
        from magentic_ui.teams.omniagent._harness._format import format_tool_output

        sb, tmp_path, guest_ws = sandbox_and_workspace

        # Set up outputs dir on host (inside workspace so it's mounted)
        outputs_dir = tmp_path / ".agent" / "tool_outputs"
        outputs_dir.mkdir(parents=True)

        # Build guest path translator using the mount
        def to_guest_path(host_path: Path) -> Path:
            rel = host_path.relative_to(tmp_path)
            return Path(guest_ws) / rel

        # Generate large output that exceeds budget
        big_output = "\n".join(f"line {i}: {'x' * 80}" for i in range(1, 301))

        # Truncate — writes spill file to host, returns text with guest path
        truncated = format_tool_output(
            data={"output": big_output},
            truncatable_fields=["output"],
            budget=2000,
            outputs_dir=outputs_dir,
            to_guest_path=to_guest_path,
        )

        # Verify truncated output has head, tail, file reference, and remarks
        assert "output.head" in truncated
        assert "output.tail" in truncated
        assert "output.file" in truncated
        assert "remarks" in truncated

        # Head should contain the beginning of the output
        assert "line 1:" in truncated
        # Tail should contain the end of the output
        assert "line 300:" in truncated

        # Extract guest path from truncated output
        guest_file_path = ""
        for line in truncated.splitlines():
            if line.startswith("output.file:"):
                guest_file_path = line.split(":", 1)[1].strip()
                break
        assert guest_file_path.startswith(guest_ws)

        # Verify spill file exists on host
        spill_files = list(outputs_dir.glob("output_*"))
        assert len(spill_files) == 1
        # Host file content matches original
        assert spill_files[0].read_text().rstrip() == big_output.rstrip()

        # Verify model can read the spill file inside the sandbox via guest path
        result = await sb.execute(f"cat '{guest_file_path}'", cwd=guest_ws)
        assert result.exit_code == 0
        assert result.stdout.rstrip() == big_output.rstrip()

    @pytest.mark.asyncio
    async def test_edit_lint_rejects_bad_python(self, sandbox_and_workspace) -> None:
        """Edit introducing undefined name is rejected by flake8 inside VM."""
        sb, tmp_path, guest_ws = sandbox_and_workspace

        # Create valid Python file
        f = tmp_path / "test.py"
        f.write_text("x = 1\ny = 2\nz = 3\n")

        # Edit line 2 with undefined name
        args = json.dumps(
            {
                "file_path": f"{guest_ws}/test.py",
                "start_line": 2,
                "end_line": 2,
                "content": "y = undefined_xyz",
            }
        )
        result = await sb.execute(
            f"PYTHONPATH={_GUEST_TOOLS_MOUNT}:$PYTHONPATH python3 -m magui_tools.edit {shlex.quote(args)}",
            cwd=guest_ws,
        )

        assert result.exit_code == 1
        data = json.loads(result.stdout)
        assert "lint_errors" in data
        assert "F821" in data["lint_errors"]
        assert "undefined_xyz" in data["lint_errors"]

        # File should be reverted
        assert f.read_text() == "x = 1\ny = 2\nz = 3\n"

    @pytest.mark.asyncio
    async def test_insert_lint_rejects_bad_python(self, sandbox_and_workspace) -> None:
        """Insert introducing undefined name is rejected by flake8 inside VM."""
        sb, tmp_path, guest_ws = sandbox_and_workspace

        f = tmp_path / "test.py"
        f.write_text("x = 1\ny = 2\n")

        args = json.dumps(
            {
                "file_path": f"{guest_ws}/test.py",
                "line": 1,
                "content": "w = undefined_abc",
            }
        )
        result = await sb.execute(
            f"PYTHONPATH={_GUEST_TOOLS_MOUNT}:$PYTHONPATH python3 -m magui_tools.insert {shlex.quote(args)}",
            cwd=guest_ws,
        )

        assert result.exit_code == 1
        data = json.loads(result.stdout)
        assert "lint_errors" in data
        assert "F821" in data["lint_errors"]

        # File should be reverted
        assert f.read_text() == "x = 1\ny = 2\n"

    @pytest.mark.asyncio
    async def test_edit_lint_accepts_good_python(self, sandbox_and_workspace) -> None:
        """Valid Python edit passes flake8 linting inside VM."""
        sb, tmp_path, guest_ws = sandbox_and_workspace

        f = tmp_path / "test.py"
        f.write_text("x = 1\ny = 2\nz = 3\n")

        args = json.dumps(
            {
                "file_path": f"{guest_ws}/test.py",
                "start_line": 2,
                "end_line": 2,
                "content": "y = 42",
            }
        )
        result = await sb.execute(
            f"PYTHONPATH={_GUEST_TOOLS_MOUNT}:$PYTHONPATH python3 -m magui_tools.edit {shlex.quote(args)}",
            cwd=guest_ws,
        )

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["ok"] is True
        assert f.read_text() == "x = 1\ny = 42\nz = 3\n"

    # ------------------------------------------------------------------
    # Search tests (search.sh sourced as bash functions inside VM)
    # ------------------------------------------------------------------

    def _search_cmd(self, script: str) -> str:
        """Build command to source search.sh and run a search function."""
        return f'bash -c ". {_GUEST_TOOLS_MOUNT}/scripts/search.sh && {script}"'

    @pytest.mark.asyncio
    async def test_search_dir_in_sandbox(self, sandbox_and_workspace) -> None:
        """search_dir finds matches across files inside VM."""
        sb, tmp_path, guest_ws = sandbox_and_workspace

        (tmp_path / "a.py").write_text("hello world\nfoo bar\nhello again\n")
        (tmp_path / "b.py").write_text("hello once\n")

        result = await sb.execute(
            self._search_cmd(f"search_dir 'hello' '{guest_ws}'"),
            cwd=guest_ws,
        )

        assert result.exit_code == 0
        assert "Found" in result.stdout
        assert "hello" in result.stdout
        assert "End of matches" in result.stdout

    @pytest.mark.asyncio
    async def test_search_dir_no_matches_in_sandbox(
        self, sandbox_and_workspace
    ) -> None:
        """search_dir reports no matches inside VM."""
        sb, tmp_path, guest_ws = sandbox_and_workspace

        (tmp_path / "a.py").write_text("hello world\n")

        result = await sb.execute(
            self._search_cmd(f"search_dir 'zzzznotfound' '{guest_ws}'"),
            cwd=guest_ws,
        )

        assert "No matches found" in result.stdout

    @pytest.mark.asyncio
    async def test_search_file_in_sandbox(self, sandbox_and_workspace) -> None:
        """search_file finds matches within a file inside VM."""
        sb, tmp_path, guest_ws = sandbox_and_workspace

        (tmp_path / "test.py").write_text("alpha\nbeta\nalpha again\ngamma\n")

        result = await sb.execute(
            self._search_cmd(f"search_file 'alpha' '{guest_ws}/test.py'"),
            cwd=guest_ws,
        )

        assert result.exit_code == 0
        assert "Found" in result.stdout
        assert "Line 1:" in result.stdout
        assert "Line 3:" in result.stdout
        assert "End of matches" in result.stdout

    @pytest.mark.asyncio
    async def test_find_file_in_sandbox(self, sandbox_and_workspace) -> None:
        """find_file locates files by name inside VM."""
        sb, tmp_path, guest_ws = sandbox_and_workspace

        (tmp_path / "foo.py").write_text("x\n")
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "foo.py").write_text("y\n")

        result = await sb.execute(
            self._search_cmd(f"find_file 'foo.py' '{guest_ws}'"),
            cwd=guest_ws,
        )

        assert result.exit_code == 0
        assert "Found" in result.stdout
        assert "foo.py" in result.stdout
