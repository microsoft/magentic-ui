"""Browser slot pool manager for Quicksand VM.

Manages a pool of browser slots inside a Quicksand VM. Each slot provides
a dedicated Xvfb display, Chromium instance with CDP, x11vnc, and noVNC
proxy. The VM lifecycle is owned by :class:`QuicksandSandbox` — this
manager only handles browser-specific concerns.

Chromium is launched with ``--user-data-dir`` for full persistent profiles
(cookies, IndexedDB, cache, service workers, history). Each slot gets a
copy-on-acquire snapshot of the master profile directory; on release the
slot profile is merged back (last-writer-wins).
"""

from __future__ import annotations

import asyncio
import secrets
import shlex
import socket
from dataclasses import dataclass
from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from ....sandbox._quicksand import QuicksandSandbox


# ---------------------------------------------------------------------------
# Slot dataclass
# ---------------------------------------------------------------------------


@dataclass
class BrowserSlot:
    """A pre-allocated slot in the port pool."""

    index: int
    display: int  # X11 display number (:99, :100, ...)
    cdp_guest_port: int  # Chromium CDP port inside VM
    cdp_host_port: int  # Chromium CDP port on host
    novnc_guest_port: int
    novnc_host_port: int
    in_use: bool = False
    # Per-acquire RFB password for x11vnc; regenerated each time the slot
    # starts and cleared on release. Passed to the frontend via the
    # browser_address WS message so noVNC can authenticate silently.
    vnc_password: str = ""


class BrowserSlotPoolFullError(RuntimeError):
    """Raised by ``acquire_slot`` when every slot is in use."""


# ---------------------------------------------------------------------------
# Profile directories inside VM
# ---------------------------------------------------------------------------

_MASTER_PROFILE_DIR = "/profiles/master"
_SLOT_PROFILE_DIR = "/profiles/slot-{index}"


