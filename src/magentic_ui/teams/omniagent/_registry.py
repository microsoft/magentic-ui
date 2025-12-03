"""Tool registry for OmniAgent.

Each tool has a definition (JSON schema for the system prompt) and an async
execute function.  Guest tools are called via ``_call_guest()``; host-only
tools call ``sandbox.execute()`` directly.

The execute function signature is::

    async def execute(agent: OmniAgent, **kwargs) -> ToolOutput

where ``ToolOutput`` has a ``to_output(state)`` method that formats for the LLM.
"""

from __future__ import annotations

import json
import logging
import shlex
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Awaitable, Callable

from ._command_policy import (
    ApprovalCheck,
    classify_bash_command,
    classify_file_tool,
    classify_sensitive_read,
)
from ._bash_observers import enrich
from ._shell_quoting import shell_quote_path
from .tools.host import (
    BashOutput,
    CreateOutput,
    EditOutput,
    FindFileOutput,
    InsertOutput,
    OpenOutput,
    ScrollOutput,
    SearchDirOutput,
    SearchFileOutput,
    ToolOutput,
    compute_open_line,
    compute_scroll_down,
    compute_scroll_up,
    constrain_line,
)

if TYPE_CHECKING:
    from ._omni_agent import OmniAgent

_log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Tool dataclass
# ---------------------------------------------------------------------------


@dataclass
class Tool:
    """A registered tool available to the agent."""

    name: str
    definition: dict[str, Any]  # JSON schema shown in system prompt
    execute: Callable[..., Awaitable[ToolOutput]] | None = None
    breaks_loop: bool = False
    requires_approval: bool = False
    # Optional callable for fine-grained approval. Unified signature:
    # ``(tool_name, tool_args, is_sandbox) -> ClassificationResult``.
    # When set and policy is ``require_approval_untrusted``, this is called
    # instead of using the boolean ``requires_approval``.
    approval_check: ApprovalCheck | None = None


# ---------------------------------------------------------------------------
# Guest module helper
# ---------------------------------------------------------------------------


def _extract_json(stdout: str) -> str:
    """Return the last JSON-like line from stdout."""
    for line in reversed(stdout.splitlines()):
        line = line.strip()
        if line.startswith("{") or line.startswith("["):
            return line
    return stdout


async def _call_guest(
    agent: OmniAgent, module: str, args: dict[str, Any]
) -> dict[str, Any]:
    """Call a guest-side magui_tools module and return parsed JSON."""
    if agent.sandbox is None:
        return {"error": "Sandbox is not available"}
    encoded = shlex.quote(json.dumps(args))
    tools_dir = shlex.quote(agent.sandbox.guest_tools_dir)
    result = await agent.sandbox.execute(
        f"PYTHONPATH={tools_dir}:$PYTHONPATH python3 -m magui_tools.{module} {encoded}",
        cwd=agent.guest_workspace,
    )
    if result.exit_code != 0:
        try:
            return json.loads(_extract_json(result.stdout))
        except json.JSONDecodeError:
            return {"error": result.stderr or result.stdout or "Unknown error"}
    try:
        return json.loads(_extract_json(result.stdout))
    except json.JSONDecodeError as e:
        _log.error(
            "Failed to parse %s output: %s\nOutput: %r", module, e, result.stdout
        )
        return {"error": f"Invalid output from {module}"}


async def _read_file(agent: OmniAgent, file_path: str) -> dict[str, Any]:
    """Read a file via guest read module."""
    return await _call_guest(agent, "read", {"file_path": file_path})


# Per-file character cap when injecting workspace files into Fara via the
# delegate_cua tool's ``files`` param. Budgeting uses ``len()`` on Python
# ``str`` (Unicode code points), not encoded byte counts. Beyond this we
# head-truncate with a marker so the model can tell something was cut.
_DELEGATE_CUA_FILE_PREVIEW_CHARS = 8_000

