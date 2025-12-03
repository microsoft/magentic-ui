"""Path validation for user-uploaded files.

Used by ``TeamManager`` to sanitize raw client-supplied attachment dicts
before they are persisted, broadcast, or registered for change tracking.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from loguru import logger

from ..datamodel.db import Run
from ..utils.utils import get_file_type


def validate_uploaded_files(
    app_dir: Path,
    attached_files: list[dict[str, Any]],
    run: Optional[Run] = None,
) -> list[tuple[dict[str, Any], str, dict[str, Any]]]:
    """Validate raw upload dicts; return ``(info, url_path, safe_ref)`` tuples.

    Paths are constrained to ``run``'s directory when provided, else
    the shared ``files/user`` root. Invalid entries are skipped.
    Display metadata (``name``, extension, file_type) is derived from
    the on-disk basename, not from client-supplied ``name``.
    """
    validated: list[tuple[dict[str, Any], str, dict[str, Any]]] = []

    if run is not None:
        run_suffix = (
            "files",
            "user",
            str(run.user_id or "unknown_user"),
            str(run.session_id or "unknown_session"),
            str(run.id or "unknown_run"),
        )
        allowed_root_path = app_dir.joinpath(*run_suffix)
        scope_label = "run dir"
    else:
        allowed_root_path = app_dir / "files" / "user"
        scope_label = "files/user root"

    try:
        allowed_root = allowed_root_path.resolve(strict=False)
    except OSError:
        logger.warning(
            "Cannot resolve %s for uploaded-file validation; rejecting all entries",
            scope_label,
        )
        return []

    for f in attached_files:
        name = f.get("name")
        rel_path = f.get("path")
        if not isinstance(name, str) or not isinstance(rel_path, str):
            continue

        url_path = rel_path.lstrip("/")
        if ".." in url_path.split("/"):
            logger.warning("Rejecting uploaded file path with traversal: %r", rel_path)
            continue

        full_path = app_dir / url_path
        try:
            resolved = full_path.resolve(strict=False)
        except OSError:
            logger.warning("Cannot resolve uploaded file path: %r", rel_path)
            continue

        if not resolved.is_relative_to(allowed_root):
            logger.warning(
                "Rejecting uploaded file path outside %s: %r",
                scope_label,
                rel_path,
            )
            continue

        display_name = resolved.name
        ext = display_name.rsplit(".", 1)[-1].lower() if "." in display_name else ""
        file_type = get_file_type(display_name)
        try:
            mtime = resolved.stat().st_mtime
        except OSError:
            logger.warning("Skipping uploaded file (cannot stat on disk): %r", rel_path)
            continue
        raw_type = f.get("type", "file")
        safe_type = raw_type if isinstance(raw_type, str) else "file"
        info = {
            "name": display_name,
            "url": "/" + url_path,
            "timestamp": mtime,
            "extension": ext,
            "file_type": file_type,
        }
        safe_ref = {
            "name": display_name,
            "path": url_path,
            "type": safe_type,
            "uploaded": True,
        }
        validated.append((info, url_path, safe_ref))

    return validated