# ---------------------------------------------------------------------------
# Ad / tracker domain blocklist
# ---------------------------------------------------------------------------
#
# Domains we map to ~NOTFOUND via Chromium's --host-resolver-rules. This
# stops the renderer from creating iframes for these origins entirely:
# DNS resolution fails fast, no connection attempt, no tab process spawn.
#
# Concrete impact observed: a single CPU benchmark page (cpu-monkey.com)
# was opening 282 CDP targets — only ~3 were actual content; the rest
# were ad / analytics / programmatic-bidding iframes hosted on these
# very domains. With this list applied, expect the same page to settle
# at 20-50 targets and chromium's main thread to stay responsive.
#
# Curation principles (chosen for low maintenance):
#   1. Big, stable companies — Google, Meta, Amazon, Microsoft (Xandr),
#      Magnite (Rubicon), Index Exchange, etc. These names persist for
#      years even after acquisitions; old domains keep redirecting.
#   2. Pure ad/tracking — never on the critical path for login,
#      payments, captcha, fonts, or CSS/SRI checks.
#   3. High prevalence (per WhoTracks.me) — block these = block most
#      of the volume across the web, not the long tail.
#   4. CPU-heavy specifically — session replay tools (Hotjar, FullStory)
#      install MutationObservers + listen on every event; they're the
#      single worst class for chromium main-thread responsiveness.
#
# Notably DO NOT block (these break legitimate functionality):
#   - google.com / gstatic.com / googleapis.com / fonts.googleapis.com
#     (search consent, fonts, maps, recaptcha API)
#   - youtube.com (legitimate embeds)
#   - facebook.com / twitter.com main domains (OAuth callbacks)
#   - cloudflare.com / cdn networks (the actual content)
#   - googletagmanager.com — GTM is sometimes used to inject anti-bot
#     sensors (PerimeterX, DataDome, Akamai Bot Manager). Blocking it
#     can make those scripts fail to load and trip hard bot-detection
#     blocks or CAPTCHAs at login. We rely on blocking the downstream
#     ad/analytics endpoints (doubleclick, google-analytics, etc.) to
#     recover most of the perf benefit without the breakage risk.
#
# Wildcard `*.{d}` automatically covers all subdomains, so we don't list
# subdomains explicitly (e.g. `pagead2.googlesyndication.com` is already
# matched by the rule for `googlesyndication.com`).
#
# Maintenance: review every 6-12 months. Add domains only when a
# specific site is observed bogging down the agent — inspect the
# slot's CDP `/json` endpoint to find the offender.
_AD_BLOCK_DOMAINS = (
    # Google ad serving — most prevalent ad infrastructure on the web
    "doubleclick.net",  # Google Marketing Platform (~18% of all sites)
    "googlesyndication.com",  # AdSense — covers pagead2/tpc subdomains
    "googleadservices.com",
    "google-analytics.com",
    "adtrafficquality.google",  # Google Ad attestation
    # Other tier-1 pixels
    "facebook.net",  # FB Pixel (connect.facebook.net etc)
    "scorecardresearch.com",  # Comscore — the actual tracking endpoint
    "quantserve.com",  # Quantcast
    # Amazon ad system
    "amazon-adsystem.com",
    # Major RTB / ad exchanges (companies that survived recent consolidation)
    "adnxs.com",  # Microsoft Xandr (formerly AppNexus)
    "rubiconproject.com",  # Magnite (Rubicon Project)
    "pubmatic.com",
    "openx.net",
    "criteo.com",  # Criteo uses both TLDs
    "criteo.net",
    "casalemedia.com",  # Index Exchange
    "adsrvr.org",  # The Trade Desk (largest indep DSP)
    # Session replay / heatmaps — CPU killers
    # These install MutationObservers + per-event listeners. Devastating
    # to chromium main thread on long agent sessions.
    "hotjar.com",
    "fullstory.com",
    "mouseflow.com",
    # Ad verification / viewability measurement
    "moatads.com",  # Oracle Moat / Equativ
    "doubleverify.com",
    "adsafeprotected.com",  # IAS (Integral Ad Science)
    # Content-recommendation widgets — load heavy ad-laden iframes
    "taboola.com",
    "outbrain.com",
    # Client-side experimentation / CDP — beacon-heavy
    "optimizely.com",
    "segment.io",  # Customer data platform
    # Native ad networks observed in real agent sessions
    "dianomi.com",
    "blismedia.com",
)


def _build_host_resolver_rules(domains: tuple[str, ...]) -> str:
    """Build the value of Chromium's ``--host-resolver-rules`` flag.

    For each domain we add two MAP rules: the bare domain and a wildcard
    for every subdomain. Both resolve to ``~NOTFOUND``, which causes
    DNS lookup to fail in Chromium's net stack — connection is never
    attempted, so there's no socket timeout, no retry, no tab process.
    """
    rules: list[str] = []
    for d in domains:
        rules.append(f"MAP {d} ~NOTFOUND")
        rules.append(f"MAP *.{d} ~NOTFOUND")
    return ",".join(rules)


_HOST_RESOLVER_RULES = _build_host_resolver_rules(_AD_BLOCK_DOMAINS)
# Note: _AD_BLOCK_DOMAINS is a compile-time constant, so the assembled
# rules string is safe to interpolate into the chromium shell command
# below. If this list ever becomes user-configurable, wrap the value in
# shlex.quote() to defend against shell injection.


