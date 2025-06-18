import os
import hashlib
import base64
from typing import Optional, Dict, ClassVar
from loguru import logger
from pathlib import Path

from autogen_ext.experimental.task_centric_memory import (
    MemoryController,
    MemoryControllerConfig,
    MemoryBankConfig,
)
from autogen_ext.experimental.task_centric_memory.utils import PageLogger
from autogen_core.models import ChatCompletionClient


MEMORY_SUBDIR = "memory_bank"
LOG_SUBDIR = "pagelogs"


class MemoryControllerProvider:
    """Singleton provider for memory controller instances"""

    _instance: ClassVar[Optional["MemoryControllerProvider"]] = None
    _memory_controllers: Dict[str, MemoryController] = {}
    _internal_workspace_root: Optional[Path] = None
    _external_workspace_root: Optional[Path] = None
    _inside_docker: bool = False

    def __new__(
        cls,
        internal_workspace_root: Optional[Path] = None,
        external_workspace_root: Optional[Path] = None,
        inside_docker: bool = False,
    ):
        if cls._instance is None:
            cls._instance = super(MemoryControllerProvider, cls).__new__(cls)
            cls._instance._memory_controllers = {}
            cls._instance._internal_workspace_root = internal_workspace_root
            cls._instance._external_workspace_root = external_workspace_root
            cls._instance._inside_docker = inside_docker
        return cls._instance

    def __init__(
        self,
        internal_workspace_root: Optional[Path] = None,
        external_workspace_root: Optional[Path] = None,
        inside_docker: bool = False,
    ):
        """
        Initialize the memory controller provider with paths

        Args:
            internal_workspace_root (Path, optional): Path to workspace root inside docker
            external_workspace_root (Path, optional): Path to workspace root on host
            inside_docker (bool, optional): Whether code is running inside Docker. Default: False
        """

        if internal_workspace_root is not None:
            self._internal_workspace_root = internal_workspace_root

        if external_workspace_root is not None:
            self._external_workspace_root = external_workspace_root

        self._inside_docker = inside_docker

        root = (
            self._internal_workspace_root
            if self._inside_docker
            else self._external_workspace_root
        )
        if isinstance(root, Path):
            memory_dir = root / MEMORY_SUBDIR
            log_dir = root / LOG_SUBDIR

            memory_dir.mkdir(exist_ok=True, parents=True)
            log_dir.mkdir(exist_ok=True, parents=True)

            try:
                self.validate_path_safety(memory_dir, root)
                self.validate_path_safety(log_dir, root)
            except ValueError as e:
                logger.error(
                    f"Path safety validation failed during initialization: {e}"
                )
                raise ValueError(f"Security violation: {e}")

        else:
            logger.warning("Invalid root path: root must be a Path object")

    @staticmethod
    def get_safe_key(memory_controller_key: str) -> str:
        """Convert a user ID into a filesystem-safe key"""
        hash_obj = hashlib.sha256(memory_controller_key.encode("utf-8"))
        safe_id = (
            base64.urlsafe_b64encode(hash_obj.digest()[:16]).decode("utf-8").rstrip("=")
        )
        return safe_id

    @staticmethod
    def validate_path_safety(path: Path, base_dir: Path) -> bool:
        """
        Validate that a path is within the expected base directory.
        Helps prevent directory traversal attacks.

        Args:
            path (Path): The path to validate
            base_dir (Path): The base directory that should contain the path

        Returns:
            bool: True if path is safe

        Raises:
            ValueError: If the path is outside the base directory
        """
        resolved_path = os.path.realpath(path)
        resolved_base = os.path.realpath(base_dir)

        if not resolved_path.startswith(resolved_base):
            raise ValueError(f"Path validation failed: {path} is outside of {base_dir}")

        return True

    def get_path(self, subdir: str, safe_key: str) -> Optional[Path]:
        """Get path based on current context (Docker or host)"""
        root = (
            self._internal_workspace_root
            if self._inside_docker
            else self._external_workspace_root
        )

        if isinstance(root, Path):
            full_path = root / subdir / safe_key
            full_path.mkdir(exist_ok=True, parents=True)

            try:
                self.validate_path_safety(full_path, root / subdir)
                return full_path
            except ValueError:
                raise ValueError("Invalid memory controller key")

        logger.warning(
            "Memory controller provider root path is not a valid Path object"
        )
        return None

    def get_memory_controller(
        self,
        memory_controller_key: str,
        client: ChatCompletionClient,
        reset: bool = False,
    ) -> MemoryController:
        """Get or create a memory controller for the specified user"""
        safe_key = self.get_safe_key(memory_controller_key)

        if safe_key in self._memory_controllers and not reset:
            return self._memory_controllers[safe_key]

        memory_path = self.get_path(MEMORY_SUBDIR, safe_key)
        log_path = self.get_path(LOG_SUBDIR, safe_key)

        try:
            page_logger = PageLogger(config={"level": "INFO", "path": str(log_path)})

            memory_bank_config = MemoryBankConfig(
                path=str(memory_path),
                relevance_conversion_threshold=float(
                    os.environ.get("MEMORY_RELEVANCE_THRESHOLD", "1.7")
                ),
            )

            memory_controller_config = MemoryControllerConfig(
                generalize_task=False,
                revise_generalized_task=False,
                generate_topics=False,
                validate_memos=True,
                max_memos_to_retrieve=1,
                MemoryBank=memory_bank_config,
            )

            memory_controller = MemoryController(
                reset=reset,
                client=client,
                logger=page_logger,
                config=memory_controller_config,
            )

            self._memory_controllers[safe_key] = memory_controller
            return memory_controller

        except Exception as e:
            logger.error(f"Error creating memory controller: {e}")
            raise

    def close_memory_controller(self, memory_controller_key: str) -> None:
        """Close a memory controller and clean up resources"""
        safe_key = self.get_safe_key(memory_controller_key)
        if safe_key in self._memory_controllers:
            logger.info(f"Closing memory controller (safe key: {safe_key})")
            del self._memory_controllers[safe_key]

    def close_all_memory_controllers(self) -> None:
        """Close all memory controllers"""
        logger.info(
            f"Closing all memory controllers ({len(self._memory_controllers)} total)"
        )
        self._memory_controllers.clear()
