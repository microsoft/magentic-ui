"""Null (direct host) sandbox — runs commands on the host without isolation."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from . import ExecuteResult, Mount
from ._local import LocalSandboxBase

# Host-side path to the magui guest tools (magui_tools/ + scripts/). With
# no VM to mount into, the agent shell calls them directly from the source
# tree on the host.
_GUEST_TOOLS_HOST_DIR = (
    Path(__file__).parent.parent / "teams" / "omniagent" / "tools" / "guest"
)


class NullSandbox(LocalSandboxBase):
    """Executes commands directly on the host; guest paths are real host paths."""

    def __init__(
        self,
        workspace: Path,
        agent_home: Path | None = None,
        reset: bool = False,
        bash_only: bool = False,
    ) -> None:
        home = agent_home or (workspace / ".agent")
        super().__init__(home, reset=reset, bash_only=bash_only)
        self._workspace = workspace.resolve()
        # Without a VM mount, point the agent shell at the host source dir.
        self.guest_tools_dir: str = str(_GUEST_TOOLS_HOST_DIR.resolve())

    async def __aenter__(self) -> NullSandbox:
        await super().__aenter__()
        # Identity mounts: to_guest_path() returns the real host path.
        self._mounts = [Mount(self._workspace, self._workspace)]
        return self

    async def __aexit__(self, *args: Any) -> None:
        await super().__aexit__(*args)

    async def execute(
        self,
        cmd: str,
        *,
        timeout: int = 60,
        cwd: Path | None = None,
        extra_env: dict[str, str] | None = None,
    ) -> ExecuteResult:
        """Run cmd directly on the host."""
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=cwd,
            env=self._activated_env(extra_env),
        )
        return ExecuteResult(
            stdout=result.stdout,
            stderr=result.stderr,
            exit_code=result.returncode,
        )
