"""Bash observer protocol and registry.

A ``BashObserver`` inspects a bash command and its execution result and
optionally emits an ``Annotation`` appended to the model-visible output.
New observers are added by implementing the protocol and appending to
``BASH_OBSERVERS``.

``enrich()`` collects path probe requests from observers, runs one
merged pre/post stat probe, executes the user's command between them,
and asks each observer for an annotation.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol

from ._command_policy import is_mount_path
from ._shell_quoting import normalize_quoted_tildes
from ._verifier import (
    VerifierClass,
    build_stat_probe_command,
    decide_verifier_class,
    detect_word_split_hint,
    diff_states,
    extract_candidate_paths,
    extract_destinations,
    parse_stat_output,
    render_diff,
    should_skip_after_exec,
)

if TYPE_CHECKING:
    from ...sandbox import ExecuteResult, Sandbox

_log = logging.getLogger(__name__)

_VERIFIER_HEADER = "[harness verification — filesystem after command]"
_HINT_HEADER = "[harness hint]"
_WARNING_HEADER = "[harness warning]"


@dataclass(frozen=True)
class Annotation:
    """Harness-injected note appended after a bash command's output."""

    text: str


@dataclass(frozen=True)
class PathProbe:
    """Paths an observer wants stat-probed."""

    paths: list[str]
    need_pre: bool = True


@dataclass
class ObserveContext:
    """Per-call observer state, threaded through the phases of enrich()."""

    command: str
    cwd: Path
    sandbox: Sandbox
    pre_state: dict[str, Any] = field(default_factory=dict[str, Any])
    result: ExecuteResult | None = None


class BashObserver(Protocol):
    """Post-hoc evidence collector for a bash command."""

    name: str

    async def contribute_paths(self, ctx: ObserveContext) -> PathProbe | None:
        """Return paths for the merged stat probe, or None."""
        ...

    async def post(
        self, ctx: ObserveContext, prior: list[Annotation]
    ) -> Annotation | None:
        """Return an annotation based on ctx, or None."""
        ...


class FilesystemDiffObserver:
    """Emit a filesystem diff for paths touched by destructive or mutating commands."""

    name = "filesystem_diff"

    async def contribute_paths(self, ctx: ObserveContext) -> PathProbe | None:
        cls = decide_verifier_class(ctx.command)
        if cls is VerifierClass.NONE:
            return None
        paths = extract_candidate_paths(ctx.command)
        if not paths:
            return None
        ctx.pre_state[self.name] = {"cls": cls, "paths": paths}
        return PathProbe(
            paths=paths,
            need_pre=cls is VerifierClass.PRE_AND_POST,
        )

    async def post(
        self, ctx: ObserveContext, prior: list[Annotation]
    ) -> Annotation | None:
        state = ctx.pre_state.get(self.name)
        if state is None or ctx.result is None:
            return None
        if "fs_after" not in ctx.pre_state:
            return None
        cls: VerifierClass = state["cls"]
        paths: list[str] = state["paths"]
        if cls is VerifierClass.PRE_AND_POST:
            before = ctx.pre_state.get("fs_before")
            if before is None:
                # Pre-probe failed; without a baseline we cannot tell
                # "deleted by this command" from "never existed", so
                # skip the diff rather than mis-report present/absent.
                return None
        else:
            before = None
        after = ctx.pre_state["fs_after"]
        changes = diff_states(paths, before, after)
        rendered = render_diff(changes, cls)
        if rendered is None:
            return None
        return Annotation(text=f"{_VERIFIER_HEADER}\n{rendered}")


