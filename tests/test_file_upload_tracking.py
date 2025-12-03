"""Tests for file upload and generated file tracking.

Covers:
- sanitize_filename: path traversal prevention
- construct_task: task string augmentation with file references
- get_modified_files: timestamp field in returned dicts
- _file_to_ws: file dict conversion to WebSocket format
- file_generated_props: message schema factory
- _detect_changed_files: created/modified detection (incl. issue #567)
"""

from __future__ import annotations

import json
import os
import tempfile
import time

import pytest

from magentic_ui.backend.utils.utils import (
    ModifiedFileInfo,
    construct_task,
    find_available_filename,
    get_modified_files,
    sanitize_filename,
)
from magentic_ui.agents.message_schemas import (
    file_generated_props,
)
from magentic_ui.backend.teammanager.teammanager import (
    _detect_changed_files,
    _file_to_ws,
)


# =============================================================================
# sanitize_filename
# =============================================================================


class TestSanitizeFilename:
    def test_simple_filename(self) -> None:
        assert sanitize_filename("report.csv") == "report.csv"

    def test_strips_directory_components(self) -> None:
        assert sanitize_filename("../../etc/passwd") == "passwd"

    def test_strips_absolute_path(self) -> None:
        assert sanitize_filename("/etc/shadow") == "shadow"

    def test_rejects_empty(self) -> None:
        with pytest.raises(ValueError):
            sanitize_filename("")

    def test_rejects_dot(self) -> None:
        with pytest.raises(ValueError):
            sanitize_filename(".")

    def test_rejects_dotdot(self) -> None:
        with pytest.raises(ValueError):
            sanitize_filename("..")

    def test_rejects_hidden_file(self) -> None:
        with pytest.raises(ValueError):
            sanitize_filename(".env")

    def test_rejects_hidden_after_strip(self) -> None:
        with pytest.raises(ValueError):
            sanitize_filename("/some/path/.secret")

    def test_nested_forward_slash_path(self) -> None:
        # os.path.basename strips forward-slash directory components
        result = sanitize_filename("dir/subdir/report.csv")
        assert result == "report.csv"

    def test_filename_with_spaces(self) -> None:
        assert sanitize_filename("my report.csv") == "my report.csv"

    def test_filename_with_special_chars(self) -> None:
        assert sanitize_filename("data (1).xlsx") == "data (1).xlsx"

    def test_windows_backslash_path(self) -> None:
        # Browsers may send Windows-style paths (e.g., C:\fakepath\file.txt)
        result = sanitize_filename(r"C:\fakepath\report.csv")
        assert result == "report.csv"

    def test_windows_backslash_traversal(self) -> None:
        result = sanitize_filename(r"..\..\etc\passwd")
        assert result == "passwd"

    def test_mixed_separators(self) -> None:
        result = sanitize_filename(r"dir/subdir\file.txt")
        assert result == "file.txt"


# =============================================================================
# find_available_filename
# =============================================================================


class TestFindAvailableFilename:
    def test_returns_unchanged_when_no_collision(self, tmp_path) -> None:
        assert find_available_filename(tmp_path, "report.txt") == "report.txt"

    def test_appends_suffix_on_disk_collision(self, tmp_path) -> None:
        (tmp_path / "report.txt").write_text("existing")
        assert find_available_filename(tmp_path, "report.txt") == "report_1.txt"

    def test_increments_suffix_until_free(self, tmp_path) -> None:
        (tmp_path / "report.txt").write_text("a")
        (tmp_path / "report_1.txt").write_text("b")
        (tmp_path / "report_2.txt").write_text("c")
        assert find_available_filename(tmp_path, "report.txt") == "report_3.txt"

    def test_handles_filename_without_extension(self, tmp_path) -> None:
        (tmp_path / "README").write_text("a")
        assert find_available_filename(tmp_path, "README") == "README_1"

    def test_preserves_compound_extension_stem(self, tmp_path) -> None:
        # Matches Path.suffix behavior: only the final extension is preserved.
        (tmp_path / "archive.tar.gz").write_text("a")
        assert find_available_filename(tmp_path, "archive.tar.gz") == "archive.tar_1.gz"

    def test_avoids_reserved_names_within_batch(self, tmp_path) -> None:
        # Simulates a single multi-file upload: the first file has been
        # accepted (added to ``reserved``) but not yet written to disk.
        first = find_available_filename(tmp_path, "report.txt", reserved=[])
        assert first == "report.txt"
        second = find_available_filename(tmp_path, "report.txt", reserved=[first])
        assert second == "report_1.txt"
        third = find_available_filename(
            tmp_path, "report.txt", reserved=[first, second]
        )
        assert third == "report_2.txt"

    def test_reserved_combines_with_disk(self, tmp_path) -> None:
        (tmp_path / "report.txt").write_text("on-disk")
        # report_1.txt is already claimed earlier in the same batch.
        result = find_available_filename(
            tmp_path, "report.txt", reserved=["report_1.txt"]
        )
        assert result == "report_2.txt"


# =============================================================================
# construct_task
# =============================================================================


