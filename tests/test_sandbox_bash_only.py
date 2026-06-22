"""Pin the production behavior of ``bash_only`` on the local sandbox.

``LocalSandboxBase`` installs ``requirements.txt`` (markitdown) into its venv on
``__aenter__`` — unless ``bash_only=True``, which builds a bare venv and skips
the install. This lives at the tests root (not under tests/agents/omni/) so it
builds its own venv via the real production path, rather than the shared session
venv, which always has markitdown.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from magentic_ui.sandbox._null import NullSandbox


@pytest.mark.asyncio
async def test_bash_only_skips_requirements_install(tmp_path: Path) -> None:
    sb = NullSandbox(workspace=tmp_path, bash_only=True)
    await sb.__aenter__()
    try:
        result = await sb.execute("python -c 'import markitdown'")
    finally:
        await sb.__aexit__(None, None, None)

    assert (
        result.exit_code != 0
    ), "bash_only=True must not install markitdown into the sandbox venv"
