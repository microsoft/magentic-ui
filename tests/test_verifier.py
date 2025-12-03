"""Tests for the bash post-hoc filesystem verifier."""

from __future__ import annotations

import pytest

from magentic_ui.teams.omniagent._verifier import (
    Change,
    FsState,
    VerifierClass,
    decide_verifier_class,
    detect_word_split_hint,
    diff_states,
    extract_candidate_paths,
    parse_stat_output,
    render_diff,
)


# ===================================================================
# extract_candidate_paths
# ===================================================================


class TestExtractCandidatePaths:
    def test_simple_rm_with_path(self) -> None:
        assert extract_candidate_paths("rm -rf /tmp/foo") == ["/tmp/foo"]

    def test_rm_with_quoted_path_with_spaces(self) -> None:
        assert extract_candidate_paths("rm -rf 'my dir'") == ["my dir"]

    def test_double_quoted_path(self) -> None:
        assert extract_candidate_paths('rm -rf "my dir"') == ["my dir"]

    def test_multi_paths(self) -> None:
        assert extract_candidate_paths("rm -rf /a /b /c") == ["/a", "/b", "/c"]

    def test_skips_short_and_long_flags(self) -> None:
        assert extract_candidate_paths("rm -rf --verbose /tmp/foo") == ["/tmp/foo"]

    def test_bare_relative_paths_are_kept(self) -> None:
        # mv src dst — both are bare names. We accept them; if they don't
        # exist they just degrade to "missing" in the diff, which is fine.
        assert extract_candidate_paths("mv src dst") == ["src", "dst"]

    def test_bails_on_unquoted_glob(self) -> None:
        assert extract_candidate_paths("rm -rf /tmp/*.log") is None

    def test_bails_on_unquoted_var(self) -> None:
        assert extract_candidate_paths("rm -rf $HOME/build") is None

    def test_bails_on_command_substitution_dollar(self) -> None:
        assert extract_candidate_paths("rm -rf $(pwd)/junk") is None

    def test_bails_on_command_substitution_backtick(self) -> None:
        assert extract_candidate_paths("rm -rf `pwd`/junk") is None

    def test_bails_on_double_amp(self) -> None:
        assert extract_candidate_paths("rm -rf /a && rm -rf /b") is None

    def test_bails_on_pipe(self) -> None:
        assert extract_candidate_paths("ls | xargs rm") is None

    def test_bails_on_semicolon(self) -> None:
        assert extract_candidate_paths("rm /a; rm /b") is None

    def test_bails_on_unbalanced_quotes(self) -> None:
        assert extract_candidate_paths("rm -rf 'unclosed") is None

    def test_bails_on_unquoted_tilde(self) -> None:
        assert extract_candidate_paths("rm -rf ~/junk") is None

    def test_preserves_quoted_metachars(self) -> None:
        # ; is inside single quotes — bash sees it as a literal char, not a
        # statement separator. The verifier should proceed.
        assert extract_candidate_paths("rm -rf 'a;b'") == ["a;b"]

    def test_preserves_quoted_glob(self) -> None:
        assert extract_candidate_paths("rm -rf 'a*b'") == ["a*b"]

    def test_caps_at_20(self) -> None:
        paths = " ".join(f"/p{i}" for i in range(30))
        result = extract_candidate_paths(f"rm -rf {paths}")
        assert result is not None
        assert len(result) == 20

    def test_bails_on_oversize_path(self) -> None:
        long_path = "/" + "a" * 5000
        assert extract_candidate_paths(f"rm -rf {long_path}") is None

    def test_strips_program_name(self) -> None:
        # The first token (rm) is the program, not a path.
        result = extract_candidate_paths("rm /tmp/foo")
        assert result == ["/tmp/foo"]
        assert "rm" not in (result or [])

    def test_empty_command(self) -> None:
        assert extract_candidate_paths("") is None

    def test_program_only_no_args(self) -> None:
        assert extract_candidate_paths("ls") == []


# ===================================================================
# decide_verifier_class
# ===================================================================


class TestDecideVerifierClass:
    @pytest.mark.parametrize(
        "cmd", ["rm /tmp/foo", "rm -rf /a /b", "rmdir /tmp/foo", "shred /tmp/secret"]
    )
    def test_destructive_is_pre_and_post(self, cmd: str) -> None:
        assert decide_verifier_class(cmd) == VerifierClass.PRE_AND_POST

    @pytest.mark.parametrize(
        "cmd",
        [
            "mv src dst",
            "cp src dst",
            "cp -r src dst",
            "chmod 755 file",
            "chown user file",
            "ln -s target link",
            "tee /tmp/out",
            "truncate -s 0 file",
        ],
    )
    def test_mutating_is_post_only(self, cmd: str) -> None:
        assert decide_verifier_class(cmd) == VerifierClass.POST_ONLY

    @pytest.mark.parametrize(
        "cmd", ["ls", "ls -la /tmp", "cat file.txt", "grep foo bar.txt", "echo hi", ""]
    )
    def test_read_only_is_none(self, cmd: str) -> None:
        assert decide_verifier_class(cmd) == VerifierClass.NONE

    def test_full_path_to_binary_resolves(self) -> None:
        assert (
            decide_verifier_class("/usr/bin/rm /tmp/foo") == VerifierClass.PRE_AND_POST
        )

    def test_unknown_command_is_none(self) -> None:
        assert decide_verifier_class("nonexistent_tool /tmp/foo") == VerifierClass.NONE


