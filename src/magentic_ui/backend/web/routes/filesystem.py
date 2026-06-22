# api/routes/filesystem.py
"""
Filesystem browsing API for folder selection.

Provides read-only directory listing so the frontend can let users
browse and select folders (full path) without needing a native dialog.
"""

import errno
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from loguru import logger

from magentic_ui.sandbox._path_normalizer import get_home

router = APIRouter()


def _resolve_path(raw_path: str) -> Path:
    """Resolve and validate a filesystem path.

    - Rejects null bytes, empty paths, and non-string input
    - Restricts browsing to user's home directory and below
    - On WSL, home is the Windows user profile directory
    - Verifies the path exists and is a directory

    The implementation avoids passing user input directly into any
    filesystem-accessing API (Path.resolve, os.path.realpath, etc.)
    to satisfy static taint analysis (CodeQL).  Instead it:
      1. Normalises via os.path.normpath (pure string op)
      2. Checks containment via Path.relative_to (pure string op)
      3. Reconstructs the final path from trusted home + clean segments
      4. Resolves symlinks on the trusted path and re-validates
    """
    if not isinstance(raw_path, str) or not raw_path.strip():
        raise HTTPException(status_code=400, detail="Invalid path")

    if "\x00" in raw_path:
        raise HTTPException(status_code=400, detail="Invalid path")

    home = get_home()

    # Pure string normalisation — collapses ".." and "." without I/O
    normed = os.path.normpath(raw_path)

    # Verify containment (pure string comparison, no I/O)
    try:
        rel = Path(normed).relative_to(home)
    except ValueError:
        raise HTTPException(
            status_code=403, detail="Access restricted to home directory"
        )

    # Reject any remaining traversal components in the relative part
    rel_parts = rel.parts
    if ".." in rel_parts:
        raise HTTPException(status_code=400, detail="Invalid path")

    # Build final path from trusted root + validated segments.
    # Using str(home) and joining clean literal parts ensures CodeQL
    # sees no taint propagation from raw_path into filesystem ops.
    safe_path = Path(str(home))
    for part in rel_parts:
        safe_path = safe_path / part

    # Resolve symlinks on the (now trusted) path
    safe_path = safe_path.resolve()

    # Re-validate after resolution in case a symlink escapes home
    try:
        safe_path.relative_to(home)
    except ValueError:
        raise HTTPException(
            status_code=403, detail="Access restricted to home directory"
        )

    if not safe_path.exists():
        raise HTTPException(status_code=404, detail="Path not found")

    if not safe_path.is_dir():
        raise HTTPException(status_code=400, detail="Path is not a directory")

    if not os.access(safe_path, os.R_OK | os.X_OK):
        raise HTTPException(
            status_code=403,
            detail=_permission_denied_detail(safe_path),
        )

    return safe_path


def _permission_denied_detail(path: Path) -> str:
    """Return a user-friendly permission denied message.

    On macOS, protected folders (Documents, Desktop, Downloads, etc.)
    require the host application (e.g. Terminal, VS Code) to have
    Files & Folders or Full Disk Access permission in
    System Settings > Privacy & Security.
    """
    if sys.platform == "darwin":
        # Try to detect macOS TCC restriction (errno 1 = EPERM)
        try:
            os.listdir(path)
        except OSError as e:
            if e.errno == errno.EPERM:
                return (
                    f"macOS blocked access to {path.name}. "
                    "Grant Full Disk Access to your terminal app in "
                    "System Settings > Privacy & Security > Full Disk Access, "
                    "then restart the app."
                )
    return "Permission denied"


def _entry_info(entry: os.DirEntry) -> Optional[Dict]:
    """Extract metadata from a directory entry. Returns None for entries
    that should be skipped (unreadable, special files, or symlinks
    that resolve outside the user's home directory)."""
    name = entry.name

    try:
        # If symlink, verify target stays within home
        if entry.is_symlink():
            target = Path(entry.path).resolve()
            try:
                target.relative_to(get_home())
            except ValueError:
                return None  # Symlink escapes home — hide it

        is_dir = entry.is_dir(follow_symlinks=True)
        is_file = entry.is_file(follow_symlinks=True)
        # Skip special files (sockets, devices, broken symlinks, etc.)
        if not is_dir and not is_file:
            return None

        stat = entry.stat(follow_symlinks=True)
        modified = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()

        info: Dict = {
            "name": name,
            "type": "directory" if is_dir else "file",
            "modified": modified,
        }
        if is_file:
            info["size"] = stat.st_size
        return info
    except (PermissionError, OSError):
        # Skip entries we can't stat
        return None


@router.get("/roots")
async def get_roots() -> Dict:
    """Get the user's home directory path.

    On WSL, returns the Windows user profile directory.
    """
    home = str(get_home())

    return {
        "status": True,
        "data": {
            "home": home,
        },
    }


@router.get("/list")
async def list_directory(
    path: str = Query(..., description="Absolute directory path to list"),
    show_hidden: bool = Query(False, description="Include hidden files/dirs"),
) -> Dict:
    """List contents of a directory."""
    resolved = _resolve_path(path)
    logger.debug(f"Listing directory: {resolved}")

    entries: List[Dict] = []
    try:
        with os.scandir(resolved) as scanner:
            for entry in scanner:
                if not show_hidden and entry.name.startswith("."):
                    continue
                info = _entry_info(entry)
                if info is not None:
                    entries.append(info)
    except PermissionError as e:
        raise HTTPException(
            status_code=403,
            detail=_permission_denied_detail(resolved)
            if getattr(e, "errno", None) == errno.EPERM and sys.platform == "darwin"
            else "Permission denied",
        )
    except OSError as e:
        logger.error(f"Failed to list directory {resolved}: {e}")
        raise HTTPException(status_code=500, detail="Failed to list directory")

    # Sort: directories first, then files, alphabetically within each group
    entries.sort(
        key=lambda e: (0 if e["type"] == "directory" else 1, e["name"].lower())
    )

    # Compute parent path (only if still within home)
    home = get_home()
    parent_path = resolved.parent
    if parent_path != resolved:
        try:
            parent_path.relative_to(home)
            parent = str(parent_path)
        except ValueError:
            parent = None
    else:
        parent = None

    return {
        "status": True,
        "data": {
            "path": str(resolved),
            "parent": parent,
            "entries": entries,
        },
    }
