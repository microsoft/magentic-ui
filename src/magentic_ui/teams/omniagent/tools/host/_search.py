"""Host-side search tools — search_dir, search_file, find_file.

These run grep/find directly via sandbox.execute() and format output
for the model.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ._state import ViewportState


@dataclass
class SearchDirOutput:
    """Result of search_dir."""

    stdout: str
    stderr: str
    exit_code: int

    def to_output(self, state: ViewportState) -> str:
        output = (self.stdout + self.stderr).rstrip()
        return output if output.strip() else "No matches found."


@dataclass
class SearchFileOutput:
    """Result of search_file."""

    stdout: str
    stderr: str
    exit_code: int

    def to_output(self, state: ViewportState) -> str:
        output = (self.stdout + self.stderr).rstrip()
        return output if output.strip() else "No matches found."


@dataclass
class FindFileOutput:
    """Result of find_file."""

    stdout: str
    stderr: str
    exit_code: int

    def to_output(self, state: ViewportState) -> str:
        output = (self.stdout + self.stderr).rstrip()
        return output if output.strip() else "No matching files found."