# Total character cap across all files in a single delegate_cua call.
# Roughly 4K tokens at Fara's tokenizer — meaningful but bounded.
_DELEGATE_CUA_FILES_TOTAL_CHARS = 16_000

_DELEGATE_CUA_TOTAL_EXHAUSTED_MARKER = "\n[...total file budget exhausted]"


async def build_delegate_cua_task(
    agent: OmniAgent,
    *,
    task: str,
    context: str,
    file_paths: list[str],
) -> str:
    """Combine delegate_cua args into a single task string for Fara.

    Fara has no file tools, so the harness reads each path via the same
    guest ``read`` module that powers OmniAgent's ``open`` tool, then
    inlines the extracted text into Fara's task input.

    Per-file content is head-truncated at
    ``_DELEGATE_CUA_FILE_PREVIEW_CHARS``; total file content across the
    call is capped at ``_DELEGATE_CUA_FILES_TOTAL_CHARS`` to keep Fara's
    context bounded.
    """
    sections = [task]
    if context.strip():
        sections.append(f"\nBackground:\n{context.strip()}")

    remaining = _DELEGATE_CUA_FILES_TOTAL_CHARS
    for path in file_paths:
        data = await _read_file(agent, path)
        if "error" in data:
            sections.append(f"\n[File {path}: {data['error']}]")
            continue
        body: str = data["content"]
        if len(body) > _DELEGATE_CUA_FILE_PREVIEW_CHARS:
            body = (
                body[:_DELEGATE_CUA_FILE_PREVIEW_CHARS]
                + f"\n[...truncated; {len(data['content'])} total chars in {path}]"
            )
        if len(body) > remaining:
            marker_len = len(_DELEGATE_CUA_TOTAL_EXHAUSTED_MARKER)
            if remaining <= marker_len:
                sections.append(_DELEGATE_CUA_TOTAL_EXHAUSTED_MARKER)
                break
            body = body[: remaining - marker_len] + _DELEGATE_CUA_TOTAL_EXHAUSTED_MARKER
        remaining -= len(body)
        sections.append(f"\nFile {path} (extracted to text):\n{body}")
        if remaining <= 0:
            break

    return "\n".join(sections)


# ---------------------------------------------------------------------------
# Execute functions
# ---------------------------------------------------------------------------


async def _exec_open(
    agent: OmniAgent, path: str = "", line_number: int | None = None, **_: Any
) -> OpenOutput:
    data = await _read_file(agent, path)
    if "error" in data:
        return OpenOutput(content="", total_lines=0, error=data["error"])

    file_content: str = data["content"]
    file_total: int = data["total_lines"]

    # Set current_file, compute current_line, constrain.
    agent.viewport.current_file = path
    agent.viewport.current_line = compute_open_line(agent.viewport, line_number)
    constrain_line(agent.viewport, file_total)

    return OpenOutput(content=file_content, total_lines=file_total)


async def _exec_edit(
    agent: OmniAgent,
    start_line: int = 0,
    end_line: int = 0,
    content: str = "",
    **_: Any,
) -> EditOutput:
    if agent.viewport.current_file is None:
        return EditOutput(
            content="",
            total_lines=0,
            error="No file open. Use the open command first.",
        )

    data = await _call_guest(
        agent,
        "edit",
        {
            "file_path": agent.viewport.current_file,
            "start_line": start_line,
            "end_line": end_line,
            "content": content,
        },
    )
    if "error" in data:
        if "lint_errors" in data:
            return EditOutput(
                content="",
                total_lines=0,
                error=data["error"],
                lint_errors=data["lint_errors"],
                edited_content=data.get("edited_content"),
                original_content=data.get("original_content"),
                start_line=data.get("start_line", start_line),
                end_line=data.get("end_line", end_line),
                line_count=data.get("line_count", 0),
            )
        return EditOutput(content="", total_lines=0, error=data["error"])

    # Re-read file for viewport
    read_data = await _read_file(agent, agent.viewport.current_file)
    if "error" in read_data:
        return EditOutput(content="", total_lines=0, error=read_data["error"])

    # current_line = start_line - 1 (0-based), then constrain.
    agent.viewport.current_line = start_line - 1
    file_content: str = read_data["content"]
    file_total: int = read_data["total_lines"]
    constrain_line(agent.viewport, file_total)

    return EditOutput(content=file_content, total_lines=file_total)


