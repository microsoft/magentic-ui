"""Pretty console formatter for magentic-ui CLI with improved visual formatting."""

from __future__ import annotations

import json
import logging
import re
import sys
import textwrap
import warnings
from typing import Any, AsyncGenerator, Dict, Optional

from autogen_agentchat.base import Response, TaskResult
from autogen_agentchat.messages import BaseAgentEvent, BaseChatMessage

# ╭────────────────────────────────────────────────────────────────────────────╮
# │  Terminal colours / styles - 7‑bit ANSI so they work everywhere            │
# ╰────────────────────────────────────────────────────────────────────────────╯
BOLD = "\033[1m"
RESET = "\033[0m"
BLUE = "\033[34m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
CYAN = "\033[36m"
MAGENTA = "\033[35m"
RED = "\033[31m"
WHITE_BG = "\033[47m"
BLACK_TEXT = "\033[30m"
UNDERLINE = "\033[4m"

# ╭────────────────────────────────────────────────────────────────────────────╮
# │  Common INFO patterns pre‑compiled for speed                               │
# ╰────────────────────────────────────────────────────────────────────────────╯
INFO_REGEX = re.compile(
    r"|".join(
        [
            r"Task received:",
            r"Analyzing",
            r"Submitting",
            r"Reviewing",
            r"checks passed",
            r"Deciding which agent",
            r"Received task:",
            r"Searching for",
            r"Processing",
            r"Executing",
            r"Reading file",
            r"Writing to",
            r"Running",
            r"Starting",
            r"Completed",
            r"Looking up",
            r"Loading",
            r"Generating",
            r"Creating",
            r"Downloading",
            r"Installing",
            r"Checking",
            r"Fetching",
            r"Exploring",
            r"Building",
            r"Setting up",
            r"Finding",
            r"Identifying",
            r"Testing",
            r"Compiling",
            r"Validating",
            r"Cloning",
        ]
    )
)


# ╭────────────────────────────────────────────────────────────────────────────╮
# │  Helper utilities                                                          │
# ╰────────────────────────────────────────────────────────────────────────────╯
def _terminal_width(fallback: int = 100) -> int:
    """Return terminal width minus a 10‑column safety margin."""
    try:
        import shutil

        return max(20, shutil.get_terminal_size().columns - 10)
    except Exception:
        return fallback


def try_parse_json(raw: str) -> tuple[bool, Any]:
    """Lightweight JSON detector – avoids `json.loads` when blatantly not JSON."""
    raw = raw.strip()
    if not (raw.startswith("{") and raw.endswith("}")) and not (
        raw.startswith("[") and raw.endswith("]")
    ):
        return False, None
    try:
        return True, json.loads(raw)
    except (ValueError, TypeError):
        return False, None


# ╭────────────────────────────────────────────────────────────────────────────╮
# │  Pretty‑printers                                                           │
# ╰────────────────────────────────────────────────────────────────────────────╯


def format_info_line(msg: str) -> str:
    return f"{BOLD}{GREEN}[INFO]{RESET} {UNDERLINE}{msg}{RESET}"


def is_info_message(msg: str) -> bool:
    if INFO_REGEX.search(msg):
        return True
    # Verb in present‑participle at start ("Loading models…")
    return bool(re.match(r"^\s*[A-Z][a-z]+ing\b", msg))


# ╭────────────────────────────────────────────────────────────────────────────╮
# │  Agent‑specific colour selection (deterministic but cheap)                 │
# ╰────────────────────────────────────────────────────────────────────────────╯
_AGENT_COLORS = {
    "orchestrator": CYAN,
    "coder_agent": MAGENTA,
    "coder": MAGENTA,
    "reviewer": GREEN,
    "web_surfer": BLUE,
    "file_surfer": YELLOW,
    "user_proxy": GREEN,
    "azure_reasoning_agent": RED,
}
_COLOR_POOL = [BLUE, GREEN, YELLOW, CYAN, MAGENTA]


def agent_color(name: str) -> str:
    ln = name.lower()
    for key, col in _AGENT_COLORS.items():
        if key in ln:
            return col
    return _COLOR_POOL[hash(name) % len(_COLOR_POOL)]


