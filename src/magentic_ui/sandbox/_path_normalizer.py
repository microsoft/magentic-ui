"""Path normalization and validation utilities.

Handles WSL path conversion, session ID validation, and directory
name extraction for cross-platform path handling.
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path


def _is_wsl() -> bool:
    """Detect if running under Windows Subsystem for Linux."""
    try:
        return "microsoft" in Path("/proc/version").read_text().lower()
    except OSError:
        return False


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
