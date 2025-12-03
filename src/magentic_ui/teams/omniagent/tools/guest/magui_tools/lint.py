"""Flake8 linting helper for edit/insert tools.

Runs flake8 before and after a file change, filters pre-existing errors,
returns only genuinely new errors introduced by the change.

    flake8 --isolated --select=F821,F822,F831,E111,E112,E113,E999,E902
"""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass

_FLAKE8_ARGS = [
    sys.executable,
    "-m",
    "flake8",
    "--isolated",
    "--select=F821,F822,F831,E111,E112,E113,E999,E902",
]


@dataclass(frozen=True)
class LintError:
    line: int
    col: int
    message: str

    @classmethod
    def parse(cls, raw: str) -> LintError | None:
        """Parse a flake8 output line: 'file:line:col: message'."""
        parts = raw.split(":", 3)
        if len(parts) < 3:
            return None
        try:
            line = int(parts[1])
            col = int(parts[2]) if len(parts) > 3 else 0
            message = parts[3].strip() if len(parts) > 3 else parts[2].strip()
            return cls(line=line, col=col, message=message)
        except ValueError:
            return None


def run_flake8(file_path: str) -> list[LintError]:
    """Run flake8 on a file, return parsed errors."""
    try:
        result = subprocess.run(
            [*_FLAKE8_ARGS, "--", file_path],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return []  # flake8 not available or timed out — skip linting
    errors: list[LintError] = []
    for line in result.stdout.strip().splitlines():
        err = LintError.parse(line)
        if err is not None:
            errors.append(err)
    return errors


def filter_new_errors(
    before: list[LintError],
    after: list[LintError],
    edit_start: int,
    edit_end: int,
    new_line_count: int,
) -> list[LintError]:
    """Return only errors introduced by the edit.

    Adjusts pre-existing error line numbers to account for lines
    added/removed by the edit, then subtracts them from the new errors.
    """
    lines_delta = new_line_count - (edit_end - edit_start + 1)

    adjusted_before: set[tuple[int, int, str]] = set()
    for err in before:
        if err.line < edit_start:
            adjusted_before.add((err.line, err.col, err.message))
        elif err.line > edit_end:
            adjusted_before.add((err.line + lines_delta, err.col, err.message))
        # Errors inside the edit window are dropped — they may not exist after edit

    new_errors: list[LintError] = []
    for err in after:
        if (err.line, err.col, err.message) not in adjusted_before:
            new_errors.append(err)
    return new_errors


def format_errors(errors: list[LintError]) -> str:
    """Format lint errors for display."""
    return "\n".join(f"- {err.message}" for err in errors)
