"""Host-side edit tool — calls guest edit, re-reads file, formats output."""

from __future__ import annotations

from dataclasses import dataclass

from ._state import ViewportState, constrain_line, format_viewport

_SUCCESS_MSG = "File updated."

_LINT_FAIL_MSG = (
    "Your proposed edit has introduced new syntax error(s). "
    "Please read this error message carefully and then retry editing the file."
)

_LINT_REVERT_MSG = (
    "Your changes have NOT been applied. Please fix your edit command and try again.\n"
    "You either need to 1) Specify the correct start/end line arguments or "
    "2) Correct your edit code.\n"
    "DO NOT re-run the same failed edit command. Running it again will lead to "
    "the same error."
)


@dataclass
class EditOutput:
    """Result of editing a file."""

    content: str
    total_lines: int
    error: str | None = None
    # Lint failure fields (populated on revert)
    lint_errors: str | None = None
    edited_content: str | None = None
    original_content: str | None = None
    start_line: int = 0
    end_line: int = 0
    line_count: int = 0

    def to_output(self, state: ViewportState) -> str:
        if self.lint_errors is not None:
            return self._format_lint_failure(state)
        if self.error is not None:
            return self.error
        viewport = format_viewport(state, self.content)
        return f"{viewport}\n{_SUCCESS_MSG}"

    def _format_lint_failure(self, state: ViewportState) -> str:
        """Format lint failure with zoomed before/after viewports."""
        parts: list[str] = [_LINT_FAIL_MSG, "", "ERRORS:", self.lint_errors or "", ""]

        if self.edited_content is not None and state.current_file is not None:
            # Centre the viewport on the edited region.
            #   CURRENT_LINE = (line_count / 2) + start_line  (0-based)
            #   WINDOW       = line_count + 10
            start_0 = self.start_line - 1
            temp = ViewportState(
                current_file=state.current_file,
                current_line=(self.line_count // 2) + start_0,
                window=self.line_count + 10,
            )
            constrain_line(temp, self.edited_content.count("\n") + 1)
            parts.append("This is how your edit would have looked if applied")
            parts.append("-------------------------------------------------")
            parts.append(format_viewport(temp, self.edited_content))
            parts.append("-------------------------------------------------")
            parts.append("")

        if self.original_content is not None and state.current_file is not None:
            # Centre the viewport on the original region (start_line 0-based,
            # end_line 1-based).
            #   CURRENT_LINE = ((end_line - start_line + 1) / 2) + start_line
            #   WINDOW       = end_line - start_line + 10
            start_0 = self.start_line - 1
            temp = ViewportState(
                current_file=state.current_file,
                current_line=((self.end_line - start_0 + 1) // 2) + start_0,
                window=self.end_line - start_0 + 10,
            )
            constrain_line(temp, self.original_content.count("\n") + 1)
            parts.append("This is the original code before your edit")
            parts.append("-------------------------------------------------")
            parts.append(format_viewport(temp, self.original_content))
            parts.append("-------------------------------------------------")

        parts.append(_LINT_REVERT_MSG)
        return "\n".join(parts)
