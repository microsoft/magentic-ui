"""TeamManager for the magentic-ui agent runtime.

Simplified version that:
- Only supports config file (--config), no UI settings merging
- Removes file tracking (TODO: add back for OmniAgent+coder)
- Removes EventLogger (TODO: add telemetry)

Missing features to add later:
- LLM call telemetry
- Run completion signal with usage metrics
- Duration tracking
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from collections.abc import Callable
from typing import (
    TYPE_CHECKING,
    AsyncGenerator,
    Any,
    Optional,
)
from loguru import logger

from ...agents.web_surfer.fara._types import StreamUpdate
from ...types import ApprovalRequest, ContinuationRequest, InputRequest, PauseController

from ...task_team import get_task_team
from ...agents.message_schemas import (
    file_generated_props,
    input_request_props,
    system_props,
)
from ...magentic_ui_config import (
    AgentMode,
    HarnessConfig,
    MagenticUIConfig,
    ModelClientConfigs,
)
from ...sandbox._path_normalizer import extract_dir_basename, normalize_host_path
from ...sandbox._path_validator import validate_host_path
from ..datamodel import Settings
from ..datamodel.db import Run
from ..utils.utils import get_modified_files, ModifiedFileInfo
from ._upload_validation import validate_uploaded_files

if TYPE_CHECKING:
    from ...agents.base import SubAgentProtocol
    from ...teams.omniagent._omni_agent import OmniAgent
    from ..database import DatabaseManager
    from ...tools.playwright.browser.quicksand_browser_manager import (
        QuicksandBrowserManager,
    )


def _file_to_ws(f: ModifiedFileInfo) -> dict[str, Any]:
    """Convert a file dict from get_modified_files() to WebSocket format."""
    return {
        "name": f["name"],
        "url": "/" + f["path"],
        "timestamp": f["timestamp"],
        "extension": f["extension"],
        "file_type": f["type"],
    }


def _detect_changed_files(
    current_files: list[ModifiedFileInfo],
    known_files: dict[str, float],
) -> list[dict[str, Any]]:
    """Detect created/modified files relative to a known baseline.

    Mutates `known_files` in-place to record the latest mtime for each
    detected file so subsequent calls don't re-emit the same change.

    Files matching internal noise (``tmp_code*``, ``supervisord.pid``)
    are skipped. User-uploaded files participate in tracking via their
    real path: they are recorded in `known_files` during the initial
    snapshot, so a "created" emit is suppressed; later modifications by
    agents surface as "modified" (issue #567).
    """
    changed: list[dict[str, Any]] = []
    for f in current_files:
        fpath = f["path"]
        name = f["name"]
        mtime = f["timestamp"]
        if name.startswith("tmp_code") or name == "supervisord.pid":
            continue
        if fpath not in known_files:
            changed.append({**_file_to_ws(f), "action": "created"})
            known_files[fpath] = mtime
        elif known_files[fpath] < mtime:
            changed.append({**_file_to_ws(f), "action": "modified"})
            known_files[fpath] = mtime
    return changed


class TeamManager:
    """Manages agent lifecycle for OmniAgent / FaraWebSurfer.

    Simplified for MVP: config from file only (no UI settings),
    FaraWebSurfer only (no OmniAgent yet), no file tracking.
    """

    def __init__(
        self,
        app_dir: Path,
        config: MagenticUIConfig | None = None,
        quicksand_manager: "QuicksandBrowserManager | None" = None,
        db_manager: "DatabaseManager | None" = None,
    ) -> None:
        self.agent: "SubAgentProtocol | OmniAgent | None" = None
        self.app_dir = app_dir
        self.config = config
        self._quicksand_manager = quicksand_manager
        self._db_manager = db_manager

        # Full WebSocket-shaped info for files the user uploaded for this run
        # (name, url, timestamp, extension, file_type). Surfaced in the
        # end-of-run summary so the frontend can show a "Files you uploaded"
        # section alongside the agent's generated/modified files.
        self._uploaded_file_infos: list[dict[str, Any]] = []

        # Baseline file mtimes for change detection, mutated in place by
        # both agent activity and mid-run uploads.
        self._known_files: dict[str, float] = {}

        # Pause controller shared with agent for pause/resume
        self._pause_controller: PauseController = PauseController()

        # Pending InputRequest respond callback (set when agent yields InputRequest)
        self._pending_respond: Callable[[str], None] | None = None
        # Whether the pending input is an approval (for NL response metadata)
        self._pending_is_approval: bool = False
        # Whether the pending input is a max-rounds continuation prompt.
        self._pending_is_continuation: bool = False

        # Session mount state (quicksand dynamic CIFS mounts)
        self._mount_handles: list[Any] = []
        self._session_id: str | None = None

    def set_uploaded_file_infos(
        self,
        attached_files: list[dict[str, Any]],
        run: Optional[Run] = None,
    ) -> None:
        """Record validated upload metadata for the end-of-run summary.

        REPLACES any previously recorded list. Use
        :py:meth:`add_uploaded_files` for mid-run uploads, which appends
        and also registers paths in the change-detection baseline.
        """
        validated = validate_uploaded_files(self.app_dir, attached_files, run=run)
        self._uploaded_file_infos = [info for info, _url, _safe in validated]

    def add_uploaded_files(
        self,
        attached_files: list[dict[str, Any]],
        run: Optional[Run] = None,
    ) -> list[dict[str, Any]]:
        """Register validated mid-run uploads and return safe refs.

        Appends to ``_uploaded_file_infos`` and registers each path in
        ``_known_files`` so the next change-detection cycle does not emit
        it as ``"created"``. Returns server-validated refs in the
        ``construct_task`` input shape; callers should use these (not
        the raw client payload) when persisting/broadcasting metadata.
        """
        validated = validate_uploaded_files(self.app_dir, attached_files, run=run)
        safe_refs: list[dict[str, Any]] = []
        for info, url_path, safe_ref in validated:
            self._uploaded_file_infos.append(info)
            self._known_files[url_path] = info["timestamp"]
            safe_refs.append(safe_ref)
        return safe_refs

    def prepare_host_run_dir(
        self,
        run: Optional[Run] = None,
    ) -> Path:
        """Prepare and return the host-side run directory.

        Creates the directory on disk. The guest (VM) path is derived
        at runtime via sandbox.to_guest_path().
        """
        if run:
            run_suffix = os.path.join(
                "files",
                "user",
                str(run.user_id or "unknown_user"),
                str(run.session_id or "unknown_session"),
                str(run.id or "unknown_run"),
            )
        else:
            run_suffix = os.path.join(
                "files", "user", "unknown_user", "unknown_session", "unknown_run"
            )

        host_run_dir = self.app_dir / Path(run_suffix)
        logger.info(f"Creating run dir: {host_run_dir}")
        host_run_dir.mkdir(parents=True, exist_ok=True)
        return host_run_dir

    def _read_settings_from_db(self) -> dict[str, Any]:
        """Read the raw config dict from the user's Settings row.

        Returns the full config dict (model_client_configs, agent_mode, etc.)
        or an empty dict on miss / error.
        """
        try:
            from ..web.config import settings as app_settings

            if not self._db_manager:
                return {}

            response = self._db_manager.get(
                Settings, filters={"user_id": app_settings.DEFAULT_USER_ID}
            )
            if not response.status or not response.data:
                return {}

            raw = response.data[0].config
            if not isinstance(raw, dict):
                return {}
            return raw  # pyright: ignore[reportUnknownVariableType]
        except Exception as e:
            logger.warning(f"Failed to read settings from DB: {e}")
            return {}

    @staticmethod
    def _extract_model_configs(raw: dict[str, Any]) -> dict[str, Any]:
        """Pull orchestrator / web_surfer dicts out of a raw settings config."""
        model_configs: dict[str, Any] = raw.get("model_client_configs", {})  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
        if not isinstance(model_configs, dict):
            return {}
        result: dict[str, Any] = {}
        if model_configs.get("orchestrator"):  # pyright: ignore[reportUnknownMemberType]
            result["orchestrator"] = model_configs["orchestrator"]
        if model_configs.get("web_surfer"):  # pyright: ignore[reportUnknownMemberType]
            result["web_surfer"] = model_configs["web_surfer"]
        return result

    @staticmethod
    def _extract_agent_mode(raw: dict[str, Any]) -> AgentMode | None:
        """Pull agent_mode out of a raw settings config; None if unset/invalid."""
        value = raw.get("agent_mode")
        if not value:
            return None
        try:
            return AgentMode(value)
        except ValueError:
            logger.warning(f"Invalid agent_mode in DB: {value!r}")
            return None

    @staticmethod
    def _apply_runtime_max_rounds(
        baseline: HarnessConfig, raw: dict[str, Any]
    ) -> HarnessConfig:
        """Override only ``max_rounds`` from DB on top of the baseline."""
        section_raw = raw.get("harness_config")
        if not isinstance(section_raw, dict):
            return baseline
        section: dict[str, Any] = section_raw  # pyright: ignore[reportUnknownVariableType]
        merged = baseline.model_copy(deep=True)
        for sub_name in ("orchestrator", "web_surfer"):
            sub_raw = section.get(sub_name)
            if not isinstance(sub_raw, dict):
                continue
            sub: dict[str, Any] = sub_raw  # pyright: ignore[reportUnknownVariableType]
            if "max_rounds" not in sub:
                continue
            try:
                value = int(sub["max_rounds"])
            except (TypeError, ValueError):
                logger.warning(
                    f"Invalid {sub_name}.max_rounds in DB ({sub['max_rounds']!r}); ignoring"
                )
                continue
            if value < 1 or value > 1000:
                logger.warning(
                    f"Out-of-range {sub_name}.max_rounds in DB ({value}); ignoring"
                )
                continue
            setattr(getattr(merged, sub_name), "max_rounds", value)
        return merged

    async def _create_agent(
        self,
        host_run_dir: Path,
        run: Optional[Run] = None,
    ) -> "SubAgentProtocol | OmniAgent":
        """Create agent with config from DB.

        When ``run`` is supplied, the resolved ``agent_mode`` is also
        persisted onto the run row so the frontend (and any later
        consumers) can render this run with the correct mode even after
        the user changes Settings.
        """
        try:
            # Single DB read per session — extract both agent_mode and model
            # configs from the same Settings row so UI changes take effect on
            # the next session without restart.
            raw_settings = self._read_settings_from_db()
            agent_mode = (
                self._extract_agent_mode(raw_settings)
                or (self.config.agent_mode if self.config else None)
                or AgentMode.ALL
            )
            db_configs = self._extract_model_configs(raw_settings)
            if db_configs:
                logger.info("Loaded model configs from DB")

            # Persist the resolved agent_mode onto the run row so the
            # frontend can disambiguate "FARA-only final answer vs OmniAgent
            # final answer" even after the user later changes Settings.
            # Best-effort: a write failure must not block agent creation.
            # On failure we revert the in-memory ``run.agent_mode`` so a
            # subsequent caller that re-uses the same ``run`` object can't
            # accidentally resurrect this failed write the next time it
            # upserts the row.
            if run is not None and getattr(run, "id", None) is not None:
                previous_agent_mode = run.agent_mode
                run.agent_mode = agent_mode.value
                try:
                    if self._db_manager is not None:
                        self._db_manager.upsert(run, return_json=False)
                except Exception:
                    run.agent_mode = previous_agent_mode
                    logger.exception(
                        "Failed to persist agent_mode={} on run {}",
                        agent_mode.value,
                        run.id,
                    )

            web_surfer_config = db_configs.get("web_surfer")
            orchestrator_config = db_configs.get("orchestrator")

            # Validate required model configs based on the active agent_mode.
            if agent_mode in (AgentMode.ALL, AgentMode.OMNIAGENT_ONLY) and (
                orchestrator_config is None
            ):
                raise ValueError(
                    "No orchestrator model config found in DB. Complete onboarding first."
                )
            if agent_mode in (AgentMode.ALL, AgentMode.WEBSURFER_ONLY) and (
                web_surfer_config is None
            ):
                raise ValueError(
                    "No web_surfer model config found in DB. Complete onboarding first."
                )

            # Build MagenticUIConfig with minimal settings.
            # ModelClientConfigs allows None for either side; the inactive
            # side is ignored downstream by task_team.
            baseline_harness = (
                self.config.harness_config if self.config else HarnessConfig()
            )
            harness_config = self._apply_runtime_max_rounds(
                baseline_harness, raw_settings
            )
            magentic_ui_config = MagenticUIConfig(
                agent_mode=agent_mode,
                web_surfer_variant=(
                    self.config.web_surfer_variant if self.config else "qwen3_next"
                ),
                harness_config=harness_config,
                model_client_configs=ModelClientConfigs(
                    orchestrator=orchestrator_config,
                    web_surfer=web_surfer_config,
                ),
            )

            self.agent = await get_task_team(
                magentic_ui_config=magentic_ui_config,
                host_run_dir=host_run_dir,
                pause_controller=self._pause_controller,
                quicksand_manager=self._quicksand_manager,
                session_id=self._session_id,
            )

            return self.agent

        except Exception as e:
            logger.error(f"Error creating agent: {e}")
            await self.close()
            raise

    async def run_stream(
        self,
        task: str,
        run: Optional[Run] = None,
        mount_dirs: list[str] | None = None,
    ) -> AsyncGenerator[Any, None]:
        # TODO: Narrow return type to AsyncGenerator[StreamUpdate, None]
        # once OmniAgent yields StreamUpdate (currently yields Any).
        """Stream agent execution results with file tracking.

        Detects new/modified files in the run directory after each agent update
        and yields type:"file" messages for them.

        Args:
            task: User task string.
            run: Database run object (provides session_id, user_id).
            mount_dirs: Host directories to mount into the session
                (quicksand mode only).
        """
        host_run_dir = self.prepare_host_run_dir(run=run)
        logger.info(
            "run_stream: mount_dirs={}, host_run_dir={}", mount_dirs, host_run_dir
        )

        # Create session mounts when using quicksand
        session_id = str(run.session_id) if run and run.session_id else None
        if self._quicksand_manager is not None and session_id:
            self._session_id = session_id
            logger.info(
                "Creating quicksand session: sid={}, workspace_host_path={}, host_dirs={}",
                session_id,
                str(host_run_dir),
                mount_dirs,
            )
            self._mount_handles = await self._quicksand_manager.sandbox.create_session(
                session_id=session_id,
                workspace_host_path=str(host_run_dir),
                host_dirs=mount_dirs,
            )
            logger.info(
                "Quicksand session created: {} mount handles",
                len(self._mount_handles),
            )

        # Augment task with mount context so agents know about available dirs.
        # Path scheme differs by sandbox: Quicksand exposes /sessions/<sid>/...
        # guest paths; NullSandbox has no isolation namespace, so the agent
        # sees real host paths.
        if mount_dirs and session_id:
            if self._quicksand_manager is not None:
                mount_paths = [
                    f"/sessions/{session_id}/mounts/{extract_dir_basename(d)}"
                    for d in mount_dirs
                ]
                workspace_path = f"/sessions/{session_id}/workspace"
            else:
                mount_paths: list[str] = []
                for d in mount_dirs:
                    n = normalize_host_path(d)
                    n = os.path.expanduser(n)
                    # validate_host_path does its own realpath() + denylist; it
                    # raises ValueError for any path outside the allowed set.
                    mount_paths.append(validate_host_path(n))
                workspace_path = os.fspath(host_run_dir.resolve())
            task = self._augment_task_with_mounts(task, mount_paths, workspace_path)
            logger.info("Augmented task with mount context:\n{}", task)

        if self.agent is None:
            logger.info("Creating agent with host_run_dir={}", host_run_dir)
            await self._create_agent(host_run_dir=host_run_dir, run=run)

        if self.agent is None:
            raise RuntimeError("Failed to create agent")

        try:
            # File tracking always uses host-side path (VM paths don't exist on host)
            file_tracking_dir = str(host_run_dir)

            # Snapshot existing files: {path: mtime} — keyed by relative path
            # to correctly track files with the same basename in different subdirs.
            # User-uploaded files are already on disk at this point and will be
            # captured here, so they will NOT trigger a "created" emit later.
            # If an agent modifies them, mtime will exceed this baseline and they
            # will be emitted as "modified" (issue #567).
            initial_files = get_modified_files(
                0, time.time(), source_dir=file_tracking_dir
            )
            self._known_files = {f["path"]: f["timestamp"] for f in initial_files}
            global_new_files: list[dict[str, Any]] = []

            # Stream agent responses (pass plain string — both FaraWebSurfer
            # and OmniAgent handle str input directly)
            async for event in self.agent.run_stream(task=task):
                if isinstance(event, ApprovalRequest):
                    # Approval request — store callback and send with tool metadata
                    self._pending_respond = event.respond
                    self._pending_is_approval = True
                    self._pending_is_continuation = False
                    yield StreamUpdate(
                        additional_properties=dict(
                            system_props("system", "awaiting_input")
                        ),
                    )
                    yield StreamUpdate(
                        additional_properties=dict(
                            input_request_props(
                                "system",
                                event.prompt,
                                input_type="approval",
                                tool=event.tool_name,
                                tool_args=event.tool_args,
                                category=event.category,
                                reason=event.reason,
                            )
                        ),
                    )
                    continue
                elif isinstance(event, ContinuationRequest):
                    # Max-rounds reached — render a Continue/Stop card on the
                    # frontend (input_type="continuation").
                    self._pending_respond = event.respond
                    self._pending_is_approval = False
                    self._pending_is_continuation = True
                    yield StreamUpdate(
                        additional_properties=dict(
                            system_props("system", "awaiting_input")
                        ),
                    )
                    yield StreamUpdate(
                        additional_properties=dict(
                            input_request_props(
                                "system",
                                event.prompt,
                                input_type="continuation",
                            )
                        ),
                    )
                    continue
                elif isinstance(event, InputRequest):
                    # Store callback so provide_input() can resolve the future
                    self._pending_respond = event.respond
                    self._pending_is_approval = False
                    self._pending_is_continuation = False
                    # Frontend expects two messages: system status + input_request
                    yield StreamUpdate(
                        additional_properties=dict(
                            system_props("system", "awaiting_input")
                        ),
                    )
                    yield StreamUpdate(
                        additional_properties=dict(
                            input_request_props("system", event.prompt)
                        ),
                    )
                    continue
                yield event

                # Detect new/modified files
                current_files = get_modified_files(
                    0, time.time(), source_dir=file_tracking_dir
                )
                changed_files = _detect_changed_files(current_files, self._known_files)

                if changed_files:
                    global_new_files.extend(changed_files)
                    yield StreamUpdate(
                        text="File Generated",
                        additional_properties=dict(
                            file_generated_props("system", changed_files)
                        ),
                    )

            # Final aggregated file message (deduplicated by url, keep latest).
            # Marked summary=True so the frontend renders it under a
            # "Files the agent created or modified" header at the end of
            # the run. Uploaded files (if any) are passed through too so the
            # frontend can show a separate "Files you uploaded" section
            # for overview.
            if global_new_files or self._uploaded_file_infos:
                deduped = list({f["url"]: f for f in global_new_files}.values())
                yield StreamUpdate(
                    text="File Generated",
                    additional_properties=dict(
                        file_generated_props(
                            "system",
                            deduped,
                            summary=True,
                            uploaded_files=self._uploaded_file_infos or None,
                        )
                    ),
                )

        finally:
            # Per-task: unmount only. Agent/browser kept alive
            if self._mount_handles and self._quicksand_manager and self._session_id:
                try:
                    await self._quicksand_manager.sandbox.destroy_session(
                        session_id=self._session_id,
                        handles=self._mount_handles,
                    )
                except Exception:
                    logger.exception(f"Failed to destroy session {self._session_id}")
                finally:
                    self._mount_handles = []
                    self._session_id = None

    async def close(self) -> None:
        """Close the agent and cleanup resources."""
        # Unmount CIFS mounts before closing agents
        if self._mount_handles and self._quicksand_manager and self._session_id:
            try:
                await self._quicksand_manager.sandbox.destroy_session(
                    session_id=self._session_id,
                    handles=self._mount_handles,
                )
            except Exception:
                logger.exception(f"Failed to destroy session {self._session_id}")
            finally:
                self._mount_handles = []
                self._session_id = None

        if self.agent is not None:
            # FaraWebSurfer.close() handles browser cleanup
            if hasattr(self.agent, "close"):
                await self.agent.close()  # type: ignore[union-attr]
            self.agent = None
            logger.info("Agent closed")

    # =========================================================================
    # Session mount helpers
    # =========================================================================

    @staticmethod
    def _augment_task_with_mounts(
        task: str, mount_paths: list[str], workspace_path: str
    ) -> str:
        """Append mount directory context to the task message."""
        mount_lines = "\n".join(f"- {p}" for p in mount_paths)
        return (
            f"{task}\n\n"
            f"User has shared the following directories. "
            f"Use these absolute paths when referring to them:\n"
            f"{mount_lines}\n\n"
            f"Your workspace: {workspace_path}"
        )

    # =========================================================================
    # Pause/Resume methods
    # =========================================================================

    async def pause_run(self) -> None:
        """Pause the agent. Agent will check is_paused and yield InputRequest."""
        self._pause_controller.pause()
        logger.info("TeamManager: Agent paused")

    async def resume_run(self) -> None:
        """Resume without input (e.g., frontend button)."""
        self._pause_controller.resume()
        logger.info("TeamManager: Agent resumed")

    def cancel_input(self) -> None:
        """Cancel any pending input wait. Used during stop_run()."""
        self._pause_controller.cancel()

    def provide_input(self, response: str) -> None:
        """Resolve the pending InputRequest future, unblocking the agent."""
        self._pause_controller.resume()
        if self._pending_respond is not None:
            self._pending_respond(response)
            self._pending_respond = None
            self._pending_is_approval = False
            self._pending_is_continuation = False
        logger.info(f"TeamManager: Input provided ({len(response)} chars)")

    def queue_user_message(self, message: str) -> None:
        """Queue a mid-run user message for the agent to drain at its next checkpoint."""
        self._pause_controller.queue_message(message)
        logger.info(f"TeamManager: User message queued ({len(message)} chars)")

    @property
    def has_pending_input(self) -> bool:
        """Whether the agent is currently waiting on an InputRequest."""
        return self._pending_respond is not None

    @property
    def has_pending_approval(self) -> bool:
        """Whether the pending input request is an approval (not a text input)."""
        return self._pending_is_approval

    @property
    def has_pending_continuation(self) -> bool:
        """Whether the pending input request is a max-rounds continuation prompt."""
        return self._pending_is_continuation
