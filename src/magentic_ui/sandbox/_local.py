"""Shared base for sandbox backends that run commands directly on the host."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

from . import SandboxBase

# Path to sandbox requirements (markitdown, etc.)
_SANDBOX_REQUIREMENTS = Path(__file__).parent / "requirements.txt"


class LocalSandboxBase(SandboxBase):
    """Base class for NullSandbox and BubblewrapSandbox.

    Creates a virtual environment under agent_home on __aenter__ for isolated
    Python dependencies. The venv is cached on disk and reused across sessions
    (set reset=True to force a fresh venv).
    """

    def __init__(
        self, agent_home: Path, reset: bool = False, bash_only: bool = False
    ) -> None:
        super().__init__()
        self._agent_home = agent_home
        self._reset = reset
        self._bash_only = bash_only
        self._venv: Path | None = None

    async def __aenter__(self) -> LocalSandboxBase:
        self._venv = self._agent_home / "sandbox" / "venv"
        if self._reset:
            shutil.rmtree(self._venv, ignore_errors=True)
        self._venv.parent.mkdir(parents=True, exist_ok=True)
        if not self._venv.exists():
            subprocess.run(["python3", "-m", "venv", str(self._venv)], check=True)
            if not self._bash_only and _SANDBOX_REQUIREMENTS.exists():
                subprocess.run(
                    [
                        str(self._venv / "bin" / "pip"),
                        "install",
                        "-q",
                        "-r",
                        str(_SANDBOX_REQUIREMENTS),
                    ],
                    check=True,
                )
        return self

    async def __aexit__(self, *args: Any) -> None:
        self._venv = None

    def _activated_env(self, extra: dict[str, str] | None = None) -> dict[str, str]:
        """Return os.environ copy with the temporary venv activated."""
        assert self._venv is not None
        env = os.environ.copy()
        env.pop("PYTHONHOME", None)
        env["VIRTUAL_ENV"] = str(self._venv)
        env["PATH"] = str(self._venv / "bin") + os.pathsep + env.get("PATH", "")
        if extra:
            env.update(extra)
        return env
