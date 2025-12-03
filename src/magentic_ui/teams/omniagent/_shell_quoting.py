"""Host-side shell quoting helpers that preserve ``~`` expansion.

Standard ``shlex.quote()`` wraps a string in single quotes, which prevents
the shell from expanding ``~`` to ``$HOME``. The helpers here produce shell
syntax that keeps ``~`` unquoted at the start of a word so the sandbox
shell expands it at runtime, using the sandbox's own ``$HOME``.

``shell_quote_path(path)``
    Used by host tools that *build* a shell command around a raw path
    argument (e.g. ``_exec_create``).

``normalize_quoted_tildes(command)``
    Used by the ``bash`` tool to rewrite *existing* shell commands the
    model wrote, moving a token-leading ``~`` outside its quotes.
"""

from __future__ import annotations

import re
import shlex


def shell_quote_path(path: str) -> str:
    """Quote ``path`` for a shell command, preserving ``~`` expansion.

    For paths that start with ``~/``, the ``~`` is left unquoted (so the
    shell expands it) and only the remainder is ``shlex.quote``-d. Paths
    that don't start with ``~`` use ``shlex.quote`` as-is.

    Examples:
        ``~`` → ``~``
        ``~/foo`` → ``~/foo``
        ``~/My Documents/foo.txt`` → ``~/'My Documents/foo.txt'``
        ``regular/path`` → ``regular/path``
        ``path with space`` → ``'path with space'``
    """
    if path == "~":
        return "~"
    if path.startswith("~/"):
        return "~/" + shlex.quote(path[2:])
    return shlex.quote(path)


# Token boundary: start of string, whitespace, or `=` (for KEY=val).
_QUOTED_TILDE_DOUBLE = re.compile(r'(^|[\s=])"~/([^"]*)"')
_QUOTED_TILDE_SINGLE = re.compile(r"(^|[\s=])'~/([^']*)'")
_LONE_QUOTED_TILDE = re.compile(r'(^|[\s=])["\']~["\']')


def normalize_quoted_tildes(command: str) -> tuple[str, bool]:
    """Move a token-leading quoted ``~`` outside the quotes.

    The shell performs tilde expansion only when ``~`` is unquoted at the
    start of a word. If the model writes ``mv "src" "~/dest"``, the quoted
    ``~`` stays literal and the move targets a path that begins with the
    character ``~``. This helper rewrites such patterns to a form the shell
    can expand:

        ``"~/foo"`` → ``~/"foo"``
        ``'~/foo'`` → ``~/'foo'``
        ``"~"``     → ``~``
        ``'~'``     → ``~``

    Only fires at token boundaries (start of string, whitespace, or ``=``),
    so mid-string occurrences like ``echo "the path ~/foo"`` are left
    alone.

    Returns:
        ``(new_command, changed)`` — ``changed`` is True iff a rewrite
        fired.
    """
    new = _QUOTED_TILDE_DOUBLE.sub(r'\1~/"\2"', command)
    new = _QUOTED_TILDE_SINGLE.sub(r"\1~/'\2'", new)
    new = _LONE_QUOTED_TILDE.sub(r"\1~", new)
    return new, new != command
