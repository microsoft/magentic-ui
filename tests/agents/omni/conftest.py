"""Share one sandbox venv across the OmniAgent test suite.

Every ``NullSandbox`` builds a Python venv under its ``agent_home`` and installs
``markitdown[all]`` (``src/magentic_ui/sandbox/requirements.txt``). These tests
use a per-test ``tmp_path`` as both workspace and (by default) ``agent_home``,
so each test rebuilt that heavy venv from scratch. With enough tests, the
per-test venvs piled up in pytest's session temp tree and exhausted the CI
runner disk (``[Errno 28] No space left on device``).

This builds the venv once per session at a shared ``agent_home`` and points
every ``NullSandbox`` at it (unless a test passes its own ``agent_home``). Each
test keeps its own ``tmp_path`` workspace, so file isolation is unchanged — only
the venv is shared.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from magentic_ui.sandbox._local import _SANDBOX_REQUIREMENTS
from magentic_ui.sandbox._null import NullSandbox


@pytest.fixture(scope="session")
def shared_sandbox_agent_home(
    tmp_path_factory: pytest.TempPathFactory,
) -> Path:
    # Anchored under this run's pytest-<N> base dir so pytest's normal
    # "keep last 3 runs" cleanup removes it — no manual teardown.
    shared_home = tmp_path_factory.getbasetemp() / "sandbox_agent_home"
    venv = shared_home / "sandbox" / "venv"

    # Build the full venv once. Use uv (the project's package manager) so we
    # don't depend on the system python3 shipping ensurepip. Tests run serially
    # today; if pytest-xdist is added, guard this build with a cross-process
    # lock and anchor ``shared_home`` at ``getbasetemp().parent`` so workers
    # share it.
    if not venv.exists():
        venv.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["uv", "venv", str(venv)], check=True, capture_output=True)
        subprocess.run(
            [
                "uv",
                "pip",
                "install",
                "-q",
                "--python",
                str(venv / "bin" / "python"),
                "-r",
                str(_SANDBOX_REQUIREMENTS),
            ],
            check=True,
        )
    return shared_home


@pytest.fixture(autouse=True)
def _redirect_null_sandbox_to_shared_venv(
    monkeypatch: pytest.MonkeyPatch,
    shared_sandbox_agent_home: Path,
) -> None:
    # Function-scoped (and confined to this package's conftest) so the redirect
    # is torn down after each test and never leaks onto NullSandbox usage in
    # other test directories. Tests that pass an explicit ``agent_home`` keep
    # it; everything else lands on the shared venv.
    original_init = NullSandbox.__init__

    def patched_init(
        self: NullSandbox,
        workspace: Path,
        agent_home: Path | None = None,
        reset: bool = False,
        bash_only: bool = False,
    ) -> None:
        original_init(
            self,
            workspace,
            agent_home=agent_home
            if agent_home is not None
            else shared_sandbox_agent_home,
            reset=reset,
            bash_only=bash_only,
        )

    monkeypatch.setattr(NullSandbox, "__init__", patched_init)
