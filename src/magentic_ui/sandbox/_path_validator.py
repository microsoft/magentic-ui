"""Host path security validation.

``validate_host_path`` enforces a two-layer policy for sandbox mounts:

1. Containment — the path must live under ``get_home()`` (the same
   root the folder picker uses). Anything outside is rejected before
   any filesystem access.
2. Denylist — credential-bearing subdirectories inside home
   (``~/.ssh``, ``~/.aws``, …) plus the WSL Windows ``AppData`` tree.

The denylist is also consumed by the NullSandbox classifiers
(``find_denied_path_in_command``, ``classify_sensitive_read``), which
have no containment layer. Those callers need to flag absolute system
paths like ``/etc/shadow`` too, so ``_denied_paths`` keeps an absolute
set alongside the home-relative one even though containment makes the
absolute entries unreachable for the mount validator itself.

On WSL there are two distinct home roots: ``get_home()`` (the Windows
profile, where the picker and mounts live) and ``get_runtime_home()``
(the Linux ``$HOME``, where the NullSandbox agent's shell actually
resolves ``~`` and reads files). The home-relative denylist is anchored
to *both* so credential dirs are guarded on whichever side a command
touches; off WSL the two collapse to one root.
"""

from __future__ import annotations

import os
from pathlib import Path

from loguru import logger

from ._path_normalizer import get_home, get_runtime_home


# Sensitive locations relative to the user's home directory (the one
# returned by ``get_home()`` — on WSL this is the Windows user profile,
# so entries like ``.ssh`` end up protecting ``/mnt/c/Users/<u>/.ssh``).
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

# System paths the NullSandbox classifiers must flag (`/etc/shadow`,
# `/proc/self/environ`, …). Unreachable for ``validate_host_path``
# because containment to ``get_home()`` rejects them first.
_DENIED_ABSOLUTE = {
    "/etc",
    "/proc",
    "/sys",
    "/dev",
    "/root",
    "/var/run",
    "/run",
}


def _home_roots() -> list[Path]:
    """Home roots the credential denylist is anchored against.

    On WSL ``get_home()`` is the Windows profile (where the picker and
    mounts live), but under NullSandbox the agent's shell runs on the
    host with the Linux ``$HOME`` (``get_runtime_home()``). Credential
    dirs must be guarded on both sides. Off WSL the two coincide and
    collapse to one root.
    """
    roots = [get_home()]
    runtime = get_runtime_home()
    if runtime not in roots:
        roots.append(runtime)
    return roots


def _denied_paths() -> list[Path]:
    """Build the full denylist (home-relative + absolute system paths)."""
    denied = [
        Path(os.path.realpath(home / rel))
        for home in _home_roots()
        for rel in _DENIED_HOME_RELATIVE
    ]
    denied.extend(Path(os.path.realpath(p)) for p in _DENIED_ABSOLUTE)
    return denied


def is_denied_path(resolved: Path) -> tuple[bool, Path | None]:
    """Check whether an already-resolved path is on the denylist.

    Caller is responsible for ``realpath``-ing first; this avoids the
    TOCTOU window of resolving twice and lets the caller use the same
    resolved value for any downstream filesystem access.

    Returns ``(True, matched_denial)`` if ``resolved`` is or is under any
    denied path; ``(False, None)`` otherwise.
    """
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

    # Expand ``~`` against get_home(); the denylist is anchored to both
    # get_home() and get_runtime_home(), so a credential dir is flagged
    # whichever home the shell would actually resolve ``~`` to.
    home = str(get_home())
    for tok in tokens:
        expanded = expand_tilde_and_home(tok, home)
        if not expanded.startswith("/"):
            continue
        denied, _matched = is_denied_path(Path(expanded).resolve())
        if denied:
            return tok
    return None


def validate_host_path(path: str) -> str:
    """Validate and canonicalize a host path for mounting.

    The flow mirrors ``backend/web/routes/filesystem._resolve_path``
    so the filesystem sinks (``.exists``, ``.is_dir``) receive a path
    built from a trusted root plus string-validated parts, not raw
    user input.

    Steps:

    1. Pure-string normalization (``expanduser`` + ``normpath``).
    2. Containment check via ``Path.relative_to`` — rejects anything
       outside ``get_home()`` without any filesystem access.
    3. Rebuild the path from ``str(home)`` + the validated relative
       parts, then ``Path.resolve`` to follow symlinks on the
       now-trusted path.
    4. Re-validate containment to catch symlink escapes.
    5. Denylist + WSL Windows ``AppData`` block (both target
       sensitive subdirectories *inside* home).
    6. Existence + directory check.

    Returns:
        The resolved (real) absolute path.

    Raises:
        ValueError: If the path escapes home, is denied, doesn't exist,
            or isn't a directory.
    """
    if not path:
        raise ValueError("Host path must not be empty")

    home = get_home()

    # Pure-string normalization — no filesystem access yet. Expand ``~``
    # against get_home() (not os.path.expanduser, which uses the Linux
    # home on WSL and would disagree with the containment root below).
    expanded = expand_tilde_and_home(path, str(home))
    normed = os.path.normpath(expanded)

    # Containment via Path.relative_to (string comparison).
    try:
        rel = Path(normed).relative_to(home)
    except ValueError:
        raise ValueError(
            f"Host path is not under user home: {path!r} (home: {str(home)!r})"
        )

    # Defense in depth: normpath should have collapsed these already.
    if ".." in rel.parts:
        raise ValueError(f"Invalid host path (traversal): {path!r}")

    # Rebuild from trusted root + validated parts. Subsequent FS ops use
    # this value, which CodeQL sees as built from str(home) (a constant)
    # plus checked string segments.
    safe = Path(str(home))
    for part in rel.parts:
        safe = safe / part

    pre_resolve = safe
    safe = safe.resolve()

    # Re-validate after resolve — catches ``~/symlink → /etc`` escapes.
    try:
        safe.relative_to(home)
    except ValueError:
        raise ValueError(
            f"Host path escapes home via symlink: {path!r} (resolved: {str(safe)!r})"
        )

    if safe != pre_resolve:
        logger.warning(
            f"Mount audit: path resolves through symlink: {path!r} → {str(safe)!r}"
        )

    # Denylist catches credential subdirs inside home (~/.ssh, ~/.aws, …).
    sensitive, matched = is_denied_path(safe)
    if sensitive:
        raise ValueError(
            f"Host path is denied (sensitive location): {path!r} "
            f"(resolved: {str(safe)!r}, matched: {str(matched)!r})"
        )

    # WSL Windows AppData block: ``/mnt/<drive>/Users/<user>/AppData/…``.
    # Lives inside ``get_home()`` on WSL, so containment doesn't catch
    # it. Username varies per host, hence the inline parts match rather
    # than a denylist entry.
    safe_parts = safe.parts
    if (
        len(safe_parts) >= 6
        and safe_parts[1] == "mnt"
        and len(safe_parts[2]) == 1  # drive letter
        and safe_parts[3].lower() == "users"
        # safe_parts[4] = username
        and safe_parts[5].lower() == "appdata"
    ):
        raise ValueError(
            f"Host path is denied (Windows AppData): {path!r} "
            f"(resolved: {str(safe)!r})"
        )

    if not safe.exists():
        raise ValueError(
            f"Host path does not exist: {path!r} (resolved: {str(safe)!r})"
        )
    if not safe.is_dir():
        raise ValueError(
            f"Host path is not a directory: {path!r} (resolved: {str(safe)!r})"
        )

    return str(safe)
