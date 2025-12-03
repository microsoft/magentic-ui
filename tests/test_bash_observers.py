"""Tests for the bash observer protocol and enrich() orchestration."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from magentic_ui.sandbox import ExecuteResult
from magentic_ui.teams.omniagent._bash_observers import (
    Annotation,
    FilesystemDiffObserver,
    ObserveContext,
    PathProbe,
    WordSplitHintObserver,
    WorkspaceEscapeObserver,
    enrich,
)

CWD = Path("/tmp")


class FakeSandbox:
    """Records execute() calls and pops canned responses from a queue."""

    guest_tools_dir = "/tools"

    def __init__(self, responses: list[ExecuteResult]) -> None:
        self._responses = list(responses)
        self.calls: list[tuple[str, Any]] = []

    async def execute(
        self,
        cmd: str,
        *,
        timeout: int = 60,
        cwd: Any = None,
        extra_env: dict[str, str] | None = None,
    ) -> ExecuteResult:
        self.calls.append((cmd, cwd))
        if self._responses:
            return self._responses.pop(0)
        return ExecuteResult(stdout="", stderr="", exit_code=0)


@pytest.mark.asyncio
async def test_enrich_with_no_observers_runs_command_only() -> None:
    sandbox = FakeSandbox([ExecuteResult("hello\n", "", 0)])
    result, annotations = await enrich("echo hello", CWD, sandbox, observers=())
    assert result.exit_code == 0
    assert result.stdout == "hello\n"
    assert annotations == []
    assert len(sandbox.calls) == 1
    assert sandbox.calls[0] == ("echo hello", CWD)


@pytest.mark.asyncio
async def test_filesystem_diff_pre_and_post_for_rm() -> None:
    sandbox = FakeSandbox(
        [
            ExecuteResult(
                stdout="/tmp/foo|10|1700000000|regular file\n", stderr="", exit_code=0
            ),
            ExecuteResult(stdout="", stderr="", exit_code=0),
            ExecuteResult(stdout="", stderr="", exit_code=0),
        ]
    )
    result, annotations = await enrich(
        "rm /tmp/foo",
        CWD,
        sandbox,
        observers=(FilesystemDiffObserver(),),
    )
    assert result.exit_code == 0
    assert len(sandbox.calls) == 3
    assert len(annotations) == 1
    assert "[harness verification" in annotations[0].text
    assert "removed: /tmp/foo" in annotations[0].text


@pytest.mark.asyncio
async def test_filesystem_diff_post_only_skips_pre_probe_for_mv() -> None:
    sandbox = FakeSandbox(
        [
            ExecuteResult(stdout="", stderr="", exit_code=0),
            ExecuteResult(
                stdout="/tmp/dst|0|1700000000|regular file\n", stderr="", exit_code=0
            ),
        ]
    )
    result, annotations = await enrich(
        "mv /tmp/src /tmp/dst",
        CWD,
        sandbox,
        observers=(FilesystemDiffObserver(),),
    )
    assert result.exit_code == 0
    assert len(sandbox.calls) == 2
    assert sandbox.calls[0][0] == "mv /tmp/src /tmp/dst"


@pytest.mark.asyncio
async def test_filesystem_diff_silent_for_safe_command() -> None:
    sandbox = FakeSandbox([ExecuteResult("file1\nfile2\n", "", 0)])
    result, annotations = await enrich(
        "ls /tmp",
        CWD,
        sandbox,
        observers=(FilesystemDiffObserver(),),
    )
    assert annotations == []
    assert len(sandbox.calls) == 1


@pytest.mark.asyncio
async def test_word_split_hint_fires_on_path_error() -> None:
    sandbox = FakeSandbox(
        [
            ExecuteResult(
                stdout="",
                stderr="mv: cannot stat '/tmp/My': No such file or directory",
                exit_code=1,
            ),
        ]
    )
    result, annotations = await enrich(
        "mv /tmp/My Folder/file.txt /dst/",
        CWD,
        sandbox,
        observers=(WordSplitHintObserver(),),
    )
    assert len(annotations) == 1
    assert "[harness hint]" in annotations[0].text


@pytest.mark.asyncio
async def test_word_split_hint_silent_on_success() -> None:
    sandbox = FakeSandbox([ExecuteResult("", "", 0)])
    result, annotations = await enrich(
        "mv /tmp/a /tmp/b",
        CWD,
        sandbox,
        observers=(WordSplitHintObserver(),),
    )
    assert annotations == []


@pytest.mark.asyncio
async def test_word_split_hint_suppressed_when_prior_annotation_present() -> None:
    """When FilesystemDiffObserver emits, WordSplitHintObserver must stay silent."""
    sandbox = FakeSandbox(
        [
            ExecuteResult(
                stdout="/tmp/foo|10|1700000000|regular file\n", stderr="", exit_code=0
            ),
            ExecuteResult(stdout="", stderr="", exit_code=0),
            ExecuteResult(stdout="", stderr="", exit_code=0),
        ]
    )
    result, annotations = await enrich(
        "rm /tmp/foo",
        CWD,
        sandbox,
        observers=(FilesystemDiffObserver(), WordSplitHintObserver()),
    )
    assert len(annotations) == 1
    assert "[harness verification" in annotations[0].text


@pytest.mark.asyncio
async def test_workspace_escape_warns_for_destination_outside_cwd() -> None:
    sandbox = FakeSandbox([ExecuteResult("", "", 0)])
    result, annotations = await enrich(
        "mv /tmp/a /etc/foo",
        CWD,
        sandbox,
        observers=(WorkspaceEscapeObserver(),),
    )
    assert result.exit_code == 0
    assert len(annotations) == 1
    assert "[harness warning]" in annotations[0].text
    assert "/etc/foo" in annotations[0].text


@pytest.mark.asyncio
async def test_workspace_escape_silent_for_destination_under_mount() -> None:
    """A write into a user-shared mount root is legitimate, not an escape."""
    sandbox = FakeSandbox([ExecuteResult("", "", 0)])
    result, annotations = await enrich(
        "mkdir -p /sessions/1/mounts/Downloads-test-17/Documents",
        Path("/sessions/1/workspace"),
        sandbox,
        observers=(WorkspaceEscapeObserver(),),
    )
    assert result.exit_code == 0
    assert annotations == []


@pytest.mark.asyncio
async def test_workspace_escape_silent_for_destination_inside_cwd() -> None:
    sandbox = FakeSandbox([ExecuteResult("", "", 0)])
    result, annotations = await enrich(
        "mv /tmp/a /tmp/b",
        CWD,
        sandbox,
        observers=(WorkspaceEscapeObserver(),),
    )
    assert result.exit_code == 0
    assert annotations == []


@pytest.mark.asyncio
async def test_observer_exception_does_not_break_enrich() -> None:
    class ExplodingObserver:
        name = "exploding"

        async def contribute_paths(self, ctx: ObserveContext) -> PathProbe | None:
            return None

        async def post(
            self, ctx: ObserveContext, prior: list[Annotation]
        ) -> Annotation | None:
            raise RuntimeError("boom")

    sandbox = FakeSandbox([ExecuteResult("ok\n", "", 0)])
    result, annotations = await enrich(
        "echo ok",
        CWD,
        sandbox,
        observers=(ExplodingObserver(),),
    )
    assert result.stdout == "ok\n"
    assert annotations == []