class TestConstructTask:
    def test_no_files(self) -> None:
        result = construct_task("Do something")
        assert result["agent_task"] == "Do something"
        assert result["attached_files"] == []
        assert json.loads(result["attached_files_json"]) == []

    def test_none_files(self) -> None:
        result = construct_task("Do something", files=None)
        assert result["agent_task"] == "Do something"
        assert result["attached_files"] == []
        assert json.loads(result["attached_files_json"]) == []

    def test_empty_files(self) -> None:
        result = construct_task("Do something", files=[])
        assert result["agent_task"] == "Do something"
        assert result["attached_files"] == []
        assert json.loads(result["attached_files_json"]) == []

    def test_uploaded_file_appended(self) -> None:
        files = [{"name": "data.csv", "path": "/workspace/data.csv", "uploaded": True}]
        result = construct_task("Analyze this", files=files)
        assert "Attached file: data.csv" in result["agent_task"]
        assert "Analyze this" in result["agent_task"]
        assert [f["name"] for f in result["attached_files"]] == ["data.csv"]
        attached = json.loads(result["attached_files_json"])
        assert len(attached) == 1
        assert attached[0]["name"] == "data.csv"
        assert attached[0]["uploaded"] is True

    def test_multiple_uploaded_files(self) -> None:
        files = [
            {"name": "a.csv", "path": "/workspace/a.csv", "uploaded": True},
            {"name": "b.txt", "path": "/workspace/b.txt", "uploaded": True},
        ]
        result = construct_task("Process files", files=files)
        assert "Attached file: a.csv" in result["agent_task"]
        assert "Attached file: b.txt" in result["agent_task"]
        assert {f["name"] for f in result["attached_files"]} == {"a.csv", "b.txt"}
        attached = json.loads(result["attached_files_json"])
        assert len(attached) == 2

    def test_non_uploaded_file_ignored(self) -> None:
        files = [{"name": "inline.txt", "content": "abc"}]
        result = construct_task("Read this", files=files)
        assert result["agent_task"] == "Read this"
        assert result["attached_files"] == []
        assert json.loads(result["attached_files_json"]) == []

    def test_uploaded_without_path_ignored(self) -> None:
        files = [{"name": "orphan.csv", "uploaded": True}]
        result = construct_task("Check", files=files)
        assert result["agent_task"] == "Check"
        assert result["attached_files"] == []

    def test_path_traversal_sanitized_to_basename(self) -> None:
        """../../etc/passwd is sanitized to 'passwd' (valid basename), both files appear."""
        files = [
            {"name": "../../etc/passwd", "path": "/evil", "uploaded": True},
            {"name": "good.csv", "path": "/workspace/good.csv", "uploaded": True},
        ]
        result = construct_task("Do work", files=files)
        assert "Attached file: passwd" in result["agent_task"]
        assert "Attached file: good.csv" in result["agent_task"]
        assert {f["name"] for f in result["attached_files"]} == {"passwd", "good.csv"}

    def test_hidden_filename_skipped(self) -> None:
        files = [
            {"name": ".env", "path": "/workspace/.env", "uploaded": True},
            {"name": "ok.txt", "path": "/workspace/ok.txt", "uploaded": True},
        ]
        result = construct_task("Do work", files=files)
        assert ".env" not in result["agent_task"]
        assert "ok.txt" in result["agent_task"]
        assert {f["name"] for f in result["attached_files"]} == {"ok.txt"}

    def test_attached_files_json_has_path_and_type(self) -> None:
        """Verify attached_files_json includes path and type fields."""
        files = [
            {
                "name": "report.pdf",
                "path": "/workspace/report.pdf",
                "type": "application/pdf",
                "uploaded": True,
            }
        ]
        result = construct_task("Summarize", files=files)
        attached = json.loads(result["attached_files_json"])
        assert len(attached) == 1
        assert attached[0]["name"] == "report.pdf"
        assert attached[0]["type"] == "application/pdf"
        assert attached[0]["path"] == "/workspace/report.pdf"
        assert attached[0]["uploaded"] is True

    def test_non_string_name_uses_fallback(self) -> None:
        """Non-string name (e.g., int/None) should fall back to 'unknown.file' without crashing."""
        files = [
            {"name": 12345, "path": "/workspace/12345", "uploaded": True},
            {"name": None, "path": "/workspace/null", "uploaded": True},
            {"name": "good.csv", "path": "/workspace/good.csv", "uploaded": True},
        ]
        result = construct_task("Process", files=files)
        # Non-string names get sanitized to "unknown.file" and still attached
        assert "good.csv" in result["agent_task"]
        assert "good.csv" in {f["name"] for f in result["attached_files"]}


# =============================================================================
# get_modified_files — timestamp field
# =============================================================================


