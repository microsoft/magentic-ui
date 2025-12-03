"""Tests for QuicksandSandbox session lifecycle.

Verifies create_session()/destroy_session() without booting a real VM.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from magentic_ui.sandbox._quicksand import QuicksandSandbox


def _make_sandbox_with_mock_sb() -> QuicksandSandbox:
    """Build a QuicksandSandbox with a mock VM bypassing __aenter__."""
    sb = QuicksandSandbox()

    mock_result = MagicMock()
    mock_result.exit_code = 0
    mock_result.stdout = ""
    mock_result.stderr = ""

    mock_sb = MagicMock()
    mock_sb.execute = AsyncMock(return_value=mock_result)
    mock_sb.mount = AsyncMock(return_value=MagicMock(name="MountHandle"))
    mock_sb.unmount = AsyncMock(return_value=None)

    sb._sb = mock_sb
    return sb


@pytest.mark.asyncio
async def test_create_session_creates_dirs(tmp_path):
    sb = _make_sandbox_with_mock_sb()
    workspace_host = str(tmp_path / "workspace")

    handles = await sb.create_session(
        session_id="test-123",
        workspace_host_path=workspace_host,
    )

    # mkdir -p should have been called inside VM for the session dirs
    execute_calls = [str(c) for c in sb._sb.execute.call_args_list]
    mkdir_calls = [
        c for c in execute_calls if "mkdir -p" in c and "/sessions/test-123" in c
    ]
    assert len(mkdir_calls) >= 1

    # One mount for workspace (no user dirs)
    assert len(handles) == 1
    assert sb._sb.mount.call_count == 1


@pytest.mark.asyncio
async def test_create_session_mounts_user_dirs(tmp_path):
    sb = _make_sandbox_with_mock_sb()
    workspace_host = str(tmp_path / "workspace")

    downloads = tmp_path / "Downloads"
    photos = tmp_path / "Photos"
    downloads.mkdir()
    photos.mkdir()

    handles = await sb.create_session(
        session_id="test-456",
        workspace_host_path=workspace_host,
        host_dirs=[str(downloads), str(photos)],
    )

    # 1 workspace mount + 2 user dir mounts
    assert len(handles) == 3
    assert sb._sb.mount.call_count == 3

    mount_calls = sb._sb.mount.call_args_list
    # Each mount call uses kwargs (host=, guest=, readonly=)
    assert mount_calls[0].kwargs["guest"] == "/sessions/test-456/workspace"
    assert mount_calls[1].kwargs["guest"] == "/sessions/test-456/mounts/Downloads"
    assert mount_calls[2].kwargs["guest"] == "/sessions/test-456/mounts/Photos"


@pytest.mark.xfail(
    strict=True,
    reason="QuicksandSandbox does not dedupe same-basename host dirs. "
    "Frontend currently allows only one folder mount per session, so "
    "this is dormant; revisit when multi-folder UI lands.",
)
@pytest.mark.asyncio
async def test_create_session_deduplicates_basenames(tmp_path):
    sb = _make_sandbox_with_mock_sb()
    workspace_host = str(tmp_path / "workspace")

    project_a = tmp_path / "a" / "project"
    project_b = tmp_path / "b" / "project"
    project_a.mkdir(parents=True)
    project_b.mkdir(parents=True)

    handles = await sb.create_session(
        session_id="test-dedup",
        workspace_host_path=workspace_host,
        host_dirs=[str(project_a), str(project_b)],
    )

    assert len(handles) == 3
    mount_calls = sb._sb.mount.call_args_list
    assert mount_calls[1].kwargs["guest"] == "/sessions/test-dedup/mounts/project"
    assert mount_calls[2].kwargs["guest"] == "/sessions/test-dedup/mounts/project_2"


@pytest.mark.asyncio
async def test_create_session_rolls_back_on_mount_failure(tmp_path):
    sb = _make_sandbox_with_mock_sb()
    workspace_host = str(tmp_path / "workspace")

    downloads = tmp_path / "Downloads"
    downloads.mkdir()

    mock_handle = MagicMock(name="MountHandle")
    sb._sb.mount.side_effect = [mock_handle, RuntimeError("mount failed")]

    with pytest.raises(RuntimeError, match="mount failed"):
        await sb.create_session(
            session_id="test-rollback",
            workspace_host_path=workspace_host,
            host_dirs=[str(downloads)],
        )

    # The successful workspace mount must be unmounted during rollback.
    assert sb._sb.unmount.call_count == 1


@pytest.mark.asyncio
async def test_create_session_creates_host_workspace_dir(tmp_path):
    from pathlib import Path

    sb = _make_sandbox_with_mock_sb()
    workspace_host = str(tmp_path / "new_dir" / "workspace")

    await sb.create_session(
        session_id="test-789",
        workspace_host_path=workspace_host,
    )

    assert Path(workspace_host).exists()


@pytest.mark.asyncio
async def test_destroy_session_unmounts_all(tmp_path):
    sb = _make_sandbox_with_mock_sb()
    workspace_host = str(tmp_path / "workspace")

    downloads = tmp_path / "Downloads"
    downloads.mkdir()

    handles = await sb.create_session(
        session_id="test-destroy",
        workspace_host_path=workspace_host,
        host_dirs=[str(downloads)],
    )

    await sb.destroy_session(session_id="test-destroy", handles=handles)

    assert sb._sb.unmount.call_count == 2


@pytest.mark.asyncio
async def test_destroy_session_tolerates_errors(tmp_path):
    sb = _make_sandbox_with_mock_sb()
    workspace_host = str(tmp_path / "workspace")

    handles = await sb.create_session(
        session_id="test-err",
        workspace_host_path=workspace_host,
    )

    sb._sb.unmount.side_effect = RuntimeError("unmount failed")

    # Should not raise
    await sb.destroy_session(session_id="test-err", handles=handles)


@pytest.mark.asyncio
async def test_destroy_session_noop_when_not_started():
    sb = QuicksandSandbox()
    # Not entered, no _sb — should be a no-op
    await sb.destroy_session(session_id="none", handles=[MagicMock()])


@pytest.mark.asyncio
async def test_create_session_fails_when_not_started():
    sb = QuicksandSandbox()
    # Asserts self._sb is not None
    with pytest.raises(AssertionError, match="Sandbox not entered"):
        await sb.create_session(
            session_id="fail",
            workspace_host_path="/tmp/ws",
        )