# ===================================================================
# parse_stat_output
# ===================================================================


class TestParseStatOutput:
    def test_parses_normal_output(self) -> None:
        stdout = (
            "/tmp/a|412|1714946221|regular file\n" "/tmp/b|0|1714946222|directory\n"
        )
        result = parse_stat_output(stdout)
        assert result == {
            "/tmp/a": FsState(size=412, mtime=1714946221, ftype="regular file"),
            "/tmp/b": FsState(size=0, mtime=1714946222, ftype="directory"),
        }

    def test_handles_empty_lines(self) -> None:
        stdout = "/tmp/a|10|100|regular file\n\n  \n/tmp/b|20|200|directory\n"
        result = parse_stat_output(stdout)
        assert set(result.keys()) == {"/tmp/a", "/tmp/b"}

    def test_handles_malformed_lines_silently(self) -> None:
        stdout = "/tmp/a|10|100|regular file\nGARBAGE\n/tmp/b|20|200|directory\n"
        result = parse_stat_output(stdout)
        assert set(result.keys()) == {"/tmp/a", "/tmp/b"}

    def test_handles_non_numeric_values(self) -> None:
        stdout = "/tmp/a|notanumber|100|regular file\n"
        # Malformed → silently dropped
        assert parse_stat_output(stdout) == {}

    def test_empty_input(self) -> None:
        assert parse_stat_output("") == {}

    def test_path_with_pipe_in_name(self) -> None:
        # We use | as a separator, but a path could contain | (rare).
        # split('|', 3) limits splits, so the name is preserved as-is up to
        # the third pipe. A path containing | is undefined behavior; we
        # accept whichever interpretation the parser produces.
        # Just verify it doesn't crash.
        parse_stat_output("/tmp/a|file|100|200|regular file\n")  # no assert


# ===================================================================
# diff_states — PRE_AND_POST mode
# ===================================================================


class TestDiffStatesPreAndPost:
    def _state(
        self, size: int = 0, mtime: int = 0, ftype: str = "regular file"
    ) -> FsState:
        return FsState(size=size, mtime=mtime, ftype=ftype)

    def test_removed(self) -> None:
        before = {"/a": self._state()}
        after: dict[str, FsState | None] = {}
        result = diff_states(["/a"], before, after)
        assert result == [Change("/a", "removed")]

    def test_added(self) -> None:
        before: dict[str, FsState | None] = {}
        after = {"/a": self._state()}
        result = diff_states(["/a"], before, after)
        assert result == [Change("/a", "added")]

    def test_changed_size(self) -> None:
        before = {"/a": self._state(size=10)}
        after = {"/a": self._state(size=20)}
        result = diff_states(["/a"], before, after)
        assert result == [Change("/a", "changed")]

    def test_changed_mtime(self) -> None:
        before = {"/a": self._state(mtime=100)}
        after = {"/a": self._state(mtime=200)}
        result = diff_states(["/a"], before, after)
        assert result == [Change("/a", "changed")]

    def test_unchanged(self) -> None:
        before = {"/a": self._state(size=10, mtime=100)}
        after = {"/a": self._state(size=10, mtime=100)}
        result = diff_states(["/a"], before, after)
        assert result == [Change("/a", "unchanged")]

    def test_missing_in_both(self) -> None:
        before: dict[str, FsState | None] = {}
        after: dict[str, FsState | None] = {}
        result = diff_states(["/missing"], before, after)
        assert result == [Change("/missing", "missing")]


# ===================================================================
# diff_states — POST_ONLY mode (no baseline)
# ===================================================================


class TestDiffStatesPostOnly:
    def test_path_present_after(self) -> None:
        after = {"/a": FsState(10, 100, "regular file")}
        result = diff_states(["/a"], None, after)
        assert result == [Change("/a", "present")]

    def test_path_absent_after(self) -> None:
        after: dict[str, FsState | None] = {}
        result = diff_states(["/a"], None, after)
        assert result == [Change("/a", "absent")]


# ===================================================================
# render_diff
# ===================================================================


