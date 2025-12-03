"""Host path security validation for sandbox mounts.

Prevents mounting sensitive directories (.ssh, .aws, /etc, etc.)
into the sandbox VM. All paths are resolved via realpath to catch
symlink escapes.
"""

from __future__ import annotations

import os
from pathlib import Path

from loguru import logger


# Paths relative to user home directory (resolved at runtime)
_DENIED_HOME_RELATIVE = {
    ".ssh",
    ".aws",
    ".gnupg",
    ".gpg",
    ".kube",
    ".docker",
    ".npmrc",
    ".pypirc",
    ".netrc",
    ".bash_history",
    ".zsh_history",
    ".python_history",
    ".config/gcloud",
    ".config/gh",
    ".magentic_ui/.env",
    ".magentic_ui/magentic_ui.db",
}

# Absolute paths always blocked
_DENIED_ABSOLUTE = {
    "/etc",
    "/proc",
    "/sys",
    "/dev",
    "/root",
    "/var/run",
    "/run",
}


def _denied_paths() -> list[Path]:
    """Build the list of denied paths (absolute, realpath-resolved)."""
    home = Path.home()
    denied = [Path(os.path.realpath(home / rel)) for rel in _DENIED_HOME_RELATIVE]
    denied.extend(Path(os.path.realpath(p)) for p in _DENIED_ABSOLUTE)
    return denied


def is_denied_path(path: str | Path) -> tuple[bool, Path | None]:
    """Resolve symlinks and check the denylist.

    Returns ``(True, matched_denial)`` if ``path`` is or is under any
    denied path; ``(False, None)`` otherwise. Used by both the mount
    validator and the runtime classifier — single source of truth for
    "this path is sensitive."
    """
    resolved = Path(os.path.realpath(str(path)))
    for denied_path in _denied_paths():
        if resolved == denied_path or resolved.is_relative_to(denied_path):
            return True, denied_path
    return False, None


def expand_tilde_and_home(tok: str, home: str) -> str:
    """Naive ~ / $HOME / ${HOME} expansion (not full shell expansion).

    Used by find_denied_path_in_command — only handles the path-prefix
    forms an agent typically writes.
    """
    if tok == "~":
        return home
    if tok.startswith("~/"):
        return home + tok[1:]
    return tok.replace("${HOME}", home).replace("$HOME", home)


def find_denied_path_in_command(command: str) -> str | None:
    """Tokenize a shell command and return the first token whose
    resolved path is in the denylist, else ``None``.

    Pure stdlib (``shlex`` + ``Path``), no regex. Doesn't claim to catch
    every shell construct (e.g. ``cat $(realpath ~/.ssh/key)``); for
    bishop's threat model the simple form covers the realistic attack
    surface.
    """
    import shlex

    try:
        tokens = shlex.split(command, posix=True)
    except ValueError:
        # malformed shell — bail; the other DENY/REQUIRE_APPROVAL rules
        # in classify_bash_command still apply.
        return None

    home = str(Path.home())
    for tok in tokens:
        expanded = expand_tilde_and_home(tok, home)
        if not expanded.startswith("/"):
            continue
        denied, _matched = is_denied_path(expanded)
        if denied:
            return tok
    return None


def validate_host_path(path: str) -> str:
    """Validate and canonicalize a host path for mounting.

    Security checks:
    1. ``os.path.realpath`` — resolve symlinks (prevents symlink escape)
    2. Must be an existing directory (not file, device, socket)
    3. Denylist — ``Path.is_relative_to()`` for proper component matching
    4. Audit log — original → resolved path mapping

    Returns:
        The resolved (real) absolute path.

    Raises:
        ValueError: If the path is denied, not a directory, or doesn't exist.
    """
    if not path:
        raise ValueError("Host path must not be empty")
    resolved = Path(os.path.realpath(path))

    if str(resolved) != os.path.abspath(path):
        logger.warning(
            f"Mount audit: path resolves through symlink: {path!r} → {resolved!r}"
        )

    if not resolved.exists():
        raise ValueError(f"Host path does not exist: {path!r} (resolved: {resolved!r})")

    if not resolved.is_dir():
        raise ValueError(
            f"Host path is not a directory: {path!r} (resolved: {resolved!r})"
        )

    sensitive, matched = is_denied_path(path)
    if sensitive:
        raise ValueError(
            f"Host path is denied (sensitive location): {path!r} "
            f"(resolved: {resolved!r}, matched: {matched!r})"
        )

    # Block Windows AppData via WSL mount paths
    resolved_parts = resolved.parts
    if (
        len(resolved_parts) >= 6
        and resolved_parts[1] == "mnt"
        and len(resolved_parts[2]) == 1  # drive letter
        and resolved_parts[3].lower() == "users"
        # parts[4] = username
        and resolved_parts[5].lower() == "appdata"
    ):
        raise ValueError(
            f"Host path is denied (Windows AppData): {path!r} "
            f"(resolved: {resolved!r})"
        )

    return str(resolved)
