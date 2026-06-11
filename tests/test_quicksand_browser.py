"""Tests for Quicksand browser manager and playwright browser.

Tests slot management logic and profile copy-on-acquire lifecycle
without requiring a real Quicksand VM.
"""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from magentic_ui.tools.playwright.browser.quicksand_browser_manager import (
    BrowserSlot,
    BrowserSlotPoolFullError,
    QuicksandBrowserManager,
    _AD_BLOCK_DOMAINS,
    _build_host_resolver_rules,
)
from magentic_ui.sandbox._path_normalizer import (
    _is_wsl,
    extract_dir_basename,
    normalize_host_path,
    validate_session_id as _validate_session_id,
    validate_dir_name as _validate_dir_name,
)
from magentic_ui.sandbox._path_validator import validate_host_path


# ---------------------------------------------------------------------------
# Slot management (unit tests - no VM)
# ---------------------------------------------------------------------------


class TestSlotManagement:
    def _make_manager(self, pool_size: int = 3) -> QuicksandBrowserManager:
        mgr = QuicksandBrowserManager(pool_size=pool_size)
        # Manually set up slots without starting VM
        mgr._slots = [
            BrowserSlot(
                index=i,
                display=99 + i,
                cdp_guest_port=9222 + i,
                cdp_host_port=40000 + i,
                novnc_guest_port=6080 + i,
                novnc_host_port=41000 + i,
            )
            for i in range(pool_size)
        ]
        mgr._started = True
        mgr._sandbox = AsyncMock()
        return mgr

    @pytest.mark.asyncio
    async def test_acquire_returns_slot(self):
        mgr = self._make_manager()
        mgr._start_slot_services = AsyncMock()

        slot = await mgr.acquire_slot()
        assert slot.index == 0
        assert slot.in_use is True
        assert slot.display == 99

    @pytest.mark.asyncio
    async def test_acquire_multiple_slots(self):
        mgr = self._make_manager(pool_size=3)
        mgr._start_slot_services = AsyncMock()

        s0 = await mgr.acquire_slot()
        s1 = await mgr.acquire_slot()
        s2 = await mgr.acquire_slot()

        assert {s0.index, s1.index, s2.index} == {0, 1, 2}

    @pytest.mark.asyncio
    async def test_acquire_raises_when_pool_full(self):
        """Pool exhaustion fails fast instead of blocking forever (issue #587).

        The old behavior was ``acquire_slot`` awaited a Condition until a
        slot was released, which manifested as the user's session being
        stuck. Callers are now responsible for surfacing the failure (the
        connection manager turns it into an InputRequest).
        """
        mgr = self._make_manager(pool_size=2)
        mgr._start_slot_services = AsyncMock()
        mgr._stop_slot_services = AsyncMock()

        await mgr.acquire_slot()
        await mgr.acquire_slot()

        with pytest.raises(BrowserSlotPoolFullError):
            await mgr.acquire_slot()

    @pytest.mark.asyncio
    async def test_acquire_succeeds_after_release(self):
        """A released slot is immediately re-acquirable."""
        mgr = self._make_manager(pool_size=1)
        mgr._start_slot_services = AsyncMock()
        mgr._stop_slot_services = AsyncMock()

        slot = await mgr.acquire_slot()
        await mgr.release_slot(slot)
        slot2 = await mgr.acquire_slot()
        assert slot2.index == 0
        assert slot2.in_use is True

    @pytest.mark.asyncio
    async def test_release_makes_slot_available(self):
        mgr = self._make_manager(pool_size=1)
        mgr._start_slot_services = AsyncMock()
        mgr._stop_slot_services = AsyncMock()

        slot = await mgr.acquire_slot()
        assert slot.in_use is True

        await mgr.release_slot(slot)
        assert slot.in_use is False

        # Should be able to acquire again
        slot2 = await mgr.acquire_slot()
        assert slot2.index == 0

    @pytest.mark.asyncio
    async def test_slot_has_cdp_ports(self):
        mgr = self._make_manager(pool_size=2)
        mgr._start_slot_services = AsyncMock()

        s0 = await mgr.acquire_slot()
        s1 = await mgr.acquire_slot()

        assert s0.cdp_guest_port == 9222
        assert s0.cdp_host_port == 40000
        assert s1.cdp_guest_port == 9223
        assert s1.cdp_host_port == 40001


# ---------------------------------------------------------------------------
# Profile copy-on-acquire lifecycle (mocked sandbox)
# ---------------------------------------------------------------------------


