"""Sandbox classification helpers shared across OmniAgent internals."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ...sandbox import Sandbox


def is_isolated_sandbox(sandbox: Sandbox | None) -> bool:
    """True iff ``sandbox`` provides isolation from the user's host machine.

    NullSandbox runs commands directly on the host with no isolation.
    Any other sandbox (Quicksand today, future variants) counts as
    isolated.
    """
    if sandbox is None:
        return False
    # Runtime import to avoid a circular dep at module load.
    from ...sandbox._null import NullSandbox

    return not isinstance(sandbox, NullSandbox)