def _find_free_port() -> int:
    """Find an available port on the host."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


# ---------------------------------------------------------------------------
# Manager
# ---------------------------------------------------------------------------


class QuicksandBrowserManager:
    """Manages a pool of browser slots inside a Quicksand VM.

    The VM lifecycle is owned by the injected ``QuicksandSandbox``.
    This manager only handles slot allocation, per-slot browser services
    (Xvfb, x11vnc, noVNC, Chromium, socat), and profile management.

    Args:
        sandbox: An entered QuicksandSandbox instance.
        pool_size: Number of concurrent browser slots.
    """

    def __init__(
        self,
        sandbox: QuicksandSandbox | None = None,
        pool_size: int = 5,
    ) -> None:
        self._sandbox: QuicksandSandbox = sandbox  # type: ignore[assignment]  # set via .sandbox property before start()
        self._pool_size = pool_size
        self._slot_available = asyncio.Condition()
        self._started = False

        # Allocate ports upfront so they can be passed to QuicksandSandbox
        # before VM boot (port forwards must be set at QEMU startup).
        self._slots: list[BrowserSlot] = []
        for i in range(pool_size):
            cdp_guest = 9222 + i
            novnc_guest = 6080 + i
            cdp_host = _find_free_port()
            novnc_host = _find_free_port()
            self._slots.append(
                BrowserSlot(
                    index=i,
                    display=99 + i,
                    cdp_guest_port=cdp_guest,
                    cdp_host_port=cdp_host,
                    novnc_guest_port=novnc_guest,
                    novnc_host_port=novnc_host,
                )
            )

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def sandbox(self) -> QuicksandSandbox:
        """The underlying sandbox instance."""
        return self._sandbox

    @sandbox.setter
    def sandbox(self, value: QuicksandSandbox) -> None:
        """Set the sandbox instance (before start)."""
        self._sandbox = value

    @property
    def is_ready(self) -> bool:
        """Whether the manager is started and ready to accept slots."""
        return self._started

    # ------------------------------------------------------------------
    # Startup / Shutdown
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Mark manager as ready.

        The VM must already be running (sandbox.__aenter__ called).
        Ports are allocated in __init__ so they can be passed to sandbox.
        """
        if self._started:
            return
        self._started = True
        logger.info(f"QuicksandBrowserManager ready: {self._pool_size} slots")

    async def stop(self) -> None:
        """Release all in-use slots."""
        if not self._started:
            return

        for slot in self._slots:
            if slot.in_use:
                await self._stop_slot_services(slot)
                slot.in_use = False

        self._started = False
        logger.info("QuicksandBrowserManager stopped")

    @property
    def port_forwards(self) -> list[tuple[int, int]]:
        """Port forwards needed for all slots (pass to QuicksandSandbox)."""
        forwards: list[tuple[int, int]] = []
        for slot in self._slots:
            forwards.extend(
                [
                    (slot.cdp_host_port, slot.cdp_guest_port),
                    (slot.novnc_host_port, slot.novnc_guest_port),
                ]
            )
        return forwards

    # ------------------------------------------------------------------
    # Slot management
    # ------------------------------------------------------------------

    async def acquire_slot(self) -> BrowserSlot:
        """Claim a slot from the pool and start services inside the VM.

        Raises ``BrowserSlotPoolFullError`` when every slot is in use.
        """
        if not self._started:
            raise RuntimeError(
                "QuicksandBrowserManager has not been started. "
                "Call 'start()' before acquiring a slot."
            )
        async with self._slot_available:
            slot = next((s for s in self._slots if not s.in_use), None)
            if slot is None:
                raise BrowserSlotPoolFullError(
                    f"All {self._pool_size} live browser slots are in use"
                )
            slot.in_use = True

        try:
            await self._start_slot_services(slot)
        except Exception:
            try:
                await self._stop_slot_services(slot)
            except Exception:
                pass
            async with self._slot_available:
                slot.in_use = False
                self._slot_available.notify()
            raise
        return slot

    async def release_slot(self, slot: BrowserSlot) -> None:
        """Stop services, merge profile back, and return the slot to the pool."""
        try:
            await self._stop_slot_services(slot)
        except Exception:
            logger.exception(f"Failed to stop services for slot {slot.index}")
        finally:
            async with self._slot_available:
                slot.in_use = False
                self._slot_available.notify()
            logger.info(f"Slot {slot.index} released")

    # ------------------------------------------------------------------
    # Per-slot services
    # ------------------------------------------------------------------

    async def _start_slot_services(self, slot: BrowserSlot) -> None:
        """Start Xvfb, x11vnc, noVNC proxy, and Chromium with CDP for a slot."""
        sb = self._sandbox
        d = slot.display
        slot_profile = _SLOT_PROFILE_DIR.format(index=slot.index)

        logger.info(
            f"Starting services for slot {slot.index} "
            f"(display=:{d}, cdp={slot.cdp_guest_port}, "
            f"novnc={slot.novnc_guest_port})"
        )

        # Copy master profile to slot (copy-on-acquire)
        await sb.execute(
            f"mkdir -p {slot_profile} && rsync -a --delete {_MASTER_PROFILE_DIR}/ {slot_profile}/"
        )

        # Xvfb
        await sb.execute(
            f"nohup Xvfb :{d} -screen 0 1440x900x24 -ac -nolisten tcp > /dev/null 2>&1 &"
        )
        await asyncio.sleep(0.5)

        # X11 setup
        await sb.execute(f'DISPLAY=:{d} xsetroot -solid "#000000" 2>/dev/null || true')

        # Clipboard bridge
        await sb.execute(f"DISPLAY=:{d} autocutsel -s CLIPBOARD -fork")
        await sb.execute(f"DISPLAY=:{d} autocutsel -s PRIMARY -fork")

        # VNC server (internal only — noVNC proxies to it). Per-acquire
        # RFB password gates incoming connections; the frontend receives
        # it via the browser_address WS message so noVNC authenticates
        # silently.
        slot.vnc_password = secrets.token_urlsafe(16)
        pw_file = f"/tmp/x11vnc-slot-{slot.index}.pw"
        quoted_pw_file = shlex.quote(pw_file)
        await sb.execute(
            f"umask 0077 && printf '%s\\n' {shlex.quote(slot.vnc_password)} > {quoted_pw_file}"
        )
        vnc_port = 5900 + slot.index
        await sb.execute(
            f"nohup x11vnc -display :{d} -forever -shared "
            f"-rfbport {vnc_port} -passwdfile {quoted_pw_file} -listen 127.0.0.1 "
            f"-geometry 1440x900 -scale 1:1 -xkb "
            f"> /dev/null 2>&1 &"
        )
        await asyncio.sleep(0.5)

        # noVNC proxy (guest-accessible port → internal VNC)
        await sb.execute(
            f"nohup websockify --web /usr/share/novnc "
            f"{slot.novnc_guest_port} localhost:{vnc_port} "
            f"> /dev/null 2>&1 &"
        )

        # Chromium (pre-installed and symlinked by quicksand-cua)
        # Resource-saving flags for in-VM operation:
        #   --disable-dev-shm-usage: avoid /dev/shm tmpfs pressure (puppeteer/playwright standard for VM/container)
        #   --disable-features: turn off BFCache (extra renderer memory), Translate, MediaRouter, OptimizationHints, AcceptCHFrame
        #     (these match puppeteer's default disabled feature set)
        #   --disable-background-networking, --disable-component-update: stop idle background traffic
        #   --disable-renderer-backgrounding, --disable-backgrounding-occluded-windows:
        #       agent watches a "background" tab; don't let chromium throttle it
        #   --mute-audio: agent never needs sound
        #   --disable-extensions, --disable-default-apps: belt-and-suspenders, no extras loaded
        #   --host-resolver-rules: block known ad/tracker domains at DNS level
        #       (see _AD_BLOCK_DOMAINS for rationale and inclusion criteria)
        chromium_bin = "chromium"
        internal_cdp_port = 19222 + slot.index
        await sb.execute(
            f"DISPLAY=:{d} nohup {chromium_bin} "
            f"--no-sandbox "
            f"--user-data-dir={slot_profile} "
            f"--remote-debugging-port={internal_cdp_port} "
            f"--disable-blink-features=AutomationControlled "
            f"--disable-dev-shm-usage "
            f"--disable-features=Translate,BackForwardCache,MediaRouter,OptimizationHints,AcceptCHFrame "
            f"--disable-background-networking "
            f"--disable-component-update "
            f"--disable-default-apps "
            f"--disable-extensions "
            f"--disable-renderer-backgrounding "
            f"--disable-backgrounding-occluded-windows "
            f"--disable-background-timer-throttling "
            f"--mute-audio "
            f"--host-resolver-rules='{_HOST_RESOLVER_RULES}' "
            f"--start-maximized --window-size=1440,900 --window-position=0,0 "
            f"--no-first-run --disable-infobars --no-default-browser-check "
            f"--disable-session-crashed-bubble --noerrdialogs "
            f"--no-restore-session-state "
            f"--force-device-scale-factor=1.0 "
            f"> /tmp/chromium-slot-{slot.index}.log 2>&1 &"
        )

        await asyncio.sleep(3)

        # Verify Chromium is running
        ps_result = await sb.execute(
            f"pgrep -f 'remote-debugging-port={internal_cdp_port}' || echo 'NOT_RUNNING'"
        )
        if "NOT_RUNNING" in ps_result.stdout:
            log_result = await sb.execute(
                f"cat /tmp/chromium-slot-{slot.index}.log 2>/dev/null | tail -50"
            )
            logger.error(
                f"Slot {slot.index}: Chromium is NOT running!\n"
                f"Log output:\n{log_result.stdout}"
            )
            raise RuntimeError(
                f"Chromium failed to start for slot {slot.index}. Check logs above."
            )

        # socat relay: 0.0.0.0:CDP_GUEST_PORT → 127.0.0.1:INTERNAL_CDP_PORT
        # Chromium only binds CDP to loopback; SLIRP traffic enters via NIC.
        await sb.execute(
            f"nohup socat TCP-LISTEN:{slot.cdp_guest_port},fork,bind=0.0.0.0,reuseaddr "
            f"TCP:127.0.0.1:{internal_cdp_port} "
            f"> /dev/null 2>&1 &"
        )
        await asyncio.sleep(0.5)

        logger.info(
            f"Slot {slot.index}: chromium PID={ps_result.stdout.strip()}, "
            f"CDP {internal_cdp_port} -> socat 0.0.0.0:{slot.cdp_guest_port}"
        )

    async def _stop_slot_services(self, slot: BrowserSlot) -> None:
        """Kill all processes associated with a slot, then merge profile back."""
        sb = self._sandbox
        d = slot.display
        slot_profile = _SLOT_PROFILE_DIR.format(index=slot.index)
        internal_cdp_port = 19222 + slot.index
        vnc_port = 5900 + slot.index

        logger.info(f"Stopping services for slot {slot.index} (display=:{d})")

        # Kill socat relay
        await sb.execute(f"fuser -k {slot.cdp_guest_port}/tcp 2>/dev/null || true")

        # Graceful chromium shutdown
        await sb.execute(
            f'pkill -f "remote-debugging-port={internal_cdp_port}" 2>/dev/null; '
            f"for i in $(seq 1 10); do "
            f'  pgrep -f "remote-debugging-port={internal_cdp_port}" >/dev/null 2>&1 || break; '
            f"  sleep 0.5; "
            f"done; "
            f'pkill -9 -f "remote-debugging-port={internal_cdp_port}" 2>/dev/null || true'
        )

        # Merge slot profile back to master (last-writer-wins)
        try:
            await sb.execute(
                f"if [ -d {slot_profile} ]; then "
                f"  rsync -a --delete {slot_profile}/ {_MASTER_PROFILE_DIR}/; "
                f"fi"
            )
        except Exception as e:
            logger.warning(f"Failed to merge slot {slot.index} profile back: {e}")

        # Kill remaining processes
        commands = [
            f"fuser -k {slot.novnc_guest_port}/tcp 2>/dev/null || true",
            f"fuser -k {vnc_port}/tcp 2>/dev/null || true",
            f"pkill -f 'Xvfb :{d}' 2>/dev/null || true",
            # Best-effort cleanup of the per-slot VNC password file. VM
            # teardown wipes /tmp anyway; this just narrows the window.
            f"rm -f /tmp/x11vnc-slot-{slot.index}.pw",
        ]
        for cmd in commands:
            try:
                await sb.execute(cmd)
            except Exception:
                pass
        slot.vnc_password = ""
