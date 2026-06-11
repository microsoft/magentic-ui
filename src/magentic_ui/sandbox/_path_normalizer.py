"""Path normalization and validation utilities.

Handles WSL path conversion, session ID validation, and directory
name extraction for cross-platform path handling.
"""

from __future__ import annotations

import os
import re
import subprocess
from functools import lru_cache
from pathlib import Path

from loguru import logger


def _is_wsl() -> bool:
    """Detect if running under Windows Subsystem for Linux."""
    try:
        return "microsoft" in Path("/proc/version").read_text().lower()
    except OSError:
        return False


@lru_cache(maxsize=1)
def get_home() -> Path:
    """Return the user's home directory used for the folder picker and
    mount validation.

    On WSL, returns the Windows user profile directory (e.g.
    ``/mnt/c/Users/<name>``) so the picker shows the user's actual
    Windows files. On Linux/macOS, returns ``Path.home().resolve()``.

    Cached so subsequent calls don't re-spawn the WSL probe. Tests that
    need a different home should call ``get_home.cache_clear()`` after
    patching ``Path.home``.
    """
    if _is_wsl():
        try:
            result = subprocess.run(
                ["cmd.exe", "/c", "echo", "%USERPROFILE%"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            win_path = result.stdout.strip().replace("\r", "")
            if win_path and "%" not in win_path:
                wsl_result = subprocess.run(
                    ["wslpath", "-u", win_path],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                wsl_path_str = wsl_result.stdout.strip()
                if wsl_result.returncode == 0 and wsl_path_str:
                    wsl_path = Path(wsl_path_str)
                    if wsl_path.is_dir():
                        logger.info(f"WSL detected, using Windows home: {wsl_path}")
                        return wsl_path.resolve()
        except (OSError, subprocess.TimeoutExpired):
            pass
        logger.warning(
            "WSL detected but failed to resolve Windows home, using Linux home"
        )
    return get_runtime_home()


def get_runtime_home() -> Path:
    """Return the OS home of the current process (``$HOME``).

    This is where a shell expands ``~``/``$HOME``. Under NullSandbox the
    agent's commands run directly on the host, so on WSL this is the
    Linux home (``/home/<user>``) — distinct from ``get_home()``'s
    Windows profile. The credential denylist anchors to both.
    """
    return Path.home().resolve()


def normalize_host_path(path: str) -> str:
    """Convert Windows paths to WSL paths when running under WSL.

    On native Linux/macOS, returns the path unchanged. On WSL, converts
    ``C:\\Users\\foo\\bar`` → ``/mnt/c/Users/foo/bar`` using ``wslpath``
    when available, with a regex fallback for simple drive-letter paths.
    """
    if path.startswith("/"):
        return path  # Already a Unix path

    # Only attempt WSL conversion for Windows-style paths on WSL
    if "\\" not in path and not re.match(r"^[A-Za-z]:", path):
        return path
    if not _is_wsl():
        return path

    # Use wslpath if available (handles UNC, spaces, unicode)
    try:
        result = subprocess.run(
            ["wslpath", "-u", path],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except FileNotFoundError:
        pass

    # Fallback: manual conversion for C:\foo\bar → /mnt/c/foo/bar
    match = re.match(r"^([A-Za-z]):[/\\](.*)$", path)
    if match:
        drive = match.group(1).lower()
        rest = match.group(2).replace("\\", "/")
        return f"/mnt/{drive}/{rest}"

    return path


_SAFE_ID_RE = re.compile(r"^[a-zA-Z0-9_-]+$")
_SAFE_DIR_NAME_RE = re.compile(r"^[\w. -]+$")


def extract_dir_basename(path: str) -> str:
    """Extract the final directory name from a path of any OS style."""
    normalized = path.replace("\\", "/")
    normalized = os.path.normpath(normalized)
    return os.path.basename(normalized)


def validate_session_id(session_id: str) -> None:
    """Reject session IDs containing shell metacharacters."""
    if not _SAFE_ID_RE.fullmatch(session_id):
        raise ValueError(
            f"Invalid session_id (must be alphanumeric/hyphen/underscore): {session_id!r}"
        )


def validate_dir_name(dir_name: str, host_dir: str) -> None:
    """Reject directory basenames that are empty, traversal, or shell-special."""
    if not dir_name:
        raise ValueError(f"Empty directory name derived from host path: {host_dir!r}")
    if dir_name in {".", ".."}:
        raise ValueError(
            f"Disallowed directory name {dir_name!r} (path traversal) from host path: {host_dir!r}"
        )
    if not _SAFE_DIR_NAME_RE.fullmatch(dir_name):
        raise ValueError(
            f"Unsafe directory name {dir_name!r} from host path: {host_dir!r}"
        )