# ╭────────────────────────────────────────────────────────────────────────────╮
# │  Header & transition boxes                                                 │
# ╰────────────────────────────────────────────────────────────────────────────╯
def header_box(agent: str) -> str:
    """Return a symmetric ASCII box with the agent name centred."""
    INNER = 24  # number of "═" characters (and usable chars in mid line)

    colour = agent_color(agent)
    text = agent.upper()[:INNER]  # truncate if the name is longer than the box
    pad = INNER - len(text)
    left, right = pad // 2, pad - pad // 2

    top = f"{BOLD}{colour}╔{'═' * INNER}╗"
    mid = f"║{' ' * left}{text}{RESET}{colour}{' ' * right}║"
    bot = f"╚{'═' * INNER}╝{RESET}"

    return f"\n{top}\n{mid}\n{bot}\n"


def transition_line(prev: str, curr: str) -> str:
    return (
        f"{BOLD}{agent_color(prev)}{prev.upper()}{RESET}  "
        f"{BOLD}{YELLOW}━━━━▶{RESET}  "
        f"{BOLD}{agent_color(curr)}{curr.upper()}{RESET}"
    )


# ╭────────────────────────────────────────────────────────────────────────────╮
# │  JSON pretty printer                                                       │
# ╰────────────────────────────────────────────────────────────────────────────╯


def pretty_print_json(raw: str, colour: str) -> bool:
    ok, obj = try_parse_json(raw)
    if not ok or obj in ([], {}):
        return False

    width = _terminal_width()
    left = f"{colour}┃{RESET} "
    indent_json = json.dumps(obj, indent=2, ensure_ascii=False)
    indent_json = re.sub(r'"([^"\\]+)":', rf'"{BOLD}\1{RESET}":', indent_json)

    print()  # top spacer
    for line in indent_json.splitlines():
        if len(line) <= width - len(left):
            print(f"{left}{line}")
        else:  # wrap overly long line while preserving indent
            lead = len(line) - len(line.lstrip())
            body = line[lead:]
            for i, chunk in enumerate(
                textwrap.wrap(
                    body, width=width - len(left) - lead, break_long_words=False
                )
            ):
                prefix = " " * lead if i else ""
                print(f"{left}{prefix}{chunk}")
    print()  # bottom spacer
    return True


# ╭────────────────────────────────────────────────────────────────────────────╮
# │  Plan & step formatters                                                    │
# ╰────────────────────────────────────────────────────────────────────────────╯


