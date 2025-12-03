"""Tests for filesystem route path validation."""

from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi import HTTPException

from magentic_ui.backend.web.routes.filesystem import _resolve_path


@pytest.fixture(autouse=True)
def _mock_home(tmp_path: Path):
    """Mock _get_home to return a temp directory for safe testing."""
    # Create some test directories
    (tmp_path / "Documents").mkdir()
    (tmp_path / "Documents" / "project").mkdir()
    (tmp_path / "Desktop").mkdir()

    with patch(
        "magentic_ui.backend.web.routes.filesystem._get_home",
        return_value=tmp_path,
    ):
        yield tmp_path


class TestResolvePath:
    """Tests for _resolve_path — validates and resolves filesystem paths."""

    def test_valid_subdirectory(self, _mock_home: Path):
        result = _resolve_path(str(_mock_home / "Documents"))
        assert result == _mock_home / "Documents"

    def test_nested_subdirectory(self, _mock_home: Path):
        result = _resolve_path(str(_mock_home / "Documents" / "project"))
        assert result == _mock_home / "Documents" / "project"

    def test_home_itself(self, _mock_home: Path):
        result = _resolve_path(str(_mock_home))
        assert result == _mock_home

    def test_rejects_path_traversal(self, _mock_home: Path):
        with pytest.raises(HTTPException) as exc_info:
            _resolve_path(str(_mock_home / ".." / "etc"))
        assert exc_info.value.status_code == 403

    def test_rejects_path_outside_home(self):
        with pytest.raises(HTTPException) as exc_info:
            _resolve_path("/etc/passwd")
        assert exc_info.value.status_code == 403

    def test_rejects_empty_path(self):
        with pytest.raises(HTTPException) as exc_info:
            _resolve_path("")
        assert exc_info.value.status_code == 400

    def test_rejects_null_bytes(self, _mock_home: Path):
        with pytest.raises(HTTPException) as exc_info:
            _resolve_path(str(_mock_home) + "/foo\x00bar")
        assert exc_info.value.status_code == 400

    def test_rejects_nonexistent_path(self, _mock_home: Path):
        with pytest.raises(HTTPException) as exc_info:
            _resolve_path(str(_mock_home / "nonexistent"))
        assert exc_info.value.status_code == 404

    def test_rejects_file_not_directory(self, _mock_home: Path):
        (file := _mock_home / "file.txt").write_text("hello")
        with pytest.raises(HTTPException) as exc_info:
            _resolve_path(str(file))
        assert exc_info.value.status_code == 400

    def test_symlink_within_home(self, _mock_home: Path):
        link = _mock_home / "link_to_docs"
        link.symlink_to(_mock_home / "Documents")
        result = _resolve_path(str(link))
        assert result == _mock_home / "Documents"

    def test_symlink_escaping_home(self, _mock_home: Path, tmp_path_factory):
        outside = tmp_path_factory.mktemp("outside")
        link = _mock_home / "escape"
        link.symlink_to(outside)
        with pytest.raises(HTTPException) as exc_info:
            _resolve_path(str(link))
        assert exc_info.value.status_code == 403