async def _exec_insert(
    agent: OmniAgent, line: int = 0, content: str = "", **_: Any
) -> InsertOutput:
    if agent.viewport.current_file is None:
        return InsertOutput(
            content="",
            total_lines=0,
            error="No file open. Use the open command first.",
        )

    data = await _call_guest(
        agent,
        "insert",
        {
            "file_path": agent.viewport.current_file,
            "line": line,
            "content": content,
        },
    )
    if "error" in data:
        if "lint_errors" in data:
            return InsertOutput(
                content="",
                total_lines=0,
                error=data["error"],
                lint_errors=data["lint_errors"],
                edited_content=data.get("edited_content"),
                original_content=data.get("original_content"),
                insert_after=data.get("insert_after", line),
                line_count=data.get("line_count", 0),
            )
        return InsertOutput(content="", total_lines=0, error=data["error"])

    # Re-read file for viewport
    read_data = await _read_file(agent, agent.viewport.current_file)
    if "error" in read_data:
        return InsertOutput(content="", total_lines=0, error=read_data["error"])

    # current_line = insert_after + 1, then constrain.
    agent.viewport.current_line = line + 1
    file_content: str = read_data["content"]
    file_total: int = read_data["total_lines"]
    constrain_line(agent.viewport, file_total)

    return InsertOutput(content=file_content, total_lines=file_total)


async def _exec_goto(agent: OmniAgent, line_number: int = 0, **_: Any) -> ScrollOutput:
    if agent.viewport.current_file is None:
        return ScrollOutput(
            content="",
            total_lines=0,
            error="No file open. Use the open command first.",
        )

    data = await _read_file(agent, agent.viewport.current_file)
    if "error" in data:
        return ScrollOutput(content="", total_lines=0, error=data["error"])

    # Same formula as open with line_number.
    file_content: str = data["content"]
    file_total: int = data["total_lines"]
    agent.viewport.current_line = compute_open_line(agent.viewport, line_number)
    constrain_line(agent.viewport, file_total)

    return ScrollOutput(content=file_content, total_lines=file_total)


async def _exec_scroll_down(agent: OmniAgent, **_: Any) -> ScrollOutput:
    if agent.viewport.current_file is None:
        return ScrollOutput(
            content="",
            total_lines=0,
            error="No file open. Use the open command first.",
        )

    data = await _read_file(agent, agent.viewport.current_file)
    if "error" in data:
        return ScrollOutput(content="", total_lines=0, error=data["error"])

    file_content: str = data["content"]
    file_total: int = data["total_lines"]
    agent.viewport.current_line = compute_scroll_down(agent.viewport)
    constrain_line(agent.viewport, file_total)

    return ScrollOutput(content=file_content, total_lines=file_total)


async def _exec_scroll_up(agent: OmniAgent, **_: Any) -> ScrollOutput:
    if agent.viewport.current_file is None:
        return ScrollOutput(
            content="",
            total_lines=0,
            error="No file open. Use the open command first.",
        )

    data = await _read_file(agent, agent.viewport.current_file)
    if "error" in data:
        return ScrollOutput(content="", total_lines=0, error=data["error"])

    file_content: str = data["content"]
    file_total: int = data["total_lines"]
    agent.viewport.current_line = compute_scroll_up(agent.viewport)
    constrain_line(agent.viewport, file_total)

    return ScrollOutput(content=file_content, total_lines=file_total)