class TestRenderDiff:
    def test_pre_and_post_renders_changes(self) -> None:
        changes = [
            Change("/a", "removed"),
            Change("/b", "added"),
            Change("/c", "unchanged"),
        ]
        result = render_diff(changes, VerifierClass.PRE_AND_POST)
        assert result is not None
        assert "removed: /a" in result
        assert "added: /b" in result
        assert "unchanged: /c" in result

    def test_pre_and_post_skips_only_missing(self) -> None:
        # If everything was missing in both, the verifier has no signal.
        changes = [Change("/a", "missing"), Change("/b", "missing")]
        result = render_diff(changes, VerifierClass.PRE_AND_POST)
        assert result is None

    def test_post_only_skips_when_all_present(self) -> None:
        # cp file1 file2 dst/ — everything exists post-cmd. Boring.
        changes = [Change("/a", "present"), Change("/b", "present")]
        result = render_diff(changes, VerifierClass.POST_ONLY)
        assert result is None

    def test_post_only_renders_absent(self) -> None:
        # mv src dst → src absent, dst present. Show the absent one as
        # signal that mv worked.
        changes = [Change("/src", "absent"), Change("/dst", "present")]
        result = render_diff(changes, VerifierClass.POST_ONLY)
        assert result is not None
        assert "absent: /src" in result
        assert "present: /dst" in result

    def test_caps_at_10_lines(self) -> None:
        changes = [Change(f"/p{i}", "removed") for i in range(20)]
        result = render_diff(changes, VerifierClass.PRE_AND_POST)
        assert result is not None
        # 10 visible lines + the "more" tail
        assert result.count("removed:") == 10
        assert "more" in result

    def test_empty_changes_returns_none(self) -> None:
        assert render_diff([], VerifierClass.PRE_AND_POST) is None
        assert render_diff([], VerifierClass.POST_ONLY) is None


# ===================================================================
# detect_word_split_hint — surfaced after-the-fact when bash word-splits
# an unquoted path with whitespace.
# ===================================================================


class TestDetectWordSplitHint:
    def test_r51_real_mv_with_unquoted_meeting_minutes(self) -> None:
        # Reproduced verbatim from trace.jsonl line 53 / R51.
        cmd = (
            "mv /sessions/1/mounts/New/Meeting Minutes/*.docx "
            "/sessions/1/mounts/New/Meeting Minutes/"
        )
        stderr = (
            "mv: cannot stat 'Minutes/*.docx': No such file or directory\n"
            "mv: cannot stat '/sessions/1/mounts/New/Meeting': No such file or directory\n"
        )
        hint = detect_word_split_hint(cmd, exit_code=1, stderr=stderr)
        assert hint is not None
        assert "/sessions/1/mounts/New/Meeting Minutes/*.docx" in hint
        assert "unquoted" in hint.lower() or "word-split" in hint.lower()

    def test_r49_real_ls_with_unquoted_meeting_transcipts(self) -> None:
        cmd = "ls -la /sessions/1/mounts/New/Meeting Transcipts/"
        stderr = "ls: cannot access 'Transcipts/': No such file or directory\n"
        hint = detect_word_split_hint(cmd, exit_code=2, stderr=stderr)
        assert hint is not None
        assert "/sessions/1/mounts/New/Meeting Transcipts/" in hint

    def test_skip_on_success(self) -> None:
        cmd = "ls /tmp/anything"
        assert detect_word_split_hint(cmd, exit_code=0, stderr="") is None

    def test_skip_when_stderr_has_no_path_error(self) -> None:
        cmd = "python /tmp/script.py"
        stderr = "Traceback (most recent call last):\n..."
        assert detect_word_split_hint(cmd, exit_code=1, stderr=stderr) is None

    def test_legit_two_path_mv_does_not_trip(self) -> None:
        cmd = "mv /tmp/a /tmp/b"
        stderr = "mv: cannot stat '/tmp/a': No such file or directory"
        assert detect_word_split_hint(cmd, exit_code=1, stderr=stderr) is None

    def test_legit_multi_source_cp_does_not_trip(self) -> None:
        # Three explicitly absolute sources + one absolute dest. None look
        # like fragments of a single path, so no false positive.
        cmd = "cp /a/file1.txt /a/file2.txt /a/file3.txt /dst/"
        stderr = "cp: cannot stat '/a/file1.txt': No such file or directory"
        assert detect_word_split_hint(cmd, exit_code=1, stderr=stderr) is None

    def test_skip_on_unparseable_command(self) -> None:
        # shlex raises on unbalanced quotes
        cmd = "rm -rf 'unclosed"
        stderr = "ls: cannot stat ..."
        assert detect_word_split_hint(cmd, exit_code=1, stderr=stderr) is None

    def test_skip_on_too_few_tokens(self) -> None:
        cmd = "ls"
        assert detect_word_split_hint(cmd, exit_code=1, stderr="No such file") is None

    def test_hint_contains_quoting_example(self) -> None:
        cmd = "ls /tmp/My Folder/file"
        stderr = "ls: cannot access 'Folder/file': No such file or directory"
        hint = detect_word_split_hint(cmd, exit_code=2, stderr=stderr)
        assert hint is not None
        # The reconstructed path should appear quoted in the hint
        assert "'/tmp/My Folder/file'" in hint or '"/tmp/My Folder/file"' in hint
