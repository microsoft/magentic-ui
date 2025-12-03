"""Sandbox protocol, base class, shared types, and backend factory."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol


@dataclass
class ExecuteResult:
    """Result of a sandbox command execution."""

    stdout: str
    stderr: str
    exit_code: int


@dataclass
class Mount:
    """A host-to-guest path mapping."""

    host_path: Path
    guest_path: Path


class Sandbox(Protocol):
    """Protocol for sandbox backends."""

    # Path the agent's shell uses to locate the magui guest tools
    # (magui_tools/ package + scripts/search.sh). Each backend sets this
    # to whatever resolves correctly inside that backend's execution env:
    # QuicksandSandbox uses the in-VM mount point; NullSandbox uses the
    # host source directory directly.
    guest_tools_dir: str

    async def __aenter__(self) -> Sandbox:
        """Enter the sandbox context."""
        ...

    async def __aexit__(self, *args: Any) -> None:
        """Exit the sandbox context."""
        ...

    async def execute(
        self,
        cmd: str,
        *,
        timeout: int = 60,
        cwd: Path | None = None,
        extra_env: dict[str, str] | None = None,
    ) -> ExecuteResult:
        """Execute a command inside the sandbox."""
        ...

    def to_guest_path(self, host_path: Path) -> Path:
        """Translate a host path to the corresponding guest path."""
        ...

    def to_host_path(self, guest_path: Path) -> Path:
        """Translate a guest path to the corresponding host path."""
        ...


class SandboxBase:
    """Base class providing path-mapping; subclasses populate _mounts in __aenter__."""

    def __init__(self) -> None:
        """Initialize with an empty mount list."""
        self._mounts: list[Mount] = []
        self._mounts_lock = asyncio.Lock()

    async def __aenter__(self) -> SandboxBase:
        """Enter the sandbox context."""
        return self

    async def __aexit__(self, *args: Any) -> None:
        """Exit the sandbox context."""
        pass

    def to_guest_path(self, host_path: Path) -> Path:
        """Translate a host path to the corresponding guest path."""
        host_path = Path(host_path).resolve()
        for m in sorted(
            self._mounts, key=lambda m: len(m.host_path.parts), reverse=True
        ):
            try:
                return m.guest_path / host_path.relative_to(m.host_path)
            except ValueError:
                continue
        raise ValueError(f"No mount covers host path: {host_path}")

    def to_host_path(self, guest_path: Path) -> Path:
        """Translate a guest path to the corresponding host path."""
        guest_path = Path(guest_path)
        for m in sorted(
            self._mounts, key=lambda m: len(m.guest_path.parts), reverse=True
        ):
            try:
                return m.host_path / guest_path.relative_to(m.guest_path)
            except ValueError:
                continue
        raise ValueError(f"No mount covers guest path: {guest_path}")