class TestProfileLifecycle:
    def _make_manager_with_mock_sandbox(self) -> QuicksandBrowserManager:
        mgr = QuicksandBrowserManager(pool_size=1)
        mgr._slots = [
            BrowserSlot(
                index=0,
                display=99,
                cdp_guest_port=9222,
                cdp_host_port=40000,
                novnc_guest_port=6080,
                novnc_host_port=41000,
            )
        ]
        mgr._started = True

        mock_sb = AsyncMock()
        mock_result = MagicMock()
        mock_result.exit_code = 0
        mock_result.stdout = (
            "/root/.cache/ms-playwright/chromium-1234/chrome-linux/chromium\n"
        )
        mock_result.stderr = ""
        mock_sb.execute.return_value = mock_result
        mgr._sandbox = mock_sb
        return mgr

    @pytest.mark.asyncio
    async def test_start_slot_copies_master_profile(self):
        mgr = self._make_manager_with_mock_sandbox()
        slot = mgr._slots[0]

        await mgr._start_slot_services(slot)

        # Check that rsync was called to copy master to slot
        calls = [str(c) for c in mgr._sandbox.execute.call_args_list]
        copy_calls = [c for c in calls if "rsync" in c and "/profiles/master" in c]
        assert len(copy_calls) >= 1, f"Expected profile copy call, got: {calls}"

    @pytest.mark.asyncio
    async def test_start_slot_launches_chromium_with_user_data_dir(self):
        mgr = self._make_manager_with_mock_sandbox()
        slot = mgr._slots[0]

        await mgr._start_slot_services(slot)

        calls = [str(c) for c in mgr._sandbox.execute.call_args_list]
        chromium_calls = [c for c in calls if "--user-data-dir=" in c]
        assert (
            len(chromium_calls) >= 1
        ), f"Expected chromium launch with --user-data-dir, got: {calls}"

        cdp_calls = [c for c in calls if "--remote-debugging-port=" in c]
        assert (
            len(cdp_calls) >= 1
        ), f"Expected chromium launch with --remote-debugging-port, got: {calls}"

    @pytest.mark.asyncio
    async def test_stop_slot_merges_profile_back(self):
        mgr = self._make_manager_with_mock_sandbox()
        slot = mgr._slots[0]

        await mgr._stop_slot_services(slot)

        calls = [str(c) for c in mgr._sandbox.execute.call_args_list]
        merge_calls = [
            c
            for c in calls
            if "rsync" in c and "/profiles/slot-0" in c and "/profiles/master" in c
        ]
        assert len(merge_calls) >= 1, f"Expected profile merge-back call, got: {calls}"

    @pytest.mark.asyncio
    async def test_stop_slot_sigterm_before_sigkill(self):
        mgr = self._make_manager_with_mock_sandbox()
        slot = mgr._slots[0]

        await mgr._stop_slot_services(slot)

        calls = [str(c) for c in mgr._sandbox.execute.call_args_list]
        # Verify the graceful shutdown uses pkill SIGTERM then pkill -9 SIGKILL
        graceful_calls = [c for c in calls if "pkill -f" in c and "pkill -9 -f" in c]
        assert (
            len(graceful_calls) >= 1
        ), f"Expected graceful shutdown with pkill then pkill -9, got: {calls}"


# ---------------------------------------------------------------------------
# Failure + cleanup paths
# ---------------------------------------------------------------------------


class TestAcquireSlotFailureCleanup:
    def _make_manager(self) -> QuicksandBrowserManager:
        mgr = QuicksandBrowserManager(pool_size=2)
        mgr._slots = [
            BrowserSlot(
                index=i,
                display=99 + i,
                cdp_guest_port=9222 + i,
                cdp_host_port=40000 + i,
                novnc_guest_port=6080 + i,
                novnc_host_port=41000 + i,
            )
            for i in range(2)
        ]
        mgr._started = True
        mgr._sandbox = AsyncMock()
        return mgr

    @pytest.mark.asyncio
    async def test_acquire_releases_slot_on_start_failure(self):
        mgr = self._make_manager()
        mgr._start_slot_services = AsyncMock(side_effect=RuntimeError("chromium crash"))
        mgr._stop_slot_services = AsyncMock()

        with pytest.raises(RuntimeError, match="chromium crash"):
            await mgr.acquire_slot()

        # Slot should be released back to pool
        assert mgr._slots[0].in_use is False
        # Cleanup should have been attempted
        mgr._stop_slot_services.assert_called_once()

    @pytest.mark.asyncio
    async def test_acquire_releases_slot_even_if_stop_fails(self):
        mgr = self._make_manager()
        mgr._start_slot_services = AsyncMock(side_effect=RuntimeError("start failed"))
        mgr._stop_slot_services = AsyncMock(
            side_effect=RuntimeError("stop also failed")
        )

        with pytest.raises(RuntimeError, match="start failed"):
            await mgr.acquire_slot()

        # Slot must still be released despite stop failure
        assert mgr._slots[0].in_use is False

    @pytest.mark.asyncio
    async def test_acquire_after_failure_reuses_slot(self):
        mgr = self._make_manager()
        call_count = 0

        async def fail_then_succeed(slot: BrowserSlot) -> None:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("transient failure")

        mgr._start_slot_services = AsyncMock(side_effect=fail_then_succeed)
        mgr._stop_slot_services = AsyncMock()

        with pytest.raises(RuntimeError, match="transient failure"):
            await mgr.acquire_slot()

        # Second attempt should succeed and reuse the same slot
        slot = await mgr.acquire_slot()
        assert slot.index == 0
        assert slot.in_use is True