def format_plan(obj: dict[str, Any], colour: str) -> None:
    width = _terminal_width()
    left = f"{colour}┃{RESET} "
    body_w = width - len(left)

    def _wrap(text: str, indent: int = 3):
        for ln in textwrap.wrap(text, body_w - indent):
            print(f"{left}{' ' * indent}{ln}")

    # Task / title
    if "task" in obj:
        print(f"{left}{BOLD}Task:{RESET} {obj['task']}")
    elif "title" in obj:
        print(f"{left}{BOLD}Plan:{RESET} {obj['title']}")

    # Summary
    if obj.get("plan_summary"):
        print()  # tail spacer
        print(f"{left}{BOLD}Plan Summary:{RESET}")
        _wrap(obj["plan_summary"])

    # Is this a user proxy interaction? (Check agent name)
    agent_name = obj.get("agent_name", "").lower()
    is_user_proxy = "user" in agent_name and "proxy" in agent_name

    # Steps
    steps: list[dict[str, Any]] = obj.get("steps", []) or []
    if steps:
        print(f"{left}\n{left}{BOLD}Steps:{RESET}")
        for i, step in enumerate(steps, 1):
            # Get step type and create indicator
            step_type = step.get("step_type", "") if isinstance(step, dict) else ""

            # Placeholder: if no step_type, default to PlanStep
            if not step_type and isinstance(step, dict):
                step_type = "PlanStep"

            # Shows the step type icon to Console
            type_indicator = ""
            if step_type == "PlanStep":
                type_indicator = f"{BOLD}{GREEN}[R]{RESET} "
            elif step_type == "SentinelPlanStep":
                type_indicator = f"{BOLD}{YELLOW}[S]{RESET} "

            # Shows the step title name to Console
            step_title = (
                step.get("title", step) if isinstance(step, dict) else str(step)
            )
            print(f"{left}\n{left}{BOLD}{i}. {type_indicator}{step_title}{RESET}")
            if isinstance(step, dict):
                if step.get("details"):
                    _wrap(step["details"], 5)
                if step.get("instruction"):
                    print(f"{left}{' ' * 5}{BOLD}Instruction:{RESET}")
                    _wrap(step["instruction"], 7)
                if step.get("progress_summary"):
                    print(f"{left}{' ' * 5}{BOLD}Progress:{RESET}")
                    _wrap(step["progress_summary"], 7)
                if step.get("agent_name"):
                    print(
                        f"{left}{' ' * 5}{BOLD}Agent:{RESET} {step['agent_name'].upper()}"
                    )
                # Show step type information if available
                if step_type:
                    type_name = (
                        "Regular Step" if step_type == "PlanStep" else "Sentinel Step"
                    )
                    print(f"{left}{' ' * 5}{BOLD}Type:{RESET} {type_name}")
                    if step_type == "SentinelPlanStep":
                        if step.get("counter"):
                            print(
                                f"{left}{' ' * 5}{BOLD}Counter:{RESET} {step['counter']}"
                            )
                        if step.get("sleep_duration"):
                            print(
                                f"{left}{' ' * 5}{BOLD}Sleep Duration:{RESET} {step['sleep_duration']}s"
                            )

        # Always show acceptance prompt for full plans
        print()  # tail spacer
        print(f"{BOLD}{YELLOW}Type 'accept' to proceed or describe changes:{RESET}")

    # Single‑step orchestrator JSON (title/index style)
    elif {"title", "index", "agent_name"}.issubset(obj):
        idx = obj["index"] + 1 if isinstance(obj.get("index"), int) else obj["index"]

        # Get step type and create indicator
        step_type = obj.get("step_type", "")

        # If no step_type, default to PlanStep
        if not step_type:
            step_type = "PlanStep"

        type_indicator = ""
        if step_type == "PlanStep":
            type_indicator = f"{BOLD}{GREEN}[R]{RESET} "
        elif step_type == "SentinelPlanStep":
            type_indicator = f"{BOLD}{YELLOW}[S]{RESET} "

        print(
            f"{left}{BOLD}Step:{RESET} {type_indicator}{idx}/{obj.get('plan_length', '?')}"
        )
        print(f"{left}{BOLD}Agent:{RESET} {obj['agent_name'].upper()}")

        # Show step type information if available
        if step_type:
            type_name = "Regular Step" if step_type == "PlanStep" else "Sentinel Step"
            print(f"{left}{BOLD}Type:{RESET} {type_name}")
            if step_type == "SentinelPlanStep":
                if obj.get("counter"):
                    print(f"{left}    {BOLD}Counter:{RESET} {obj['counter']}")
                if obj.get("sleep_duration"):
                    print(
                        f"{left}    {BOLD}Sleep Duration:{RESET} {obj['sleep_duration']}s"
                    )

        if obj.get("details"):
            print(f"{left}{BOLD}Details:{RESET}")
            _wrap(obj["details"])
        if obj.get("instruction"):
            print(f"{left}{BOLD}Instruction:{RESET}")
            _wrap(obj["instruction"])
        if obj.get("progress_summary"):
            print(f"{left}{BOLD}Progress:{RESET}")
            _wrap(obj["progress_summary"])

        print()  # tail spacer

        # Only show the prompt if this is a user proxy agent interaction
        if is_user_proxy:
            print(f"{BOLD}{YELLOW}Type 'accept' to proceed or describe changes:{RESET}")
    # If it's a full plan without steps, always show acceptance prompt
    elif "task" in obj or "plan_summary" in obj:
        print()  # tail spacer
        print(f"{BOLD}{YELLOW}Type 'accept' to proceed or describe changes:{RESET}")


def pretty_print_plan(raw: str, colour: str) -> bool:
    ok, obj = try_parse_json(raw)
    if not ok:
        return False
    if any(k in obj for k in ("task", "plan_summary", "steps", "title")):
        format_plan(obj, colour)
        return True
    return False


