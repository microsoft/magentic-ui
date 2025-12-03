"""Host-side tool implementations — orchestration, state, formatting."""

from ._output import ToolOutput
from ._state import (
    ViewportState,
    constrain_line,
    format_viewport,
    compute_open_line,
    compute_scroll_down,
    compute_scroll_up,
    increment_scroll,
    reset_scroll,
)
from ._bash import BashOutput
from ._open import OpenOutput
from ._edit import EditOutput
from ._insert import InsertOutput
from ._scroll import ScrollOutput
from ._create import CreateOutput
from ._search import SearchDirOutput, SearchFileOutput, FindFileOutput

__all__ = [
    "ToolOutput",
    "ViewportState",
    "constrain_line",
    "format_viewport",
    "compute_open_line",
    "compute_scroll_down",
    "compute_scroll_up",
    "increment_scroll",
    "reset_scroll",
    "BashOutput",
    "OpenOutput",
    "EditOutput",
    "InsertOutput",
    "ScrollOutput",
    "CreateOutput",
    "SearchDirOutput",
    "SearchFileOutput",
    "FindFileOutput",
]