# ---------------------------------------------------------------------------
# Concurrent slot acquisition
# ---------------------------------------------------------------------------


class TestConcurrentAcquisition:
    @pytest.mark.asyncio
    async def test_concurrent_acquires_get_different_slots(self):
        mgr = QuicksandBrowserManager(pool_size=3)
        mgr._slots = [
            BrowserSlot(
                index=i,
                display=99 + i,
                cdp_guest_port=9222 + i,
                cdp_host_port=40000 + i,
                novnc_guest_port=6080 + i,
                novnc_host_port=41000 + i,
            )
            for i in range(3)
        ]
        mgr._started = True
        mgr._sandbox = AsyncMock()
        mgr._start_slot_services = AsyncMock()

        # Acquire all 3 slots concurrently
        slots = await asyncio.gather(
            mgr.acquire_slot(),
            mgr.acquire_slot(),
            mgr.acquire_slot(),
        )

        indices = {s.index for s in slots}
        assert indices == {0, 1, 2}, f"Expected 3 unique slots, got indices {indices}"

    @pytest.mark.asyncio
    async def test_concurrent_acquire_excess_raises(self):
        """Excess concurrent acquires raise instead of queueing (issue #587).

        Exactly ``pool_size`` concurrent acquires succeed; the rest raise
        ``BrowserSlotPoolFullError``.
        """
        mgr = QuicksandBrowserManager(pool_size=2)
        mgr._slots = [
            BrowserSlot(
                index=i,
                display=99 + i,
                cdp_guest_port=9222 + i,
                cdp_host_port=40000 + i,
                novnc_guest_port=6080 + i,
                novnc_host_port=41000 + i,
            )
            for i in range(2)
        ]
        mgr._started = True
        mgr._sandbox = AsyncMock()
        mgr._start_slot_services = AsyncMock()
        mgr._stop_slot_services = AsyncMock()

        results = await asyncio.gather(
            mgr.acquire_slot(),
            mgr.acquire_slot(),
            mgr.acquire_slot(),
            return_exceptions=True,
        )
        successes = [r for r in results if isinstance(r, BrowserSlot)]
        failures = [r for r in results if isinstance(r, BrowserSlotPoolFullError)]
        assert len(successes) == 2
        assert len(failures) == 1


# ---------------------------------------------------------------------------
# Ad-block host resolver rules
# ---------------------------------------------------------------------------


