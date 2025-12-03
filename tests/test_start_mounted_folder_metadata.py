from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from magentic_ui.backend.datamodel import RunStatus
from magentic_ui.backend.web.managers.connection import WebSocketManager


async def _empty_stream(**_: Any):
    if False:
        yield None


@pytest.mark.asyncio
async def test_start_message_persists_mounted_folder_metadata() -> None:
    team = MagicMock()
    team.set_uploaded_file_infos = MagicMock()
    team.run_stream = MagicMock(side_effect=lambda **kwargs: _empty_stream(**kwargs))
    team.close = AsyncMock()

    run = MagicMock(id=1, status=RunStatus.CREATED)
    mgr = WebSocketManager.__new__(WebSocketManager)
    mgr._connections = {1: MagicMock()}
    mgr._closed_connections = set()
    mgr._quicksand_manager = None
    mgr._team_managers = {1: team}
    mgr._stream_tasks = {}
    mgr._stopping_runs = set()
    mgr._get_run = AsyncMock(return_value=run)
    mgr._update_run_status = AsyncMock()
    mgr._send_message = AsyncMock()
    mgr._save_message = AsyncMock()
    mgr._run_is_mid_input = AsyncMock(return_value=False)
    mgr.db_manager = MagicMock()

    folder_path = "/home/user/project"

    await mgr._execute_stream(
        1,
        "Inspect this repo",
        settings_config={"mount_dirs": [folder_path]},
    )

    broadcast_payload = mgr._send_message.await_args_list[0].args[1]
    metadata = broadcast_payload["data"]["metadata"]
    assert json.loads(metadata["attached_files"]) == []
    assert metadata["mounted_folder"] == {
        "name": "project",
        "path": folder_path,
    }

    save_payload = mgr._save_message.await_args_list[0].args[1]
    assert save_payload["metadata"]["mounted_folder"] == {
        "name": "project",
        "path": folder_path,
    }

    team.run_stream.assert_called_once()
    assert team.run_stream.call_args.kwargs["mount_dirs"] == [folder_path]