async def _exec_create(agent: OmniAgent, filename: str = "", **_: Any) -> CreateOutput:
    if agent.sandbox is None:
        return CreateOutput(content="", total_lines=0, error="Sandbox is not available")

    quoted = shell_quote_path(filename)

    # Refuse to overwrite an existing file. The upstream `printf > "$1"` truncates
    # silently, leading the model to misdiagnose later failures ("the previous
    # insert didn't work") and waste turns rewriting from scratch.
    exists_check = await agent.sandbox.execute(
        f"test -e {quoted} && echo EXISTS || true",
        cwd=agent.guest_workspace,
    )
    if exists_check.stdout.strip() == "EXISTS":
        return CreateOutput(
            content="",
            total_lines=0,
            error=(
                f"'{filename}' already exists. Use `open` to view it, "
                "`edit` to replace lines, or `insert` to add lines. "
                "To start over, delete it first with `bash rm`."
            ),
        )

    # printf '\n' > "$1", then open it.
    result = await agent.sandbox.execute(
        f'mkdir -p -- "$(dirname -- {quoted})" ' f"&& printf '\\n' > {quoted}",
        cwd=agent.guest_workspace,
    )
    if result.exit_code != 0:
        return CreateOutput(
            content="",
            total_lines=0,
            error=f"Failed to create '{filename}': {result.stderr or result.stdout}",
        )

    data = await _read_file(agent, filename)
    if "error" in data:
        return CreateOutput(content="", total_lines=0, error=data["error"])

    file_content: str = data["content"]
    file_total: int = data["total_lines"]
    agent.viewport.current_file = filename
    agent.viewport.current_line = compute_open_line(agent.viewport, None)
    constrain_line(agent.viewport, file_total)

    return CreateOutput(content=file_content, total_lines=file_total)


async def _exec_bash(agent: OmniAgent, command: str = "", **_: Any) -> BashOutput:
    if agent.sandbox is None:
        return BashOutput(stdout="", stderr="Sandbox is not available", exit_code=1)
    if not command.strip():
        return BashOutput(stdout="", stderr="bash: empty command", exit_code=1)

    result, annotations = await enrich(
        command=command, cwd=agent.guest_workspace, sandbox=agent.sandbox
    )
    return BashOutput(
        stdout=result.stdout,
        stderr=result.stderr,
        exit_code=result.exit_code,
        annotations=annotations,
    )


def _search_cmd(tools_dir: str, func: str, *args: str) -> str:
    """Build a bash command to source search.sh and call a function."""
    script_path = shlex.quote(f"{tools_dir}/scripts/search.sh")
    quoted_args = " ".join(shlex.quote(a) for a in args)
    inner = f"source {script_path} && {func} {quoted_args}"
    return f"bash -c {shlex.quote(inner)}"


async def _exec_search_dir(
    agent: OmniAgent, term: str = "", directory: str = ".", **_: Any
) -> SearchDirOutput:
    if agent.sandbox is None:
        return SearchDirOutput(
            stdout="", stderr="Sandbox is not available", exit_code=1
        )
    result = await agent.sandbox.execute(
        _search_cmd(agent.sandbox.guest_tools_dir, "search_dir", term, directory),
        cwd=agent.guest_workspace,
    )
    return SearchDirOutput(
        stdout=result.stdout,
        stderr=result.stderr,
        exit_code=result.exit_code,
    )


async def _exec_search_file(
    agent: OmniAgent, term: str = "", file: str | None = None, **_: Any
) -> SearchFileOutput:
    if agent.sandbox is None:
        return SearchFileOutput(
            stdout="", stderr="Sandbox is not available", exit_code=1
        )
    tools_dir = agent.sandbox.guest_tools_dir
    target = file or (agent.viewport.current_file or "")
    if target:
        result = await agent.sandbox.execute(
            _search_cmd(tools_dir, "search_file", term, target),
            cwd=agent.guest_workspace,
        )
    else:
        # No file specified and no file open — let the bash function handle it
        result = await agent.sandbox.execute(
            _search_cmd(tools_dir, "search_file", term),
            cwd=agent.guest_workspace,
        )
    return SearchFileOutput(
        stdout=result.stdout,
        stderr=result.stderr,
        exit_code=result.exit_code,
    )