class TestBuildHostResolverRules:
    """Unit tests for ``_build_host_resolver_rules``.

    The returned string is interpolated into Chromium's
    ``--host-resolver-rules`` flag, so format mistakes (trailing comma,
    missing wildcard, swapped order) silently disable the blocklist.
    """

    def test_empty_input_returns_empty_string(self):
        assert _build_host_resolver_rules(()) == ""

    def test_single_domain_emits_bare_then_wildcard(self):
        rules = _build_host_resolver_rules(("example.com",))
        # Order matters: bare rule must precede the wildcard for the
        # comment in the source to stay accurate.
        assert rules == "MAP example.com ~NOTFOUND,MAP *.example.com ~NOTFOUND"

    def test_multiple_domains_preserve_input_order(self):
        rules = _build_host_resolver_rules(("a.com", "b.net"))
        parts = rules.split(",")
        assert parts == [
            "MAP a.com ~NOTFOUND",
            "MAP *.a.com ~NOTFOUND",
            "MAP b.net ~NOTFOUND",
            "MAP *.b.net ~NOTFOUND",
        ]

    def test_no_trailing_comma(self):
        rules = _build_host_resolver_rules(("a.com", "b.net"))
        assert not rules.endswith(",")
        assert ",," not in rules  # no empty entries either

    def test_each_domain_produces_two_rules(self):
        domains = ("a.com", "b.net", "c.org")
        rules = _build_host_resolver_rules(domains)
        assert len(rules.split(",")) == 2 * len(domains)

    def test_googletagmanager_intentionally_not_blocked(self):
        # GTM is sometimes used to inject anti-bot sensors (PerimeterX,
        # DataDome, Akamai Bot Manager). Blocking it can trip hard
        # bot-detection at login. If this test fails, see the comment
        # block above _AD_BLOCK_DOMAINS in quicksand_browser_manager.py.
        assert "googletagmanager.com" not in _AD_BLOCK_DOMAINS

    def test_blocklist_contains_known_high_volume_domains(self):
        # Sanity check that the curated list still includes the most
        # impactful domains. If we ever accidentally truncate the tuple,
        # this test catches it.
        for d in ("doubleclick.net", "googlesyndication.com", "facebook.net"):
            assert d in _AD_BLOCK_DOMAINS


# ---------------------------------------------------------------------------
# get_browser_resource with quicksand_manager
# ---------------------------------------------------------------------------


class TestGetBrowserResourceQuicksand:
    def test_returns_quicksand_browser_when_manager_provided(self):
        from magentic_ui.tools.playwright.browser.utils import get_browser_resource
        from magentic_ui.tools.playwright.browser.quicksand_playwright_browser import (
            QuicksandPlaywrightBrowser,
        )

        mgr = QuicksandBrowserManager()
        browser, novnc_port, pw_port = get_browser_resource(
            bind_dir=Path("/tmp"),
            quicksand_manager=mgr,
        )

        assert isinstance(browser, QuicksandPlaywrightBrowser)
        assert novnc_port == -1
        assert pw_port == -1

    def test_returns_local_browser_when_no_manager(self):
        from magentic_ui.tools.playwright.browser.utils import get_browser_resource
        from magentic_ui.tools.playwright.browser.local_playwright_browser import (
            LocalPlaywrightBrowser,
        )

        browser, _, _ = get_browser_resource(
            bind_dir=Path("/tmp"),
            local=True,
            quicksand_manager=None,
        )

        assert isinstance(browser, LocalPlaywrightBrowser)


# ---------------------------------------------------------------------------
# normalize_host_path
# ---------------------------------------------------------------------------


class TestNormalizeHostPath:
    def test_unix_path_unchanged(self):
        assert normalize_host_path("/home/user/Downloads") == "/home/user/Downloads"

    @pytest.mark.skipif(not _is_wsl(), reason="WSL-only: Windows path conversion")
    def test_windows_drive_letter(self):
        result = normalize_host_path("C:\\Users\\demo\\Downloads")
        assert result == "/mnt/c/Users/demo/Downloads"

    @pytest.mark.skipif(not _is_wsl(), reason="WSL-only: Windows path conversion")
    def test_windows_forward_slashes(self):
        result = normalize_host_path("D:/Data/Photos")
        assert result == "/mnt/d/Data/Photos"

    @pytest.mark.skipif(not _is_wsl(), reason="WSL-only: Windows path conversion")
    def test_lowercase_drive(self):
        result = normalize_host_path("e:\\projects")
        assert result == "/mnt/e/projects"

    def test_non_matching_path_returned_as_is(self):
        result = normalize_host_path("relative/path/file.txt")
        assert result == "relative/path/file.txt"


# ---------------------------------------------------------------------------
# Input validation (session_id, dir_name)
# ---------------------------------------------------------------------------


class TestValidation:
    def test_valid_session_id(self):
        _validate_session_id("abc-123_XYZ")  # should not raise

    def test_session_id_rejects_semicolon(self):
        with pytest.raises(ValueError, match="Invalid session_id"):
            _validate_session_id("abc; rm -rf /")

    def test_session_id_rejects_spaces(self):
        with pytest.raises(ValueError, match="Invalid session_id"):
            _validate_session_id("abc def")

    def test_session_id_rejects_empty(self):
        with pytest.raises(ValueError, match="Invalid session_id"):
            _validate_session_id("")

    def test_valid_dir_name(self):
        _validate_dir_name("Downloads", "/home/user/Downloads")  # should not raise

    def test_dir_name_with_spaces(self):
        _validate_dir_name("My Photos", "/home/user/My Photos")  # should not raise

    def test_dir_name_rejects_empty(self):
        with pytest.raises(ValueError, match="Empty directory name"):
            _validate_dir_name("", "/")

    def test_dir_name_rejects_semicolon(self):
        with pytest.raises(ValueError, match="Unsafe directory name"):
            _validate_dir_name("foo;id", "/tmp/foo;id")

    def test_dir_name_rejects_dot(self):
        with pytest.raises(ValueError, match="path traversal"):
            _validate_dir_name(".", "/tmp/.")

    def test_dir_name_rejects_dotdot(self):
        with pytest.raises(ValueError, match="path traversal"):
            _validate_dir_name("..", "/tmp/..")