# Step formatter (simple schema: {step, content})
def try_format_step(raw: str, colour: str) -> bool:
    ok, obj = try_parse_json(raw)
    if not ok or not {"step", "content"}.issubset(obj):
        return False
    width = _terminal_width()
    title = obj.get("title", f"Step {obj['step']}")
    print(
        f"\n{BOLD}{colour}╔{'═' * (width - 4)}╗\n"
        f"║ {title:<{width - 6}}║\n"
        f"╚{'═' * (width - 4)}╝{RESET}\n"
    )
    print(f"{BOLD}{colour}┃{RESET} {obj['content']}\n")
    return True


# ╭────────────────────────────────────────────────────────────────────────────╮
# │  PrettyConsole coroutine - main entry point                                │
# ╰────────────────────────────────────────────────────────────────────────────╯
async def _PrettyConsole(
    stream: AsyncGenerator[Any, None],
    *,
    debug: bool = False,
    no_inline_images: bool = False,  # reserved for future use
    output_stats: bool = False,  # reserved for future use
) -> Any:
    current_agent: Optional[str] = None
    previous_agent: Optional[str] = None
    last_processed: Any = None

    # Quiet libraries unless debugging
    if not debug:
        warnings.filterwarnings("ignore")
        logging.disable(logging.CRITICAL)

    class _Gate:
        """Allow writes only when inside `process_message`."""

        def __init__(self, dbg: bool, flag: Dict[str, bool]):
            self.dbg, self.flag = dbg, flag

        def write(self, txt: str):
            if self.dbg or self.flag["open"]:
                if sys.__stdout__ is not None:
                    sys.__stdout__.write(txt)

        def flush(self):
            if sys.__stdout__ is not None:
                sys.__stdout__.flush()

    gate = {"open": False}
    sys.stdout = _Gate(debug, gate)
    sys.stderr = _Gate(debug, gate)
    sys.__stdout__ = sys.__stdout__  # keep a reference for raw writes

    async def process(msg: BaseChatMessage | BaseAgentEvent | TaskResult | Response):
        nonlocal current_agent, previous_agent, last_processed
        last_processed = msg
        gate["open"] = True

        try:
            # Chat message
            if isinstance(msg, BaseChatMessage):
                meta = getattr(msg, "metadata", {})
                if meta.get("internal") == "yes" and not debug:
                    return
                src = msg.source
                if src != current_agent:
                    previous_agent, current_agent = current_agent, src
                    if previous_agent:
                        print("\n" + transition_line(previous_agent, current_agent))
                    print(header_box(src))

                colour = agent_color(src)
                content = str(getattr(msg, "content", ""))

                if is_info_message(content):
                    print(format_info_line(content))
                elif pretty_print_plan(content, colour):
                    pass
                elif pretty_print_json(content, colour):
                    pass
                elif try_format_step(content, colour):
                    pass
                else:
                    width = _terminal_width()
                    left = f"{colour}┃{RESET} "
                    body_w = width - len(left)
                    for line in content.splitlines():
                        if not line.strip():
                            continue
                        if len(line) <= body_w:
                            print(f"{left}{line}")
                        else:
                            for chunk in textwrap.wrap(line, body_w):
                                print(f"{left}{chunk}")

            # Event message (non‑chat)
            elif isinstance(msg, BaseAgentEvent):
                if debug:
                    print(
                        f"{BOLD}{YELLOW}[EVENT]{RESET} "
                        f"{msg.__class__.__name__} from {getattr(msg, 'source', 'unknown')}"
                    )

            # TaskResult / Response (final outputs)
            elif isinstance(msg, (TaskResult, Response)):
                print(
                    f"\n{BOLD}{MAGENTA}╔═════════════════════════╗\n"
                    f"║     SESSION COMPLETE    ║\n"
                    f"╚═════════════════════════╝{RESET}\n"
                )
            # Fallback unknown type
            else:
                print(f"{BOLD}{RED}[WARN]{RESET} Unhandled message type: {type(msg)}")

        finally:
            gate["open"] = False

    # Main loop
    if debug:
        print(f"{BOLD}{YELLOW}[DEBUG] Starting console stream processing…{RESET}")

    async for m in stream:
        await process(m)

    return last_processed


# Public alias
PrettyConsole = _PrettyConsole