async def _exec_find_file(
    agent: OmniAgent, name: str = "", directory: str = ".", **_: Any
) -> FindFileOutput:
    if agent.sandbox is None:
        return FindFileOutput(stdout="", stderr="Sandbox is not available", exit_code=1)
    result = await agent.sandbox.execute(
        _search_cmd(agent.sandbox.guest_tools_dir, "find_file", name, directory),
        cwd=agent.guest_workspace,
    )
    return FindFileOutput(
        stdout=result.stdout,
        stderr=result.stderr,
        exit_code=result.exit_code,
    )


# ---------------------------------------------------------------------------
# Tool list
# ---------------------------------------------------------------------------


def _find_def(name: str, defs: list[dict[str, Any]]) -> dict[str, Any]:
    """Find a tool definition by name from prompts.py lists."""
    for d in defs:
        if d.get("function", {}).get("name") == name:
            return d
    raise ValueError(f"Tool definition not found: {name}")


_CORE_DEFS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "bash",
            "description": "Execute a bash command.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "The bash command to execute.",
                    },
                },
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create",
            "description": "Create a new file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {
                        "type": "string",
                        "description": "Path of the file to create.",
                    },
                },
                "required": ["filename"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "open",
            "description": "Open a file in the editor. Supports binary document formats (.docx, .pdf, .xlsx, .pptx) via automatic text extraction.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path of the file to open.",
                    },
                    "line_number": {
                        "type": "integer",
                        "description": "Optional line number to jump to.",
                    },
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "edit",
            "description": "Edit lines in the currently open file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "start_line": {
                        "type": "integer",
                        "description": "First line to replace (1-based).",
                    },
                    "end_line": {
                        "type": "integer",
                        "description": "Last line to replace (inclusive).",
                    },
                    "content": {
                        "type": "string",
                        "description": "Replacement content.",
                    },
                },
                "required": ["start_line", "end_line", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "insert",
            "description": "Insert content after a line in the currently open file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "line": {
                        "type": "integer",
                        "description": "Line number to insert after (0 for beginning).",
                    },
                    "content": {"type": "string", "description": "Content to insert."},
                },
                "required": ["line", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "goto",
            "description": "Go to a specific line in the currently open file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "line_number": {
                        "type": "integer",
                        "description": "Line number to navigate to.",
                    },
                },
                "required": ["line_number"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "scroll_down",
            "description": "Scroll down in the currently open file.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "scroll_up",
            "description": "Scroll up in the currently open file.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_dir",
            "description": "Search for a term in plain-text files within a directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "term": {"type": "string", "description": "Search term."},
                    "directory": {
                        "type": "string",
                        "description": "Directory to search in. Defaults to current directory.",
                    },
                },
                "required": ["term"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_file",
            "description": "Search for a term in a plain-text file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "term": {"type": "string", "description": "Search term."},
                    "file": {
                        "type": "string",
                        "description": "File to search in. Defaults to the currently open file.",
                    },
                },
                "required": ["term"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "find_file",
            "description": "Find files by name.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "File name or pattern to search for.",
                    },
                    "directory": {
                        "type": "string",
                        "description": "Directory to search in. Defaults to current directory.",
                    },
                },
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "request_user_input",
            "description": "Pause and ask the user for input or clarification.",
            "parameters": {
                "type": "object",
                "properties": {
                    "prompt": {
                        "type": "string",
                        "description": "The question or prompt to show the user.",
                    },
                },
                "required": ["prompt"],
            },
        },
    },
]

