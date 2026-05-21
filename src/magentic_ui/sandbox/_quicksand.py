"""Quicksand-backed sandbox implementation.

Manages a single long-lived Quicksand VM. Implements the Sandbox protocol
for command execution, and provides session management (CIFS mounts) for
multi-tenant workspace isolation.
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Any

from loguru import logger
from quicksand import Sandbox as QuicksandVM  # type: ignore[import-untyped]
from quicksand_core import NetworkMode, PortForward  # type: ignore[import-untyped]

from . import ExecuteResult, Mount, SandboxBase
from ._path_normalizer import (
    extract_dir_basename,
    normalize_host_path,
    validate_dir_name,
    validate_session_id,
)
from ._path_validator import validate_host_path

# Image name for the pre-built sandbox image
_SANDBOX_IMAGE = "quicksand-cua"

# Host-side path to the init script (runs on every boot)
_INIT_SCRIPT_DIR = Path(__file__).parent / "resources"

# Host-side path to guest tools (mounted to /usr/local/lib/magui in VM)
_GUEST_TOOLS_DIR = (
    Path(__file__).parent.parent / "teams" / "omniagent" / "tools" / "guest"
)

# Guest-side mount point for the tools package
_GUEST_TOOLS_MOUNT = "/usr/local/lib/magui"


class QuicksandSandbox(SandboxBase):
    """Quicksand VM sandbox — owns VM lifecycle, execute, mounts, sessions.

    Args:
        memory: VM memory (e.g. "4G").
        cpus: Number of virtual CPUs.
        port_forwards: List of (host_port, guest_port) tuples for port forwarding.
    """

    def __init__(
        self,
        *,
        memory: str = "6G",
        cpus: int = 3,
        port_forwards: list[tuple[int, int]] | None = None,
    ) -> None:
        super().__init__()
        self._memory = memory
        self._cpus = cpus
        self._port_forwards: list[Any] = [
            PortForward(host=h, guest=g) for h, g in (port_forwards or [])
        ]
        self._sb: Any = None
        self._mount_task: asyncio.Task[None] | None = None
        # Inside the VM, magui tools live at the mount point.
        self.guest_tools_dir: str = _GUEST_TOOLS_MOUNT

    # ------------------------------------------------------------------
    # Async mount helper (matching harness pattern)
    # ------------------------------------------------------------------

    async def _mount_all(self, hot_mounts: list[tuple[str, str, bool]]) -> None:
        """Mount multiple directories in parallel."""
        await asyncio.gather(
            *[self._sb.mount(src, dst, readonly=ro) for src, dst, ro in hot_mounts]
        )

    # ------------------------------------------------------------------
    # Lifecycle (matching harness pattern)
    # ------------------------------------------------------------------

    async def __aenter__(self) -> QuicksandSandbox:
        logger.info("Starting Quicksand VM...")
        logger.info(
            f"VM config: memory={self._memory}, cpus={self._cpus}, "
            f"port_forwards={len(self._port_forwards)} ports"
        )
        sb = QuicksandVM(  # type: ignore[call-arg]
            image=_SANDBOX_IMAGE,
            memory=self._memory,
            cpus=self._cpus,
            network_mode=NetworkMode.FULL,
            port_forwards=self._port_forwards,
        )
        logger.info("Starting VM...")
        self._sb = await sb.__aenter__()  # type: ignore[union-attr]
        logger.info("VM started successfully")

        # From here on, the VM is running. If any setup step raises,
        # __aenter__ will not trigger __aexit__ on the caller side, so
        # we must explicitly shut down the VM to avoid a leaked qemu.
        try:
            # Disable default systemd services and create the profile dir
            await self._run_init_script()

            # Mount guest tools (shared, read-only, session-independent)
            if _GUEST_TOOLS_DIR.exists():
                await self._sb.mount(  # pyright: ignore[reportUnknownMemberType]
                    host=str(_GUEST_TOOLS_DIR.resolve()),
                    guest=_GUEST_TOOLS_MOUNT,
                    readonly=True,
                )
                self._mounts.append(
                    Mount(
                        host_path=_GUEST_TOOLS_DIR.resolve(),
                        guest_path=Path(_GUEST_TOOLS_MOUNT),
                    )
                )
                logger.info(
                    f"Mounted guest tools: {_GUEST_TOOLS_DIR} → {_GUEST_TOOLS_MOUNT}"
                )
        except BaseException:
            logger.exception("VM setup failed after boot; shutting down VM")
            try:
                await self._sb.__aexit__(None, None, None)  # pyright: ignore[reportUnknownMemberType]
            except Exception as cleanup_err:
                logger.warning(f"VM cleanup after failed setup errored: {cleanup_err}")
            finally:
                self._sb = None
            raise

        return self

    async def _run_init_script(self) -> None:
        """Run init.sh: disable default systemd services and create the
        shared browser-profile directory."""
        logger.info(f"Mounting init script from {_INIT_SCRIPT_DIR.resolve()}")
        init_mount = await self._sb.mount(
            host=str(_INIT_SCRIPT_DIR.resolve()),
            guest="/usr/local/magentic-ui",
            readonly=True,
        )
        try:
            logger.info("Running init.sh...")

            def _log_line(line: str) -> None:
                stripped = line.rstrip()
                if stripped:
                    logger.info(f"  VM | {stripped}")

            result = await self._sb.execute(
                "bash /usr/local/magentic-ui/init.sh",
                300,
                on_stdout=_log_line,
                on_stderr=_log_line,
            )
            if result.exit_code != 0:
                logger.error(
                    f"init.sh failed:\n"
                    f"stdout: {result.stdout[-1000:]}\n"
                    f"stderr: {result.stderr[-1000:]}"
                )
                raise RuntimeError("VM init.sh failed")
        finally:
            logger.info("Unmounting init script")
            await self._sb.unmount(init_mount)

    async def __aexit__(self, *args: Any) -> None:
        if self._sb is not None:
            # Wait for any pending mounts
            if self._mount_task is not None:
                await self._mount_task
                self._mount_task = None

            await self._sb.__aexit__(*args)
            self._sb = None
            logger.info("Quicksand VM stopped")

    # ------------------------------------------------------------------
    # Execute (matching harness pattern)
    # ------------------------------------------------------------------

    async def execute(
        self,
        cmd: str,
        *,
        timeout: int = 60,
        cwd: Path | None = None,
        extra_env: dict[str, str] | None = None,
    ) -> ExecuteResult:
        """Run cmd inside the Quicksand VM."""
        assert self._sb is not None, "Sandbox not entered"

        # Wait for any pending mounts before executing
        if self._mount_task is not None:
            await self._mount_task
            self._mount_task = None

        # Apply extra environment variables
        if extra_env:
            exports = " && ".join(
                f"export {k}={_shell_quote(v)}" for k, v in extra_env.items()
            )
            cmd = f"{exports} && {cmd}"

        # Run command with optional cwd (quicksand 0.9.0 supports cwd natively)
        result = await self._sb.execute(cmd, timeout, cwd=str(cwd) if cwd else None)
        return ExecuteResult(
            stdout=result.stdout,
            stderr=result.stderr,
            exit_code=result.exit_code,
        )

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    async def health_check(self) -> bool:
        """Ping the VM to check if it's alive."""
        if self._sb is None:
            return False
        try:
            result = await self._sb.execute("echo ok")
            return result.exit_code == 0 and "ok" in result.stdout
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Session lifecycle (dynamic CIFS mounts)
    # ------------------------------------------------------------------

    async def create_session(
        self,
        session_id: str,
        workspace_host_path: str,
        host_dirs: list[str] | None = None,
    ) -> list[Any]:
        """Create session directory structure and mount user-selected dirs.

        Mounts are performed in parallel via asyncio.gather.

        Returns:
            List of opaque MountHandle objects for later cleanup via
            :meth:`destroy_session`.
        """
        assert self._sb is not None, "Sandbox not entered"

        validate_session_id(session_id)

        # Create session dirs inside VM
        await self.execute(
            f"mkdir -p /sessions/{session_id}/workspace /sessions/{session_id}/mounts"
        )

        # Build mount list: (host_path, guest_path, readonly)
        workspace_host = (
            Path(normalize_host_path(workspace_host_path)).expanduser().resolve()
        )
        workspace_host.mkdir(parents=True, exist_ok=True)

        mount_specs: list[tuple[str, str, bool]] = [
            (str(workspace_host), f"/sessions/{session_id}/workspace", False),
        ]
        logger.info(
            f"Session {session_id}: mounting workspace "
            f"host={workspace_host} → guest=/sessions/{session_id}/workspace"
        )

        # Add user-selected host dirs
        for host_dir in host_dirs or []:
            normalized = normalize_host_path(host_dir)
            normalized = os.path.expanduser(normalized)
            # validate_host_path canonicalizes via realpath() and raises
            # ValueError if the path doesn't exist, isn't a directory, or
            # matches the sensitive denylist (.ssh, .aws, /etc, WSL AppData).
            normalized = validate_host_path(normalized)
            dir_name = extract_dir_basename(normalized)
            validate_dir_name(dir_name, host_dir)
            guest_path = f"/sessions/{session_id}/mounts/{dir_name}"
            logger.info(
                f"Session {session_id}: mounting user dir "
                f"host={normalized} → guest={guest_path}"
            )
            mount_specs.append((normalized, guest_path, False))

        # Mount all in parallel. Use return_exceptions=True so partial
        # successes can be unmounted in the except branch — otherwise a
        # mid-mount failure would leak any handles that already succeeded.
        handles: list[Any] = []
        try:
            mount_results = await asyncio.gather(
                *[
                    self._sb.mount(host=src, guest=dst, readonly=ro)
                    for src, dst, ro in mount_specs
                ],
                return_exceptions=True,
            )
            first_exc: BaseException | None = None
            for r in mount_results:
                if isinstance(r, BaseException):
                    if first_exc is None:
                        first_exc = r
                else:
                    handles.append(r)
            if first_exc is not None:
                raise first_exc

            # Register mounts for to_guest_path() / to_host_path() translation
            async with self._mounts_lock:
                for src, dst, _ro in mount_specs:
                    self._mounts.append(
                        Mount(host_path=Path(src), guest_path=Path(dst))
                    )

            # Verify mounts
            verify_result = await self.execute(
                f"ls -la /sessions/{session_id}/ && "
                f"ls -la /sessions/{session_id}/mounts/ 2>/dev/null || true"
            )
            logger.debug(
                f"Session {session_id}: VM directory listing:\n{verify_result.stdout}"
            )
        except Exception:
            try:
                await self.destroy_session(session_id, handles)
            except Exception as rollback_err:
                logger.warning(f"Session {session_id}: rollback failed: {rollback_err}")
            raise

        logger.info(
            f"Session {session_id}: created with {len(handles)} mounts "
            f"(workspace + {len(host_dirs or [])} user dirs)"
        )
        return handles

    async def destroy_session(
        self,
        session_id: str,
        handles: list[Any],
    ) -> None:
        """Unmount all CIFS mounts for a session."""
        if self._sb is None:
            return

        for handle in handles:
            try:
                await self._sb.unmount(handle)
            except Exception as e:
                logger.warning(
                    f"Failed to unmount handle for session {session_id}: {e}"
                )

        # Remove session mounts from path translation table
        async with self._mounts_lock:
            session_prefix = f"/sessions/{session_id}/"
            self._mounts = [
                m
                for m in self._mounts
                if not str(m.guest_path).startswith(session_prefix)
            ]

        logger.info(f"Session {session_id}: {len(handles)} mounts removed")


def _shell_quote(s: str) -> str:
    """Quote a string for shell use."""
    import shlex

    return shlex.quote(s)
