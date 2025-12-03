"""Host-side bash tool — output type and formatting."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..._bash_observers import Annotation
    from ._state import ViewportState


@dataclass
class BashOutput:
    """Result of a bash command execution, optionally carrying harness annotations."""

    stdout: str
    stderr: str
    exit_code: int
    annotations: list[Annotation] = field(default_factory=list["Annotation"])

    def to_output(self, state: ViewportState) -> str:
        output = (self.stdout + self.stderr).rstrip()
        if self.exit_code == 0:
            body = output if output.strip() else "(no output)"
        else:
            body = f"Exit code: {self.exit_code}\n{output}"
        for annotation in self.annotations:
            body = f"{body}\n\n{annotation.text}"
        return body