class TestExtractDirBasename:
    def test_simple_unix(self):
        assert extract_dir_basename("/home/user/Photos") == "Photos"

    def test_trailing_slash(self):
        assert extract_dir_basename("/home/user/Photos/") == "Photos"

    def test_windows_path(self):
        assert extract_dir_basename("C:\\Users\\demo\\Downloads") == "Downloads"

    def test_dotdot_resolved(self):
        # /home/user/Photos/.. normalizes to /home/user → basename "user"
        assert extract_dir_basename("/home/user/Photos/..") == "user"

    def test_dot_resolved(self):
        # /home/user/. normalizes to /home/user → basename "user"
        assert extract_dir_basename("/home/user/.") == "user"

    def test_root_returns_empty(self):
        # Edge case: / normalizes to / → basename ""
        assert extract_dir_basename("/") == ""


class TestValidateHostPath:
    @pytest.fixture
    def fake_home(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
        """Return a temp directory that ``validate_host_path`` treats as
        the user home (the root mounts must live under)."""
        home = tmp_path / "home"
        home.mkdir()
        home = home.resolve()
        monkeypatch.setattr(
            "magentic_ui.sandbox._path_validator.get_home",
            lambda: home,
        )
        return home

    def test_valid_directory(self, fake_home: Path):
        d = fake_home / "photos"
        d.mkdir()
        result = validate_host_path(str(d))
        assert result == str(d)

    def test_tilde_expands_against_get_home(self, fake_home: Path):
        # ``~`` must expand against get_home() (the containment root),
        # not os.path.expanduser (which uses the Linux $HOME on WSL and
        # would land outside the fake home, rejecting a valid path).
        d = fake_home / "photos"
        d.mkdir()
        result = validate_host_path("~/photos")
        assert result == str(d)

    def test_rejects_nonexistent(self, fake_home: Path):
        with pytest.raises(ValueError, match="does not exist"):
            validate_host_path(str(fake_home / "nope"))

    def test_rejects_file(self, fake_home: Path):
        f = fake_home / "file.txt"
        f.write_text("hi")
        with pytest.raises(ValueError, match="not a directory"):
            validate_host_path(str(f))

    def test_rejects_ssh_dir(self, fake_home: Path):
        ssh = fake_home / ".ssh"
        ssh.mkdir()
        with pytest.raises(ValueError, match="sensitive location"):
            validate_host_path(str(ssh))

    def test_rejects_subdir_of_ssh(self, fake_home: Path):
        keys = fake_home / ".ssh" / "keys"
        keys.mkdir(parents=True)
        with pytest.raises(ValueError, match="sensitive location"):
            validate_host_path(str(keys))

    def test_rejects_outside_home(self, fake_home: Path):
        # /etc lives outside the user-home root; the containment check
        # rejects it before the denylist gets a turn.
        with pytest.raises(ValueError, match="not under user home"):
            validate_host_path("/etc")

    def test_rejects_symlink_to_denied(self, fake_home: Path):
        ssh = fake_home / ".ssh"
        ssh.mkdir()
        # Symlink lives inside home so containment passes; resolution
        # then lands on ``.ssh`` which the denylist catches.
        innocent = fake_home / "innocent"
        innocent.symlink_to(ssh)
        with pytest.raises(ValueError, match="sensitive location"):
            validate_host_path(str(innocent))

    def test_rejects_symlink_escaping_home(
        self, fake_home: Path, tmp_path: Path
    ) -> None:
        # Symlink inside home pointing to a target outside home — passes
        # the initial string containment but ``resolve`` then escapes,
        # and the re-validation step catches it.
        outside = tmp_path / "outside"
        outside.mkdir()
        escape = fake_home / "escape"
        escape.symlink_to(outside)
        with pytest.raises(ValueError, match="escapes home via symlink"):
            validate_host_path(str(escape))