class WorkspaceEscapeObserver:
    """Warn when mv/cp/ln/mkdir/rmdir destinations resolve outside user-visible paths.

    User-visible paths are the agent workspace and any directories the user
    shared via mounts. A destination outside both is sandbox-internal — it
    persists only inside the VM and is lost at session end. The model
    rarely intends to write there, so flag it.
    """

    name = "workspace_escape"

    async def contribute_paths(self, ctx: ObserveContext) -> PathProbe | None:
        return None

    async def post(
        self, ctx: ObserveContext, prior: list[Annotation]
    ) -> Annotation | None:
        import os.path as _op

        dests = extract_destinations(ctx.command)
        if not dests:
            return None
        cwd_abs = _op.abspath(ctx.cwd)
        escapes: list[str] = []
        for d in dests:
            if d.startswith("~"):
                # Leave ~-expansion to the shell; we can't resolve $HOME here.
                continue
            dest_abs = (
                _op.abspath(d) if _op.isabs(d) else _op.abspath(_op.join(ctx.cwd, d))
            )
            # User-visible target #1: under the agent workspace (== cwd).
            try:
                common = _op.commonpath([dest_abs, cwd_abs])
            except ValueError:
                common = None
            if common == cwd_abs:
                continue
            # User-visible target #2: under a mounts root.
            if is_mount_path(dest_abs):
                continue
            escapes.append(d)
        if not escapes:
            return None
        body = "\n".join(
            f"  destination '{e}' is outside the workspace and any shared mount"
            for e in escapes
        )
        text = (
            f"{_WARNING_HEADER}\n{body}\n"
            f"(cwd={ctx.cwd}). Only writes under the workspace and shared mount "
            "directories are user-visible — other paths persist only inside the "
            "sandbox and are lost when the session ends. If you intended a "
            "user-shared directory, use its full mount path."
        )
        return Annotation(text=text)


class WordSplitHintObserver:
    """Emit a hint when a failed command looks like a bash word-split bug.

    Stays silent when any earlier observer already emitted.
    """

    name = "word_split_hint"

    async def contribute_paths(self, ctx: ObserveContext) -> PathProbe | None:
        return None

    async def post(
        self, ctx: ObserveContext, prior: list[Annotation]
    ) -> Annotation | None:
        if ctx.result is None or ctx.result.exit_code == 0:
            return None
        if prior:
            return None
        hint = detect_word_split_hint(
            ctx.command, ctx.result.exit_code, ctx.result.stderr
        )
        if hint is None:
            return None
        return Annotation(text=f"{_HINT_HEADER} {hint}")


BASH_OBSERVERS: tuple[BashObserver, ...] = (
    FilesystemDiffObserver(),
    WorkspaceEscapeObserver(),
    WordSplitHintObserver(),
)


async def enrich(
    command: str,
    cwd: Path,
    sandbox: Sandbox,
    observers: tuple[BashObserver, ...] | None = None,
) -> tuple[ExecuteResult, list[Annotation]]:
    """Probe pre, execute command, probe post, collect annotations from observers."""
    if observers is None:
        observers = BASH_OBSERVERS

    rewritten, tildes_rewritten = normalize_quoted_tildes(command)
    pre_annotations: list[Annotation] = []
    if tildes_rewritten:
        pre_annotations.append(
            Annotation(
                text=(
                    f"{_HINT_HEADER} Quoted `~` does not expand in the shell. "
                    f"Rewrote so tilde expansion fires:\n"
                    f"  {command}\n  → {rewritten}"
                )
            )
        )
        command = rewritten

    ctx = ObserveContext(command=command, cwd=cwd, sandbox=sandbox)

    pre_paths: list[str] = []
    post_paths: list[str] = []
    for o in observers:
        req = await o.contribute_paths(ctx)
        if req is None:
            continue
        if req.need_pre:
            pre_paths.extend(req.paths)
        post_paths.extend(req.paths)
    pre_paths = list(dict.fromkeys(pre_paths))
    post_paths = list(dict.fromkeys(post_paths))

    if pre_paths:
        try:
            pre = await sandbox.execute(build_stat_probe_command(pre_paths), cwd=cwd)
            ctx.pre_state["fs_before"] = parse_stat_output(pre.stdout)
        except Exception as exc:
            _log.debug("merged pre-probe failed: %s", exc)

    ctx.result = await sandbox.execute(command, cwd=cwd)

    if post_paths and not should_skip_after_exec(
        ctx.result.exit_code, ctx.result.stderr
    ):
        try:
            post = await sandbox.execute(build_stat_probe_command(post_paths), cwd=cwd)
            ctx.pre_state["fs_after"] = parse_stat_output(post.stdout)
        except Exception as exc:
            _log.debug("merged post-probe failed: %s", exc)

    annotations: list[Annotation] = list(pre_annotations)
    for o in observers:
        try:
            annotation = await o.post(ctx, annotations)
        except Exception as exc:
            _log.warning("observer %s.post() raised: %s", o.name, exc)
            continue
        if annotation is not None:
            annotations.append(annotation)

    return ctx.result, annotations
