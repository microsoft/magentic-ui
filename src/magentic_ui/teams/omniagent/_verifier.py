"""Post-hoc filesystem verifier for destructive bash commands.

The verifier surfaces evidence of what changed after a destructive command
runs. The model already sees the command's stdout/stderr/exit_code; the
verifier adds a diff of filesystem state for the paths the command touched,
so the model can self-correct on no-op cases (typo'd path, word-split
arguments where bash split an unquoted whitespace path, etc.). Commands
that contain unquoted shell metacharacters (including unquoted globs)
are skipped — see the skip conditions below.

This module is **pure logic**: path extraction, stat-output parsing, diff,
and rendering. The actual sandbox round-trips for the stat probes live in
``enrich()`` in ``_bash_observers.py``, invoked from ``_exec_bash`` in
``_registry.py``.

Verifier classes:

* ``PRE_AND_POST`` — for ``rm``/``rmdir``/``shred``. Needs a baseline because
  "missing now" could mean "deleted" or "never existed."
* ``POST_ONLY`` — for ``mv``/``cp``/``chmod``/``chown``/``ln``/``tee``/
  ``truncate``. The post-state alone tells the story.
* ``NONE`` — read-only commands and everything else.

Skip conditions (verifier returns no block, original output flows through):

* command contains unquoted shell metacharacters (``;`` ``&&`` ``||`` ``|``
  ``$`` ``*`` ``?`` ``[`` ``~`` backtick);
* path extraction fails or returns 0 candidates;
* any single path token exceeds Linux ``PATH_MAX`` (4096 bytes);
* command failed with stderr (model already has the error).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------


class VerifierClass(str, Enum):
    """Decides whether (and how) to run the post-hoc verifier."""

    NONE = "none"
    POST_ONLY = "post"
    PRE_AND_POST = "both"


@dataclass(frozen=True)
class FsState:
    """Snapshot of a single filesystem entry."""

    size: int
    mtime: int
    ftype: str


@dataclass(frozen=True)
class Change:
    """One entry in the diff between pre and post probe.

    ``kind`` values:

    * ``removed``    — was present, now missing (PRE_AND_POST)
    * ``added``      — was missing, now present (PRE_AND_POST)
    * ``changed``    — present in both, size or mtime differs (PRE_AND_POST)
    * ``unchanged``  — present in both, identical (PRE_AND_POST)
    * ``missing``    — missing in both (PRE_AND_POST; usually skipped)
    * ``present``    — exists post-cmd (POST_ONLY)
    * ``absent``     — does not exist post-cmd (POST_ONLY)
    """

    path: str
    kind: str


# ---------------------------------------------------------------------------
# Path extraction
# ---------------------------------------------------------------------------

_MAX_PATHS = 20
_PATH_MAX_BYTES = 4096  # Linux PATH_MAX

# Single chars that, if unquoted, mean we cannot reason about the command
# without doing shell expansion. Bail to keep the verifier safe.
_UNSAFE_UNQUOTED_CHARS = set(";|&$*?[~`")


def _has_unsafe_unquoted_metachar(s: str) -> bool:
    """Return True iff ``s`` contains a metachar from ``_UNSAFE_UNQUOTED_CHARS``
    that is NOT inside single quotes, double quotes, or escaped with ``\\``."""
    in_single = False
    in_double = False
    i = 0
    n = len(s)
    while i < n:
        c = s[i]
        if c == "\\" and i + 1 < n:
            i += 2
            continue
        if c == "'" and not in_double:
            in_single = not in_single
        elif c == '"' and not in_single:
            in_double = not in_double
        elif not in_single and not in_double and c in _UNSAFE_UNQUOTED_CHARS:
            return True
        i += 1
    return False


def extract_candidate_paths(command: str) -> list[str] | None:
    """Extract path tokens from ``command``. Returns ``None`` to abort.

    Best-effort heuristic. False positives (a literal that isn't a path) just
    stat as missing both times and don't appear in the diff. False negatives
    (a real path we miss) leave a gap in verification — acceptable in v1.
    """
    if not command.strip():
        return None
    if _has_unsafe_unquoted_metachar(command):
        return None
    # Lazy import — shlex is stdlib, but keep the module top fast.
    import shlex

    try:
        tokens = shlex.split(command, posix=True)
    except ValueError:
        return None  # unbalanced quotes
    if not tokens:
        return None

    candidates: list[str] = []
    in_options = True
    for tok in tokens[1:]:  # drop program name
        if not tok:
            continue
        if in_options:
            if tok == "--":
                in_options = False
                continue
            if tok.startswith("-"):
                continue
        if len(tok.encode()) > _PATH_MAX_BYTES:
            return None
        candidates.append(tok)
    return candidates[:_MAX_PATHS]


_DEST_LAST_PROGRAMS: frozenset[str] = frozenset({"mv", "cp", "ln"})
_DEST_ALL_PROGRAMS: frozenset[str] = frozenset({"mkdir", "rmdir"})


def extract_destinations(command: str) -> list[str] | None:
    """Return write destinations from ``command``, or ``None`` if not applicable.

    For ``mv``/``cp``/``ln``: the last positional argument.
    For ``mkdir``/``rmdir``: every positional argument.
    Returns ``None`` for any other program or for commands that cannot be
    safely parsed (unsafe unquoted metachars, unbalanced quotes, empty).
    """
    if not command.strip():
        return None
    if _has_unsafe_unquoted_metachar(command):
        return None
    import shlex

    try:
        tokens = shlex.split(command, posix=True)
    except ValueError:
        return None
    if not tokens:
        return None
    program = tokens[0].rsplit("/", 1)[-1]
    args: list[str] = []
    in_options = True
    for tok in tokens[1:]:
        if not tok:
            continue
        if in_options:
            if tok == "--":
                in_options = False
                continue
            if tok.startswith("-"):
                continue
        args.append(tok)
    if program in _DEST_ALL_PROGRAMS:
        return args or None
    if program in _DEST_LAST_PROGRAMS:
        if len(args) < 2:
            return None
        return [args[-1]]
    return None


# ---------------------------------------------------------------------------
# Verifier-class decision
# ---------------------------------------------------------------------------

_PRE_AND_POST_PROGRAMS: frozenset[str] = frozenset({"rm", "rmdir", "shred"})
_POST_ONLY_PROGRAMS: frozenset[str] = frozenset(
    {"mv", "cp", "chmod", "chown", "ln", "tee", "truncate"}
)


def decide_verifier_class(command: str) -> VerifierClass:
    """Return the verifier class for ``command``.

    Looks at the program name only — flags and arguments don't change the
    verifier class. Resolves ``/usr/bin/rm`` → ``rm``.
    """
    stripped = command.strip()
    if not stripped:
        return VerifierClass.NONE
    first = stripped.split(maxsplit=1)[0]
    program = first.rsplit("/", 1)[-1]
    if program in _PRE_AND_POST_PROGRAMS:
        return VerifierClass.PRE_AND_POST
    if program in _POST_ONLY_PROGRAMS:
        return VerifierClass.POST_ONLY
    return VerifierClass.NONE


# ---------------------------------------------------------------------------
# stat output parsing
# ---------------------------------------------------------------------------


def parse_stat_output(stdout: str) -> dict[str, FsState | None]:
    """Parse the output of ``stat -c '%n|%s|%Y|%F' -- p1 p2 ...``.

    Missing files are simply absent from the output (because we redirect
    stat's per-file errors to /dev/null at the call site). Malformed lines
    are dropped silently — the verifier degrades to "we don't know about
    this path" rather than crashing.
    """
    result: dict[str, FsState | None] = {}
    for raw_line in stdout.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        # split('|', 3) gives at most 4 parts. If a path itself contains '|',
        # the parser may misinterpret — undefined behavior, accepted in v1.
        parts = line.split("|", 3)
        if len(parts) != 4:
            continue
        name, size_s, mtime_s, ftype = parts
        try:
            result[name] = FsState(int(size_s), int(mtime_s), ftype)
        except ValueError:
            continue
    return result


# ---------------------------------------------------------------------------
# Diff
# ---------------------------------------------------------------------------


def diff_states(
    candidates: list[str],
    before: dict[str, FsState | None] | None,
    after: dict[str, FsState | None],
) -> list[Change]:
    """Compute the diff in the order of ``candidates``.

    ``before is None`` signals POST_ONLY mode: we report ``present`` /
    ``absent`` based on the post-state alone. Otherwise PRE_AND_POST mode
    classifies into removed / added / changed / unchanged / missing.
    """
    changes: list[Change] = []
    for path in candidates:
        a = after.get(path)
        if before is None:
            changes.append(Change(path, "present" if a is not None else "absent"))
            continue
        b = before.get(path)
        if b is None and a is None:
            changes.append(Change(path, "missing"))
        elif b is None and a is not None:
            changes.append(Change(path, "added"))
        elif b is not None and a is None:
            changes.append(Change(path, "removed"))
        elif b != a:
            changes.append(Change(path, "changed"))
        else:
            changes.append(Change(path, "unchanged"))
    return changes


# ---------------------------------------------------------------------------
# Render
# ---------------------------------------------------------------------------

_MAX_RENDERED_LINES = 10

# Order in which to display change kinds. "missing" is dropped entirely;
# "unchanged" / "present" come last because they're the lowest-signal.
_KIND_ORDER: dict[str, int] = {
    "removed": 0,
    "added": 1,
    "changed": 2,
    "absent": 3,
    "unchanged": 4,
    "present": 5,
}


def render_diff(changes: list[Change], cls: VerifierClass) -> str | None:
    """Render the diff as a verifier block, or ``None`` to suppress.

    Suppression rules:

    * No changes → suppress (nothing to report).
    * PRE_AND_POST and every change is ``missing`` → suppress (the model
      asked about paths that never existed; not actionable).
    * POST_ONLY and every change is ``present`` → suppress (boring; nothing
      surprising about all targets existing after a ``cp``).
    """
    if not changes:
        return None

    # PRE_AND_POST: always drop "missing" lines from output.
    if cls is VerifierClass.PRE_AND_POST:
        visible = [c for c in changes if c.kind != "missing"]
        if not visible:
            return None
    elif cls is VerifierClass.POST_ONLY:
        # If every entry is "present", the verifier adds no signal.
        if all(c.kind == "present" for c in changes):
            return None
        visible = list(changes)
    else:
        return None

    visible.sort(key=lambda c: (_KIND_ORDER.get(c.kind, 99), c.path))

    capped = visible[:_MAX_RENDERED_LINES]
    overflow = len(visible) - len(capped)

    lines = [f"{c.kind}: {c.path}" for c in capped]
    if overflow > 0:
        lines.append(f"(+{overflow} more)")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Probe-command builder (used by the call site to issue stat over the
# candidate set in a single sandbox round-trip)
# ---------------------------------------------------------------------------


def build_stat_probe_command(paths: list[str]) -> str:
    """Build a single bash command that stats every path in ``paths``.

    Uses ``--`` to terminate flag parsing so paths starting with ``-`` work.
    Per-path errors go to /dev/null so missing files are simply absent from
    stdout. Returns an empty string when ``paths`` is empty.
    """
    if not paths:
        return ""
    import shlex

    quoted = " ".join(shlex.quote(p) for p in paths)
    return f"stat -c '%n|%s|%Y|%F' -- {quoted} 2>/dev/null || true"


# ---------------------------------------------------------------------------
# Skip-after-execution check
# ---------------------------------------------------------------------------


_PATH_ERROR_MARKERS: tuple[str, ...] = (
    "No such file or directory",
    "cannot stat",
    "cannot access",
)


def detect_word_split_hint(command: str, exit_code: int, stderr: str) -> str | None:
    """Return a hint when a failed bash command's tokens look word-split.

    Fires only when:

    1. ``exit_code != 0``;
    2. stderr contains a path-resolution error marker;
    3. after ``shlex.split``, an adjacent token pair ``(prev, curr)`` satisfies:

       * neither starts with ``-`` (not a flag);
       * ``prev`` starts with ``/`` (absolute path);
       * ``prev`` does NOT end with ``/`` (looks incomplete);
       * ``curr`` does NOT start with ``/``, ``./``, ``../``, ``~`` (not a
         fresh path);
       * ``curr`` contains ``/`` or ``.`` (path-y enough).

    The reconstructed candidate is ``prev + " " + curr`` — the path the model
    most likely intended before bash word-split it.
    """
    if exit_code == 0:
        return None
    if not any(marker in stderr for marker in _PATH_ERROR_MARKERS):
        return None
    import shlex

    try:
        tokens = shlex.split(command, posix=True)
    except ValueError:
        return None
    if len(tokens) < 3:
        return None

    for i in range(len(tokens) - 1):
        prev, curr = tokens[i], tokens[i + 1]
        if prev.startswith("-") or curr.startswith("-"):
            continue
        if not prev.startswith("/"):
            continue
        if prev.endswith("/"):
            continue
        if curr.startswith(("/", "./", "../", "~")):
            continue
        if "/" not in curr and "." not in curr:
            continue
        candidate = f"{prev} {curr}"
        return (
            "Your command appears to contain a path with unquoted whitespace. "
            "Bash word-split it into separate arguments.\n"
            f"Likely intended path: '{candidate}'\n"
            f"Quote it with single quotes when calling bash, "
            f"e.g. mv '{candidate}' /dst/."
        )
    return None


def should_skip_after_exec(exit_code: int, stderr: str) -> bool:
    """Decide whether to skip the verifier *after* the command runs.

    Skip when the command clearly didn't execute or already produced an
    error message — the model has the error from the kernel and a
    "verification: nothing changed" line would just be noise.

    * exit_code == -1 → infra error (guest agent never reached the shell)
    * exit_code in (126, 127) → not executable / not found
    * exit_code != 0 AND stderr non-empty → real error already surfaced
    """
    if exit_code in (-1, 126, 127):
        return True
    if exit_code != 0 and stderr.strip():
        return True
    return False