DELEGATE_CUA_DEF: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "delegate_cua",
        "description": (
            "Delegate a web task to the web agent. The web agent has no file "
            "tools and no memory of your conversation — pass everything it "
            "needs via task/context/files.\n\n"
            "WHEN TO USE:\n"
            "- Looking up information that requires real web browsing "
            "(current prices, news, search results, facts)\n"
            "- Filling out forms with multiple fields or pages\n"
            "- Any task requiring clicking, typing, or navigating across "
            "rendered web pages\n\n"
            "WHEN NOT TO USE:\n"
            "- Pure local file or code work — use bash, open, or edit instead\n"
            "- Hitting a JSON or REST API endpoint that returns raw data "
            "(no HTML to render) — use bash with curl"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "task": {
                    "type": "string",
                    "description": (
                        "The action the web agent should take. Be specific "
                        "and self-contained — the web agent knows nothing "
                        "about your conversation."
                    ),
                },
                "context": {
                    "type": "string",
                    "description": (
                        "Background data the web agent needs: URLs the user "
                        "mentioned, user constraints (location, account, "
                        "deadlines), prior tool results, or values to fill "
                        "into forms. The agent has no memory of your "
                        "conversation — anything from earlier turns must be "
                        "repeated here. Always include the target URL if the "
                        "user gave one."
                    ),
                },
                "files": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "Workspace file paths the agent needs (e.g. a resume "
                        "to fill into a form). The harness extracts text from "
                        "each file (txt/md/docx/pdf/xlsx/pptx are supported) "
                        "and injects it into the agent's context. Use this "
                        "instead of opening the file yourself first — it "
                        "saves a round trip."
                    ),
                },
            },
            "required": ["task"],
        },
    },
}

TOOLS: list[Tool] = [
    Tool(
        name="bash",
        definition=_find_def("bash", _CORE_DEFS),
        execute=_exec_bash,
        requires_approval=True,
        approval_check=lambda _name, args, is_sandbox: classify_bash_command(
            args.get("command", ""), is_sandbox=is_sandbox
        ),
    ),
    Tool(
        name="create",
        definition=_find_def("create", _CORE_DEFS),
        execute=_exec_create,
        requires_approval=True,
        approval_check=lambda name, args, is_sandbox: classify_file_tool(
            name, args.get("filename", ""), is_sandbox
        ),
    ),
    Tool(
        name="open",
        definition=_find_def("open", _CORE_DEFS),
        execute=_exec_open,
        requires_approval=True,
        approval_check=lambda _name, args, is_sandbox: classify_sensitive_read(
            args.get("path", ""), is_sandbox
        ),
    ),
    Tool(
        name="edit",
        definition=_find_def("edit", _CORE_DEFS),
        execute=_exec_edit,
        requires_approval=True,
        # edit has no filename arg; caller injects "_current_file"
        approval_check=lambda name, args, is_sandbox: classify_file_tool(
            name, args.get("_current_file", ""), is_sandbox
        ),
    ),
    Tool(
        name="insert",
        definition=_find_def("insert", _CORE_DEFS),
        execute=_exec_insert,
        requires_approval=True,
        # insert has no filename arg; caller injects "_current_file"
        approval_check=lambda name, args, is_sandbox: classify_file_tool(
            name, args.get("_current_file", ""), is_sandbox
        ),
    ),
    Tool(name="goto", definition=_find_def("goto", _CORE_DEFS), execute=_exec_goto),
    Tool(
        name="scroll_down",
        definition=_find_def("scroll_down", _CORE_DEFS),
        execute=_exec_scroll_down,
    ),
    Tool(
        name="scroll_up",
        definition=_find_def("scroll_up", _CORE_DEFS),
        execute=_exec_scroll_up,
    ),
    Tool(
        name="search_dir",
        definition=_find_def("search_dir", _CORE_DEFS),
        execute=_exec_search_dir,
    ),
    Tool(
        name="search_file",
        definition=_find_def("search_file", _CORE_DEFS),
        execute=_exec_search_file,
    ),
    Tool(
        name="find_file",
        definition=_find_def("find_file", _CORE_DEFS),
        execute=_exec_find_file,
    ),
    Tool(
        name="request_user_input",
        definition=_find_def("request_user_input", _CORE_DEFS),
    ),
]