class TestGetModifiedFiles:
    def test_returns_timestamp_field(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a test file
            filepath = os.path.join(tmpdir, "test.txt")
            with open(filepath, "w") as f:
                f.write("hello")

            mtime = os.path.getmtime(filepath)
            results = get_modified_files(0, time.time() + 1, source_dir=tmpdir)

            assert len(results) == 1
            assert results[0]["name"] == "test.txt"
            assert "timestamp" in results[0]
            assert results[0]["timestamp"] == mtime

    def test_timestamp_is_float(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, "data.csv")
            with open(filepath, "w") as f:
                f.write("a,b,c")

            results = get_modified_files(0, time.time() + 1, source_dir=tmpdir)
            assert isinstance(results[0]["timestamp"], float)

    def test_ignores_pyc_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, "module.pyc"), "w") as f:
                f.write("")
            with open(os.path.join(tmpdir, "script.py"), "w") as f:
                f.write("pass")

            results = get_modified_files(0, time.time() + 1, source_dir=tmpdir)
            names = [r["name"] for r in results]
            assert "script.py" in names
            assert "module.pyc" not in names

    def test_file_type_detection(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            for name in ["data.csv", "image.png", "doc.pdf", "code.py"]:
                with open(os.path.join(tmpdir, name), "w") as f:
                    f.write("")

            results = get_modified_files(0, time.time() + 1, source_dir=tmpdir)
            type_map = {r["name"]: r["type"] for r in results}
            assert type_map["data.csv"] == "csv"
            assert type_map["image.png"] == "image"
            assert type_map["doc.pdf"] == "pdf"
            assert type_map["code.py"] == "code"

    def test_empty_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            results = get_modified_files(0, time.time() + 1, source_dir=tmpdir)
            assert results == []


# =============================================================================
# _file_to_ws
# =============================================================================


class TestFileToWs:
    def test_converts_fields(self) -> None:
        f: ModifiedFileInfo = {
            "name": "report.csv",
            "path": "files/user/uid/sid/rid/report.csv",
            "short_path": "files/user/uid/sid/rid/report.csv",
            "timestamp": 1709561234.567,
            "extension": "csv",
            "type": "csv",
        }
        result = _file_to_ws(f)
        assert result == {
            "name": "report.csv",
            "url": "/files/user/uid/sid/rid/report.csv",
            "timestamp": 1709561234.567,
            "extension": "csv",
            "file_type": "csv",
        }

    def test_url_has_leading_slash(self) -> None:
        f: ModifiedFileInfo = {
            "name": "x.txt",
            "path": "files/user/a/b/c/x.txt",
            "short_path": "files/user/a/b/c/x.txt",
            "timestamp": 0.0,
            "extension": "txt",
            "type": "code",
        }
        result = _file_to_ws(f)
        assert result["url"].startswith("/")

    def test_type_renamed_to_file_type(self) -> None:
        """Verify 'type' → 'file_type' rename to avoid collision with WS message type."""
        f: ModifiedFileInfo = {
            "name": "a.py",
            "path": "files/user/u/s/r/a.py",
            "short_path": "files/user/u/s/r/a.py",
            "timestamp": 1.0,
            "extension": "py",
            "type": "code",
        }
        result = _file_to_ws(f)
        assert "file_type" in result
        assert "type" not in result


# =============================================================================
# file_generated_props
# =============================================================================


class TestFileGeneratedProps:
    def test_structure(self) -> None:
        files = [{"name": "a.csv", "url": "/files/a.csv", "action": "created"}]
        props = file_generated_props("system", files)
        assert props["source"] == "system"
        assert props["type"] == "file"
        assert json.loads(props["files"]) == files

    def test_files_is_json_string(self) -> None:
        props = file_generated_props("system", [])
        assert isinstance(props["files"], str)
        assert json.loads(props["files"]) == []

    def test_multiple_files(self) -> None:
        files = [
            {"name": "a.csv", "action": "created"},
            {"name": "b.csv", "action": "modified"},
        ]
        props = file_generated_props("system", files)
        parsed = json.loads(props["files"])
        assert len(parsed) == 2
        assert parsed[0]["action"] == "created"
        assert parsed[1]["action"] == "modified"

    def test_dict_conversion_for_mutable_mapping(self) -> None:
        """Verify dict() conversion works."""
        props = file_generated_props("system", [])
        as_dict = dict(props)
        assert isinstance(as_dict, dict)
        assert as_dict["type"] == "file"

    def test_summary_omitted_by_default(self) -> None:
        """Per-step file emits should NOT carry the summary flag."""
        props = file_generated_props("system", [{"name": "x.csv"}])
        assert "summary" not in props

    def test_summary_set_when_flag_true(self) -> None:
        """End-of-run aggregated emit must set summary=True so the frontend
        renders the 'Files created or modified' header."""
        props = file_generated_props("system", [{"name": "x.csv"}], summary=True)
        assert props.get("summary") is True

    def test_summary_omitted_when_flag_false(self) -> None:
        """summary=False must omit the field (treated identically to default)."""
        props = file_generated_props("system", [{"name": "x.csv"}], summary=False)
        assert "summary" not in props

    def test_uploaded_files_omitted_by_default(self) -> None:
        """Per-step emits must not carry uploaded_files."""
        props = file_generated_props("system", [{"name": "x.csv"}])
        assert "uploaded_files" not in props

    def test_uploaded_files_serialized_on_summary(self) -> None:
        """Summary must serialize uploaded files as JSON for the frontend."""
        uploaded = [
            {
                "name": "input.csv",
                "url": "/files/user/u/s/r/input.csv",
                "timestamp": 1.0,
                "extension": "csv",
                "file_type": "csv",
            }
        ]
        props = file_generated_props(
            "system", [{"name": "out.md"}], summary=True, uploaded_files=uploaded
        )
        assert props.get("summary") is True
        assert isinstance(props.get("uploaded_files"), str)
        assert json.loads(props["uploaded_files"]) == uploaded

    def test_empty_uploaded_files_omitted(self) -> None:
        """An empty uploaded_files list must not produce the field."""
        props = file_generated_props(
            "system", [{"name": "out.md"}], summary=True, uploaded_files=[]
        )
        assert "uploaded_files" not in props


# =============================================================================
# _detect_changed_files — file change detection algorithm (issue #567)
# =============================================================================


def _make_file(path: str, mtime: float, name: str | None = None) -> ModifiedFileInfo:
    """Helper to build a ModifiedFileInfo for tests."""
    base = name or os.path.basename(path)
    ext = base.rsplit(".", 1)[-1] if "." in base else ""
    return {
        "name": base,
        "path": path,
        "short_path": path,
        "timestamp": mtime,
        "extension": ext,
        "type": "code",
    }


class TestDetectChangedFiles:
    def test_new_file_emitted_as_created(self) -> None:
        known: dict[str, float] = {}
        current = [_make_file("files/user/u/s/r/report.md", 100.0)]
        changed = _detect_changed_files(current, known)

        assert len(changed) == 1
        assert changed[0]["action"] == "created"
        assert changed[0]["name"] == "report.md"
        # known_files updated so a second pass with same mtime is a no-op
        assert known["files/user/u/s/r/report.md"] == 100.0

    def test_unchanged_file_not_emitted(self) -> None:
        known = {"files/user/u/s/r/data.csv": 100.0}
        current = [_make_file("files/user/u/s/r/data.csv", 100.0)]
        changed = _detect_changed_files(current, known)
        assert changed == []

    def test_modified_file_emitted(self) -> None:
        known = {"files/user/u/s/r/data.csv": 100.0}
        current = [_make_file("files/user/u/s/r/data.csv", 200.0)]
        changed = _detect_changed_files(current, known)

        assert len(changed) == 1
        assert changed[0]["action"] == "modified"
        assert changed[0]["name"] == "data.csv"
        assert known["files/user/u/s/r/data.csv"] == 200.0

    def test_uploaded_file_unchanged_not_emitted(self) -> None:
        """Issue #567: a user-uploaded file present in the initial baseline
        must NOT be re-emitted as 'created' when no agent has modified it.

        The baseline is built from the on-disk snapshot taken right after
        upload, so the file's real path+mtime is already in known_files.
        """
        # Initial snapshot taken right after the user uploaded data.csv
        known: dict[str, float] = {"files/user/u/s/r/data.csv": 100.0}

        # Agent runs but never modifies the uploaded file; mtime unchanged
        current = [_make_file("files/user/u/s/r/data.csv", 100.0)]

        changed = _detect_changed_files(current, known)
        assert changed == []

    def test_uploaded_file_modified_by_agent_is_emitted(self) -> None:
        """Issue #567: when an agent modifies a user-uploaded file, the
        change MUST surface as a 'modified' file message so the user can
        download / re-open the updated file.

        Previously this was suppressed by an unconditional basename-based
        skip (`if name in self.uploaded_files: continue`), leaving the user
        with no visibility into edits.
        """
        # Initial snapshot taken right after upload
        known = {"files/user/u/s/r/companies.xlsx": 100.0}

        # Agent has rewritten the spreadsheet (mtime > baseline)
        current = [_make_file("files/user/u/s/r/companies.xlsx", 250.0)]

        changed = _detect_changed_files(current, known)
        assert len(changed) == 1
        assert changed[0]["action"] == "modified"
        assert changed[0]["name"] == "companies.xlsx"
        # URL points to the same upload location so preview/download works
        assert changed[0]["url"] == "/files/user/u/s/r/companies.xlsx"

    def test_skips_tmp_code_files(self) -> None:
        known: dict[str, float] = {}
        current = [
            _make_file("files/user/u/s/r/tmp_code_abc.py", 100.0),
            _make_file("files/user/u/s/r/output.py", 100.0),
        ]
        changed = _detect_changed_files(current, known)
        names = [c["name"] for c in changed]
        assert "output.py" in names
        assert "tmp_code_abc.py" not in names

    def test_skips_supervisord_pid(self) -> None:
        known: dict[str, float] = {}
        current = [
            _make_file("files/user/u/s/r/supervisord.pid", 100.0),
            _make_file("files/user/u/s/r/result.txt", 100.0),
        ]
        changed = _detect_changed_files(current, known)
        names = [c["name"] for c in changed]
        assert "result.txt" in names
        assert "supervisord.pid" not in names

    def test_same_basename_different_paths_tracked_independently(self) -> None:
        """Two files with the same basename in different subdirs must
        track independently — that's why detection is path-keyed."""
        known: dict[str, float] = {}
        current = [
            _make_file("files/user/u/s/r/sub_a/data.csv", 100.0),
            _make_file("files/user/u/s/r/sub_b/data.csv", 100.0),
        ]
        changed = _detect_changed_files(current, known)
        assert len(changed) == 2
        urls = {c["url"] for c in changed}
        assert urls == {
            "/files/user/u/s/r/sub_a/data.csv",
            "/files/user/u/s/r/sub_b/data.csv",
        }

    def test_repeated_call_after_modification_is_idempotent(self) -> None:
        """After a modification is reported once, calling again with the
        same current state should not re-emit (mtime now matches known)."""
        known = {"files/user/u/s/r/x.md": 100.0}
        current = [_make_file("files/user/u/s/r/x.md", 200.0)]

        first = _detect_changed_files(current, known)
        assert len(first) == 1
        assert first[0]["action"] == "modified"

        second = _detect_changed_files(current, known)
        assert second == []


# =============================================================================
# TeamManager.set_uploaded_file_infos — path validation and reset behavior
# =============================================================================


def _make_team_manager(app_dir):
    """Build a minimal TeamManager rooted at the given app_dir for testing."""
    from magentic_ui.backend.teammanager.teammanager import TeamManager

    return TeamManager(app_dir=app_dir)


class TestSetUploadedFileInfos:
    """Covers Copilot review feedback on PR #574:
    - Path traversal hardening (the input ultimately comes from WS payload)
    - Reset semantics so a stale uploaded list never leaks into the next task
    """

    def test_accepts_valid_uploaded_path(self, tmp_path) -> None:
        # Real file under app_dir/files/user/...
        run_dir = tmp_path / "files" / "user" / "u1" / "s1" / "r1"
        run_dir.mkdir(parents=True)
        (run_dir / "data.csv").write_text("a,b\n1,2\n")

        tm = _make_team_manager(tmp_path)
        tm.set_uploaded_file_infos(
            [{"name": "data.csv", "path": "files/user/u1/s1/r1/data.csv"}]
        )

        assert len(tm._uploaded_file_infos) == 1
        info = tm._uploaded_file_infos[0]
        assert info["name"] == "data.csv"
        assert info["url"] == "/files/user/u1/s1/r1/data.csv"
        assert info["extension"] == "csv"
        # mtime came from the real file, not the time.time() fallback
        assert info["timestamp"] == (run_dir / "data.csv").stat().st_mtime

    def test_rejects_path_traversal(self, tmp_path) -> None:
        """A '..' segment must not be allowed to escape files/user."""
        run_dir = tmp_path / "files" / "user" / "u" / "s" / "r"
        run_dir.mkdir(parents=True)
        (run_dir / "ok.csv").write_text("ok")
        tm = _make_team_manager(tmp_path)
        tm.set_uploaded_file_infos(
            [
                {"name": "evil", "path": "files/user/../../etc/passwd"},
                {"name": "ok.csv", "path": "files/user/u/s/r/ok.csv"},
            ]
        )

        # Only the ok entry should remain; the traversal entry is dropped
        names = [i["name"] for i in tm._uploaded_file_infos]
        assert "evil" not in names
        assert names == ["ok.csv"]

    def test_rejects_absolute_path_outside_root(self, tmp_path) -> None:
        """An absolute filesystem path outside files/user is rejected even
        when the leading slash is stripped."""
        tm = _make_team_manager(tmp_path)
        tm.set_uploaded_file_infos([{"name": "shadow", "path": "/etc/shadow"}])
        assert tm._uploaded_file_infos == []

    def test_rejects_path_outside_files_user(self, tmp_path) -> None:
        """Paths under app_dir but outside files/user are rejected so
        attackers can't probe siblings (e.g. config files, db)."""
        tm = _make_team_manager(tmp_path)
        tm.set_uploaded_file_infos([{"name": "cfg", "path": "config.yaml"}])
        assert tm._uploaded_file_infos == []

    def test_skips_non_string_entries(self, tmp_path) -> None:
        run_dir = tmp_path / "files" / "user" / "u" / "s" / "r"
        run_dir.mkdir(parents=True)
        (run_dir / "good.csv").write_text("ok")
        tm = _make_team_manager(tmp_path)
        tm.set_uploaded_file_infos(
            [
                {"name": 123, "path": "files/user/u/s/r/x.csv"},
                {"name": "ok", "path": None},
                {"path": "files/user/u/s/r/anon"},
                {"name": "good.csv", "path": "files/user/u/s/r/good.csv"},
            ]
        )
        names = [i["name"] for i in tm._uploaded_file_infos]
        assert names == ["good.csv"]

    def test_missing_file_is_skipped(self, tmp_path) -> None:
        """File path passes scope validation but the file isn't on disk
        — entry must be dropped (not silently passed through with a
        synthetic mtime), so the agent never sees an attached_file
        reference it can't open."""
        # Make sure the directory exists so resolve() doesn't fail spuriously
        (tmp_path / "files" / "user" / "u" / "s" / "r").mkdir(parents=True)
        tm = _make_team_manager(tmp_path)
        tm.set_uploaded_file_infos(
            [{"name": "ghost.csv", "path": "files/user/u/s/r/ghost.csv"}]
        )
        assert tm._uploaded_file_infos == []

    def test_empty_list_clears_previous(self, tmp_path) -> None:
        """Reset semantics — second call with [] must wipe out the list
        from the first call. Otherwise the next task on the same
        TeamManager would emit stale uploaded_files."""
        run_dir = tmp_path / "files" / "user" / "u" / "s" / "r"
        run_dir.mkdir(parents=True)
        (run_dir / "first.csv").write_text("x")

        tm = _make_team_manager(tmp_path)
        tm.set_uploaded_file_infos(
            [{"name": "first.csv", "path": "files/user/u/s/r/first.csv"}]
        )
        assert len(tm._uploaded_file_infos) == 1

        tm.set_uploaded_file_infos([])
        assert tm._uploaded_file_infos == []

    def test_second_call_replaces_not_extends(self, tmp_path) -> None:
        """Second non-empty call must REPLACE, not append, the prior list."""
        run_dir = tmp_path / "files" / "user" / "u" / "s" / "r"
        run_dir.mkdir(parents=True)
        (run_dir / "a.csv").write_text("a")
        (run_dir / "b.csv").write_text("b")

        tm = _make_team_manager(tmp_path)
        tm.set_uploaded_file_infos(
            [{"name": "a.csv", "path": "files/user/u/s/r/a.csv"}]
        )
        tm.set_uploaded_file_infos(
            [{"name": "b.csv", "path": "files/user/u/s/r/b.csv"}]
        )
        names = [i["name"] for i in tm._uploaded_file_infos]
        assert names == ["b.csv"]


# Lightweight Run stub: set_uploaded_file_infos only reads .user_id /
# .session_id / .id, so we don't need a real SQLModel instance.
class _RunStub:
    def __init__(self, user_id: str, session_id: str, run_id: str) -> None:
        self.user_id = user_id
        self.session_id = session_id
        self.id = run_id


class TestSetUploadedFileInfosRunScoping:
    """Covers Copilot review feedback (round 2) on PR #574:
    when a `run` is passed, validation must scope to THAT run's directory
    so a malicious WS payload can't echo back URLs/timestamps for files
    belonging to other users / sessions / runs.
    """

    def test_accepts_path_in_current_run(self, tmp_path) -> None:
        run_dir = tmp_path / "files" / "user" / "u1" / "s1" / "r1"
        run_dir.mkdir(parents=True)
        (run_dir / "data.csv").write_text("ok")

        tm = _make_team_manager(tmp_path)
        run = _RunStub("u1", "s1", "r1")
        tm.set_uploaded_file_infos(
            [{"name": "data.csv", "path": "files/user/u1/s1/r1/data.csv"}],
            run=run,
        )

        assert len(tm._uploaded_file_infos) == 1
        assert tm._uploaded_file_infos[0]["url"] == "/files/user/u1/s1/r1/data.csv"

    def test_rejects_path_in_other_run_same_session(self, tmp_path) -> None:
        # Another run dir under the same session — must be rejected
        other_run_dir = tmp_path / "files" / "user" / "u1" / "s1" / "r-other"
        other_run_dir.mkdir(parents=True)
        (other_run_dir / "secret.csv").write_text("private")

        tm = _make_team_manager(tmp_path)
        run = _RunStub("u1", "s1", "r1")
        tm.set_uploaded_file_infos(
            [{"name": "secret.csv", "path": "files/user/u1/s1/r-other/secret.csv"}],
            run=run,
        )
        assert tm._uploaded_file_infos == []

    def test_rejects_path_in_other_session(self, tmp_path) -> None:
        other_run_dir = tmp_path / "files" / "user" / "u1" / "s-other" / "r-x"
        other_run_dir.mkdir(parents=True)
        (other_run_dir / "x.csv").write_text("x")

        tm = _make_team_manager(tmp_path)
        run = _RunStub("u1", "s1", "r1")
        tm.set_uploaded_file_infos(
            [{"name": "x.csv", "path": "files/user/u1/s-other/r-x/x.csv"}],
            run=run,
        )
        assert tm._uploaded_file_infos == []

    def test_rejects_path_in_other_user(self, tmp_path) -> None:
        other_run_dir = tmp_path / "files" / "user" / "u-other" / "s" / "r"
        other_run_dir.mkdir(parents=True)
        (other_run_dir / "y.csv").write_text("y")

        tm = _make_team_manager(tmp_path)
        run = _RunStub("u1", "s1", "r1")
        tm.set_uploaded_file_infos(
            [{"name": "y.csv", "path": "files/user/u-other/s/r/y.csv"}],
            run=run,
        )
        assert tm._uploaded_file_infos == []

    def test_run_with_none_ids_falls_back_to_unknown_segments(self, tmp_path) -> None:
        """Run with None ids resolves to the 'unknown_*' fallback dir, so
        only paths under that exact dir are accepted."""
        run_dir = (
            tmp_path
            / "files"
            / "user"
            / "unknown_user"
            / "unknown_session"
            / "unknown_run"
        )
        run_dir.mkdir(parents=True)
        (run_dir / "z.csv").write_text("z")

        tm = _make_team_manager(tmp_path)
        run = _RunStub(None, None, None)
        tm.set_uploaded_file_infos(
            [
                {
                    "name": "z.csv",
                    "path": "files/user/unknown_user/unknown_session/unknown_run/z.csv",
                },
                {"name": "elsewhere", "path": "files/user/u1/s1/r1/x.csv"},
            ],
            run=run,
        )
        names = [i["name"] for i in tm._uploaded_file_infos]
        assert names == ["z.csv"]


class TestSetUploadedFileInfosMetadataFromPath:
    """Covers Copilot review feedback (round 2) on PR #574: display
    metadata (name, extension, file_type) must come from the resolved
    on-disk basename, not the client-supplied `name`. Otherwise a payload
    like `{name: "report.pdf", path: ".../data.csv"}` would advertise a
    CSV URL labeled as a PDF.
    """

    def test_extension_derived_from_path_basename(self, tmp_path) -> None:
        run_dir = tmp_path / "files" / "user" / "u" / "s" / "r"
        run_dir.mkdir(parents=True)
        (run_dir / "data.csv").write_text("a,b\n1,2\n")

        tm = _make_team_manager(tmp_path)
        tm.set_uploaded_file_infos(
            [{"name": "report.pdf", "path": "files/user/u/s/r/data.csv"}]
        )

        assert len(tm._uploaded_file_infos) == 1
        info = tm._uploaded_file_infos[0]
        # Display fields reflect the real file, not the client-supplied lie
        assert info["name"] == "data.csv"
        assert info["extension"] == "csv"
        assert info["file_type"] == "csv"
        # URL still uses the client-supplied path so the static file
        # endpoint serves the right resource (validation already ensured
        # it stays inside the allowed root).
        assert info["url"] == "/files/user/u/s/r/data.csv"

    def test_name_with_no_extension_uses_empty_extension(self, tmp_path) -> None:
        run_dir = tmp_path / "files" / "user" / "u" / "s" / "r"
        run_dir.mkdir(parents=True)
        (run_dir / "Makefile").write_text("all:\n")

        tm = _make_team_manager(tmp_path)
        tm.set_uploaded_file_infos(
            [{"name": "Makefile.pdf", "path": "files/user/u/s/r/Makefile"}]
        )

        info = tm._uploaded_file_infos[0]
        assert info["name"] == "Makefile"
        assert info["extension"] == ""


# =============================================================================
# TeamManager.add_uploaded_files — mid-session upload registration
# =============================================================================


class TestAddUploadedFiles:
    """Covers issue #291: mid-session uploads must be registered in the
    file-tracking baseline so they aren't reported as agent-created files,
    and must be appended (not replace) to the uploaded-files list shown in
    the end-of-run summary.
    """

    def test_appends_rather_than_replaces(self, tmp_path) -> None:
        run_dir = tmp_path / "files" / "user" / "u" / "s" / "r"
        run_dir.mkdir(parents=True)
        (run_dir / "first.csv").write_text("first")
        (run_dir / "second.csv").write_text("second")

        tm = _make_team_manager(tmp_path)
        # Initial upload at task start — REPLACE semantics
        tm.set_uploaded_file_infos(
            [{"name": "first.csv", "path": "files/user/u/s/r/first.csv"}]
        )
        # Mid-session upload — APPEND semantics
        added = tm.add_uploaded_files(
            [{"name": "second.csv", "path": "files/user/u/s/r/second.csv"}]
        )

        names = [i["name"] for i in tm._uploaded_file_infos]
        assert names == ["first.csv", "second.csv"]
        assert [i["name"] for i in added] == ["second.csv"]

    def test_registers_in_known_files_baseline(self, tmp_path) -> None:
        """After add_uploaded_files, _detect_changed_files for the same path
        should NOT emit a 'created' event — the file is treated as already
        known."""
        from magentic_ui.backend.teammanager.teammanager import (
            _detect_changed_files,
        )

        run_dir = tmp_path / "files" / "user" / "u" / "s" / "r"
        run_dir.mkdir(parents=True)
        upload = run_dir / "upload.csv"
        upload.write_text("a,b\n")

        tm = _make_team_manager(tmp_path)
        tm.add_uploaded_files(
            [{"name": "upload.csv", "path": "files/user/u/s/r/upload.csv"}]
        )

        # Simulate a subsequent change-detection cycle: the file is on disk
        # with the same mtime as when it was registered.
        current_files = [
            {
                "path": "files/user/u/s/r/upload.csv",
                "short_path": "files/user/u/s/r/upload.csv",
                "name": "upload.csv",
                "extension": "csv",
                "type": "csv",
                "timestamp": upload.stat().st_mtime,
            }
        ]
        changed = _detect_changed_files(current_files, tm._known_files)
        assert changed == []

    def test_subsequent_modification_emits_modified(self, tmp_path) -> None:
        """If an agent modifies an uploaded file after add_uploaded_files,
        the next change-detection cycle should report it as 'modified',
        not 'created'."""
        from magentic_ui.backend.teammanager.teammanager import (
            _detect_changed_files,
        )

        run_dir = tmp_path / "files" / "user" / "u" / "s" / "r"
        run_dir.mkdir(parents=True)
        upload = run_dir / "upload.csv"
        upload.write_text("v1")

        tm = _make_team_manager(tmp_path)
        tm.add_uploaded_files(
            [{"name": "upload.csv", "path": "files/user/u/s/r/upload.csv"}]
        )

        # Agent modifies the file — bump mtime past the registered baseline
        registered_mtime = tm._known_files["files/user/u/s/r/upload.csv"]
        current_files = [
            {
                "path": "files/user/u/s/r/upload.csv",
                "short_path": "files/user/u/s/r/upload.csv",
                "name": "upload.csv",
                "extension": "csv",
                "type": "csv",
                "timestamp": registered_mtime + 10.0,
            }
        ]
        changed = _detect_changed_files(current_files, tm._known_files)
        assert len(changed) == 1
        assert changed[0]["action"] == "modified"
        assert changed[0]["name"] == "upload.csv"

    def test_rejects_path_traversal(self, tmp_path) -> None:
        """add_uploaded_files must reuse the same path validation as
        set_uploaded_file_infos."""
        run_dir = tmp_path / "files" / "user" / "u" / "s" / "r"
        run_dir.mkdir(parents=True)
        (run_dir / "ok.csv").write_text("ok")
        tm = _make_team_manager(tmp_path)
        added = tm.add_uploaded_files(
            [
                {"name": "evil", "path": "files/user/../../etc/passwd"},
                {"name": "ok.csv", "path": "files/user/u/s/r/ok.csv"},
            ]
        )
        assert [i["name"] for i in added] == ["ok.csv"]
        # _known_files should only contain the validated entry
        assert "files/user/u/s/r/ok.csv" in tm._known_files
        assert all("passwd" not in k and ".." not in k for k in tm._known_files)

    def test_rejects_path_outside_run_dir_when_run_provided(self, tmp_path) -> None:
        """When a run is passed, paths outside that run's directory are
        rejected — same scoping rules as set_uploaded_file_infos."""
        other_run_dir = tmp_path / "files" / "user" / "u1" / "s1" / "r-other"
        other_run_dir.mkdir(parents=True)
        (other_run_dir / "secret.csv").write_text("private")

        tm = _make_team_manager(tmp_path)
        run = _RunStub("u1", "s1", "r1")
        added = tm.add_uploaded_files(
            [{"name": "secret.csv", "path": "files/user/u1/s1/r-other/secret.csv"}],
            run=run,
        )
        assert added == []
        assert tm._uploaded_file_infos == []
        assert tm._known_files == {}

    def test_empty_input_is_noop(self, tmp_path) -> None:
        tm = _make_team_manager(tmp_path)
        # Pre-seed state so we can verify nothing changes
        tm._known_files = {"existing/path": 100.0}
        tm._uploaded_file_infos = [{"name": "existing"}]

        added = tm.add_uploaded_files([])
        assert added == []
        assert tm._known_files == {"existing/path": 100.0}
        assert tm._uploaded_file_infos == [{"name": "existing"}]

    def test_returns_safe_refs_in_construct_task_shape(self, tmp_path) -> None:
        """add_uploaded_files returns server-validated safe refs in the
        construct_task input shape ({name, path, type, uploaded}).
        Caller uses these — not the raw client payload — to build
        attached_files_json so a malicious path never reaches the wire.

        Also verifies that display fields come from the resolved on-disk
        basename (not the client-supplied name), so a payload like
        {name: "report.pdf", path: ".../data.csv"} can't smuggle a
        misleading label into chat metadata.
        """
        run_dir = tmp_path / "files" / "user" / "u" / "s" / "r"
        run_dir.mkdir(parents=True)
        (run_dir / "data.csv").write_text("a,b\n")

        tm = _make_team_manager(tmp_path)
        added = tm.add_uploaded_files(
            [
                # Client lies about the name — server must use the
                # on-disk basename in the returned safe ref.
                {
                    "name": "report.pdf",
                    "path": "files/user/u/s/r/data.csv",
                    "type": "application/pdf",
                    "uploaded": True,
                },
            ]
        )

        assert len(added) == 1
        ref = added[0]
        # Safe ref shape (matches construct_task input)
        assert set(ref.keys()) == {"name", "path", "type", "uploaded"}
        # Name comes from the resolved file, not the client lie
        assert ref["name"] == "data.csv"
        assert ref["path"] == "files/user/u/s/r/data.csv"
        assert ref["type"] == "application/pdf"
        assert ref["uploaded"] is True

    def test_safe_refs_filter_traversal_attempts(self, tmp_path) -> None:
        """When some entries fail validation, only the safe ones appear in
        the returned safe-ref list."""
        run_dir = tmp_path / "files" / "user" / "u" / "s" / "r"
        run_dir.mkdir(parents=True)
        (run_dir / "ok.csv").write_text("ok")

        tm = _make_team_manager(tmp_path)
        added = tm.add_uploaded_files(
            [
                {"name": "evil", "path": "files/user/../../etc/passwd"},
                {"name": "ok.csv", "path": "files/user/u/s/r/ok.csv"},
            ]
        )

        assert [r["name"] for r in added] == ["ok.csv"]
        # All returned refs are in the safe shape
        assert all("path" in r and "uploaded" in r for r in added)

    def test_non_string_type_is_coerced_to_default(self, tmp_path) -> None:
        """A malicious or buggy client may send `type` as a non-string
        (object, number, list). The server-validated safe ref must
        always carry a string `type` so the frontend's `String(...)`
        coercion can't yield "[object Object]" and break file-type
        icons."""
        run_dir = tmp_path / "files" / "user" / "u" / "s" / "r"
        run_dir.mkdir(parents=True)
        (run_dir / "data.csv").write_text("x")

        tm = _make_team_manager(tmp_path)
        added = tm.add_uploaded_files(
            [
                {
                    "name": "data.csv",
                    "path": "files/user/u/s/r/data.csv",
                    "type": {"malicious": "object"},
                    "uploaded": True,
                },
            ]
        )

        assert len(added) == 1
        assert added[0]["type"] == "file"
