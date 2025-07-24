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


# ╭──────────────────────────────────────────────────────────────────────────╮
# │  ANSI Color Detection and Agent Colors                                   │
# ╰──────────────────────────────────────────────────────────────────────────╯
def _ansi(seq: str) -> str:
    """Return full ESC sequence if colours are on, else empty string."""
    return f"\033[{seq}m" if _COLOR_ENABLED else ""


# checks if the terminal supports ANSI colors
_COLOR_ENABLED = sys.stdout.isatty()

# text attributes
RESET = _ansi("0")
BOLD = _ansi("1")
UNDERLINE = _ansi("4")

# foreground colours
RED = _ansi("31")
GREEN = _ansi("32")
YELLOW = _ansi("33")
BLUE = _ansi("34")
MAGENTA = _ansi("35")
CYAN = _ansi("36")

# cursor control (not m‑terminated)
CURSOR_UP = "\033[A" if _COLOR_ENABLED else ""
CLEAR_LINE = "\033[2K" if _COLOR_ENABLED else ""
CURSOR_TO_START = "\033[G" if _COLOR_ENABLED else ""

# used for clearing the "input prompt" box
_LINES_TO_CLEAR = 4

# agent colors
_AGENT_COLORS = {
    "orchestrator": MAGENTA,
    "coder_agent": RED,
    "coder": RED,
    "web_surfer": BLUE,
    "file_surfer": YELLOW,
    "user": GREEN,
    "user_proxy": GREEN,
    "no_action_agent": CYAN,
    "reviewer": GREEN,
}

# consistent color fallback for non-defined agents
_COLOR_POOL = [BLUE, GREEN, YELLOW, CYAN, MAGENTA]


def agent_color(name: str) -> str:
    ln = name.lower()
    for key, col in _AGENT_COLORS.items():
        if key in ln:
            return col
    return _COLOR_POOL[hash(name) % len(_COLOR_POOL)]


# ╭────────────────────────────────────────────────────────────────────────────╮
# │  Helper utilities                                                          │
# ╰────────────────────────────────────────────────────────────────────────────╯
def terminal_width(fallback: int = 100) -> int:
    """Return terminal width minus a 10‑column safety margin."""
    try:
        import shutil

        return max(20, shutil.get_terminal_size().columns - 10)
    except Exception:
        return fallback


def try_parse_json(raw: str) -> tuple[bool, Any]:
    """Lightweight JSON detector – avoids `json.loads` when blatantly not JSON."""
    raw = raw.strip()
    # If it's a Python-style list (web_surfer output), skip JSON parsing and print a hint
    if raw.startswith("[") and ", <autogen_core._image.Image object" in raw:
        # print(f"{YELLOW}[Screenshot captured]{RESET}")
        return False, raw
    if not (raw.startswith("{") and raw.endswith("}")) and not (
        raw.startswith("[") and raw.endswith("]")
    ):
        return False, None
    try:
        return True, json.loads(raw)
    except (ValueError, TypeError) as e:
        # Print detailed error information to help with debugging
        if sys.__stdout__ is not None:
            print(f"\n{RED}[JSON PARSE ERROR]{RESET} {type(e).__name__}: {str(e)}")
            # Show a truncated version of the problematic content
            preview = raw[:200] + "..." if len(raw) > 200 else raw
            print(f"{RED}Problem content:{RESET}\n{preview}\n")
        return False, None


# ╭────────────────────────────────────────────────────────────────────────────╮
# │  Header & transition boxes                                                 │
# ╰────────────────────────────────────────────────────────────────────────────╯
def header_box(agent: str) -> str:
    """Return a symmetric ASCII box with the agent name centered."""

    # number of "═" characters (and usable chars in mid line)
    INNER = 24

    # Show "USER" instead of "USER_PROXY"
    if agent.upper() == "USER_PROXY":
        agent = "USER"

    colour = agent_color(agent)
    text = agent.upper()[:INNER]
    pad = INNER - len(text)
    left, right = pad // 2, pad - pad // 2

    top = f"{BOLD}{colour}╔{'═' * INNER}╗"
    mid = f"║{' ' * left}{text}{RESET}{colour}{' ' * right}║"
    bot = f"╚{'═' * INNER}╝{RESET}"

    return f"{top}\n{mid}\n{bot}"


def transition_line(prev: str, curr: str) -> str:
    # Display "USER" instead of "USER_PROXY"
    if prev.upper() == "USER_PROXY":
        prev = "USER"
    if curr.upper() == "USER_PROXY":
        curr = "USER"

    return (
        f"{BOLD}{agent_color(prev)}{str(prev).upper()}{RESET}  "
        f"{BOLD}{YELLOW}━━━━▶{RESET}  "
        f"{BOLD}{agent_color(curr)}{str(curr).upper()}{RESET}"
    )


# ╭────────────────────────────────────────────────────────────────────────────╮
# │  JSON pretty printer                                                       │
# ╰────────────────────────────────────────────────────────────────────────────╯
def pretty_print_json(raw: str, colour: str) -> bool:
    ok, obj = try_parse_json(raw)
    if not ok or obj in ([], {}):
        return False

    width = terminal_width()
    left = f"{colour}┃{RESET} "
    indent_json = json.dumps(obj, indent=2, ensure_ascii=False)
    indent_json = re.sub(r'"([^"\\]+)":', rf'"{BOLD}\1{RESET}":', indent_json)

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
    print()
    return True


# ╭────────────────────────────────────────────────────────────────────────────╮
# │  Plan & step formatters                                                    │
# ╰────────────────────────────────────────────────────────────────────────────╯
def format_plan(obj: dict[str, Any], colour: str) -> None:
    width = terminal_width()
    left = f"{colour}┃{RESET} "
    body_w = width - len(left)

    def _wrap(text: str, indent: int = 3):
        for ln in textwrap.wrap(text, body_w - indent):
            print(f"{left}{' ' * indent}{ln}")

    # printing the ledger (step status and progress info)
    if (
        "is_current_step_complete" in obj
        and "need_to_replan" in obj
        and "instruction_or_question" in obj
        and "progress_summary" in obj
    ):
        print(f"{left}{BOLD}━━━━━━━━━━ STATUS UPDATE ━━━━━━━━━━{RESET}")

        # Current step completion status
        step_complete = obj["is_current_step_complete"]
        if isinstance(step_complete, dict) and "answer" in step_complete:
            status = (
                f"{GREEN}Yes{RESET}"
                if step_complete["answer"]
                else f"{YELLOW}No{RESET}"
            )
            print(f"{left}{BOLD}Current Step Complete:{RESET} {status}")

            # Print reason if available
            if "reason" in step_complete:
                print(f"{left}{' ' * 3}{BOLD}Reason:{RESET}")
                _wrap(str(step_complete.get("reason", "")), 5)  # type: ignore[arg-type]
        else:
            # Simple boolean display if not in detailed format
            status = f"{GREEN}Yes{RESET}" if step_complete else f"{YELLOW}No{RESET}"
            print(f"{left}{BOLD}Current Step Complete:{RESET} {status}")

        print(left)  # Add spacing between sections

        # Need to replan status
        replan = obj["need_to_replan"]
        if isinstance(replan, dict) and "answer" in replan:
            status = f"{YELLOW}Yes{RESET}" if replan["answer"] else f"{GREEN}No{RESET}"
            print(f"{left}{BOLD}Need to Replan:{RESET} {status}")

            # Print reason if available
            if "reason" in replan:
                print(f"{left}{' ' * 3}{BOLD}Reason:{RESET}")
                _wrap(str(replan.get("reason", "")), 5)  # type: ignore[arg-type]
        else:
            # Simple boolean display if not in detailed format
            status = f"{YELLOW}Yes{RESET}" if replan else f"{GREEN}No{RESET}"
            print(f"{left}{BOLD}Need to Replan:{RESET} {status}")

        print(left)  # Add spacing between sections

        # Instruction or question
        instruction = obj["instruction_or_question"]
        if isinstance(instruction, dict):
            if "answer" in instruction:
                print(f"{left}{BOLD}Next Action:{RESET}")
                _wrap(str(instruction.get("answer", "")), 3)  # type: ignore[arg-type]

            # Show which agent will handle this instruction
            if "agent_name" in instruction:
                agent = str(instruction.get("agent_name", "")).upper()  # type: ignore[arg-type]
                print(f"{left}{' ' * 3}{BOLD}Agent:{RESET} {agent}")
        else:
            # Simple string display if not in detailed format
            print(f"{left}{BOLD}Next Action:{RESET}")
            _wrap(str(instruction), 3)

        print(left)

        # Progress summary
        print(f"{left}{BOLD}Progress Summary:{RESET}")
        _wrap(str(obj["progress_summary"]), 3)
        print(left)

        print(f"{left}{BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{RESET}")

    elif "response" in obj and "task" in obj and "steps" in obj:
        # Response
        _wrap(str(obj["response"]), 0)

        # Task
        print(left)
        print(f"{left}{BOLD}Task:{RESET}")
        _wrap(str(obj["task"]))

        # Steps
        steps: list[dict[str, Any]] = obj.get("steps", []) or []
        if steps:
            print(f"{left}\n{left}{BOLD}Steps:{RESET}")
            for i, step in enumerate(steps, 1):
                # Add a line break between steps (except for the first one)
                if i > 1:
                    print(f"{left}")  # Add an empty line between steps

                # Get step type and create indicator
                if (
                    isinstance(step, dict)
                    and step.get("step_type") == "SentinelPlanStep"
                ):
                    step_type = "SentinelPlanStep"
                else:
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
                print(f"{left}{BOLD}{i}. {type_indicator}{step_title}{RESET}")

                if isinstance(step, dict):
                    # shows the details for a specific step
                    if step.get("details"):
                        print(f"{left}{' ' * 3}{BOLD}Details:{RESET}")
                        _wrap(str(step["details"]), 5)

                    # instruction
                    if step.get("instruction"):
                        print(f"{left}{' ' * 3}{BOLD}Instruction:{RESET}")
                        _wrap(str(step["instruction"]), 7)

                    # progress summary
                    if step.get("progress_summary"):
                        print(f"{left}{' ' * 3}{BOLD}Progress Summary:{RESET}")
                        _wrap(str(step["progress_summary"]), 7)

                    # shows which agent should perform the action for this step
                    if step.get("agent_name"):
                        print(
                            f"{left}{' ' * 3}{BOLD}Agent:{RESET} {BOLD}{agent_color(step['agent_name'])}{step['agent_name'].upper()}{RESET}"
                        )

                    # Show step type information if available
                    if step_type:
                        type_name = (
                            "Regular Step"
                            if step_type == "PlanStep"
                            else "Sentinel Step"
                        )
                        print(f"{left}{' ' * 3}{BOLD}Type:{RESET} {type_name}")
                        if step_type == "SentinelPlanStep":
                            if "condition" in step:
                                print(
                                    f"{left}{' ' * 5}{BOLD}Condition:{RESET} {step['condition']}"
                                )
                            if "sleep_duration" in step:
                                print(
                                    f"{left}{' ' * 5}{BOLD}Sleep Duration:{RESET} {step['sleep_duration']}s"
                                )

            # Always show acceptance prompt for full plans
            print()  # tail spacer
            print(f"{BOLD}{YELLOW}Type 'accept' to proceed or describe changes:{RESET}")

    # Single‑step orchestrator JSON (title/index style)
    # Prints the information of the current step being processed
    elif {"title", "index", "agent_name"}.issubset(obj):
        idx = obj["index"] + 1 if isinstance(obj.get("index"), int) else obj["index"]

        if "title" in obj:
            print(f"{left}{BOLD}Step #{idx}:{RESET}")
            _wrap(str(obj["title"]))

        if "details" in obj:
            print(left)
            print(f"{left}{BOLD}Details:{RESET}")
            _wrap(str(obj["details"]))

        if "agent_name" in obj:
            print(left)
            print(
                f"{left}{BOLD}Agent:{RESET} {BOLD}{agent_color(obj['agent_name'])}{str(obj['agent_name']).upper()}{RESET}"
            )

        if "instruction" in obj:
            print(left)
            print(f"{left}{BOLD}Instruction:{RESET}")
            _wrap(str(obj["instruction"]))

        if "step_type" in obj:
            step_type = (
                "Sentinel Step"
                if obj["step_type"] == "SentinelPlanStep"
                else "Regular Step"
            )
            print(left)
            print(f"{left}{BOLD}Type:{RESET} {step_type}")

        if "condition" in obj:
            print(left)
            print(f"{left}{BOLD}Condition:{RESET} {obj['condition']}")

        if "sleep_duration" in obj:
            print(left)
            print(f"{left}{BOLD}Sleep Duration:{RESET} {obj['sleep_duration']}s")

        print()  # tail spacer

        # Is this a user proxy interaction? (Check agent name)
        agent_name = obj.get("agent_name", "").lower()
        is_user_proxy = "user" in agent_name and "proxy" in agent_name

        # Only show the prompt if this is a user proxy agent interaction
        if is_user_proxy:
            print(f"{BOLD}{YELLOW}Type 'accept' to proceed or describe changes:{RESET}")

    # If it's a full plan without steps, the user may need to clarify their task
    elif "task" in obj or "plan_summary" in obj:
        print()  # tail spacer
        print(f"{BOLD}{YELLOW}You may need to clarify your task:{RESET}")


def pretty_print_plan(raw: str, colour: str) -> bool:
    ok, obj = try_parse_json(raw)
    if not ok:
        return False
    if any(
        k in obj
        for k in (
            "task",
            "plan_summary",
            "steps",
            "title",
            "is_current_step_complete",
            "agent_name",
        )
    ):
        format_plan(obj, colour)
        return True

    return False


# Step formatter (simple schema: {step, content})
def try_format_step(raw: str, colour: str) -> bool:
    ok, obj = try_parse_json(raw)
    if not ok or not {"step", "content"}.issubset(obj):
        return False
    width = terminal_width()
    title = obj.get("title", f"Step {obj['step']}")
    print(
        f"{BOLD}{colour}╔{'═' * (width - 4)}╗\n"
        f"║ {title:<{width - 6}}║\n"
        f"╚{'═' * (width - 4)}╝{RESET}\n"
    )
    print(f"{BOLD}{colour}┃{RESET} {obj['content']}\n")
    return True


# ╭────────────────────────────────────────────────────────────────────────────╮
# │  Function to print Web_Surfer's Formatted Actions                          │
# ╰────────────────────────────────────────────────────────────────────────────╯
def format_web_surfer_actions(raw: str, colour: str) -> bool:
    """Format and display Web Surfer actions and observations in a structured way."""
    # Check if this is a Web Surfer action log
    if (
        not isinstance(raw, str)
        or "The actions the websurfer performed are the following" not in raw
    ):
        return False

    width = terminal_width()
    left = f"{colour}┃{RESET} "
    body_w = width - len(left)

    # Function to wrap text with proper indentation
    def _wrap_text(text: str, indent: int = 0):
        for line in text.splitlines():
            if not line.strip():
                print(f"{left}")  # Empty line
                continue

            if len(line) + indent <= body_w:
                print(f"{left}{' ' * indent}{line}")
            else:
                for chunk in textwrap.wrap(line, width=body_w - indent):
                    print(f"{left}{' ' * indent}{chunk}")

    print(f"{BOLD}{colour}╔{'═' * (width - 4)}╗")
    print(f"{colour}║ {BOLD}WEB SURFER ACTIONS{RESET}{colour}{' ' * (width - 20)}║")
    print(f"{colour}╚{'═' * (width - 4)}╝{RESET}\n")

    # Split the content into sections
    content = raw.strip()
    parts = content.split("Action: ")

    # Handle the intro text
    if parts[0]:
        intro = parts[0].strip()
        _wrap_text(intro)
        print(f"{left}")  # Add spacing

    # Process each action and observation pair
    for i, part in enumerate(parts[1:], 1):
        if not part.strip():
            continue

        # Split into action and observation
        action_obs = part.split("Observation:", 1)

        if len(action_obs) != 2:
            # Malformed action/observation pair, just print it
            print(f"{left}{BOLD}{YELLOW}Malformed action/observation:{RESET}")
            _wrap_text(part, 2)
            continue

        action, observation = action_obs

        # Extract action details
        action = action.strip()

        # Format and print the action
        print(f"{left}{BOLD}Action #{i}:{RESET}")

        # Check if this is a formatted action with JSON
        if "(" in action and ")" in action:
            action_name, action_params = action.split("(", 1)
            action_params = action_params.rsplit(")", 1)[0]

            print(f"{left}{' ' * 2}{BOLD}{BLUE}{action_name}{RESET}(")

            # Try to parse the JSON parameters
            try:
                # Clean up the parameter string
                action_params = action_params.strip()
                if action_params.startswith("{") and action_params.endswith("}"):
                    params_obj = json.loads(action_params)
                    # Pretty print the parameters
                    params_json = json.dumps(params_obj, indent=2)
                    for line in params_json.splitlines():
                        print(f"{left}{' ' * 4}{line}")
                    print(f"{left}{' ' * 2})")
                else:
                    # Not JSON, just print the params
                    _wrap_text(action_params, 4)
                    print(f"{left}{' ' * 2})")
            except json.JSONDecodeError:
                # If JSON parsing fails, just print the params as text
                _wrap_text(action_params, 4)
                print(f"{left}{' ' * 2})")
        else:
            # Simple text action
            _wrap_text(action, 2)

        # Format and print the observation
        observation = observation.strip()
        print(f"{left}{' ' * 2}{BOLD}Observation:{RESET}")
        _wrap_text(observation, 4)

        # Add spacing between action/observation pairs
        print(f"{left}")

    # Check for webpage information at the end
    if "We are at the following webpage" in content:
        webpage_info = content.split("We are at the following webpage", 1)[1].strip()
        print(f"{left}{BOLD}Current Webpage:{RESET}")
        _wrap_text(webpage_info, 2)

    print()
    return True


def clear_previous_lines(num_lines: int) -> None:
    """Clear the specified number of previous lines in the terminal.

    This function moves the cursor up and clears lines, effectively
    erasing previous output from the terminal.
    """
    if num_lines <= 0:
        return

    for _ in range(num_lines):
        print(f"{CURSOR_UP}{CLEAR_LINE}", end="", flush=True)


def display_initial_user_task(task: str) -> None:
    """Display the initial user task in the same format as other messages.

    This function is meant to be called before starting the agent stream
    to display the user's initial input in a consistent format.
    """
    colour = agent_color("user")
    print(header_box("USER"))
    left = f"{colour}┃{RESET} "

    width = terminal_width()
    body_w = width - len(left)

    # Format the task text with proper line wrapping
    lines = task.splitlines()
    for line in lines:
        if not line.strip():
            print(f"{left}")
            continue

        if len(line) <= body_w:
            print(f"{left}{line}")
        else:
            # Wrap long lines
            for chunk in textwrap.wrap(line, body_w):
                print(f"{left}{chunk}")

    print()


# display a welcome message from the orchestrator
def display_orchestrator_welcome() -> None:
    agent_name = "orchestrator"
    colour = agent_color(agent_name)
    print(header_box(agent_name))
    left = f"{colour}┃{RESET} "

    width = terminal_width()
    body_w = width - len(left)

    welcome_message = "Hi, welcome to Magentic-UI CLI! How can I help you?"

    # Format the welcome message with proper line wrapping
    for chunk in textwrap.wrap(welcome_message, body_w):
        print(f"{left}{chunk}")

    # Add a green '>' prompt similar to the input requested format
    print(f"{BOLD}{GREEN}> {RESET}", end="")


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

    # Track the most recent input prompt state
    input_prompt_shown = False

    async def process(msg: BaseChatMessage | BaseAgentEvent | TaskResult | Response):
        nonlocal current_agent, previous_agent, last_processed, input_prompt_shown
        last_processed = msg
        gate["open"] = True

        try:
            # Chat message
            if isinstance(msg, BaseChatMessage):
                meta = getattr(msg, "metadata", {})
                if meta.get("internal") == "yes" and not debug:
                    return
                src = msg.source

                # Clear the request prompt box for better display
                if src.lower() in ("user", "user_proxy") and input_prompt_shown:
                    # Get the content of the user message
                    content = str(getattr(msg, "content", ""))

                    # Calculate lines dynamically based on message length and terminal width
                    width = terminal_width()

                    # Start with the base _LINES_TO_CLEAR (box + prompt)
                    lines_to_clear = _LINES_TO_CLEAR

                    # Add lines for the actual user input (if any)
                    if content:
                        # Count explicit newlines
                        newline_count = content.count("\n")

                        # Calculate wrapped lines based on content length and terminal width
                        # Subtract 2 from width to account for the prompt '> '
                        chars_per_line = max(20, width - 2)
                        wrapped_lines = (
                            len(content) + chars_per_line - 1
                        ) // chars_per_line

                        # Use the maximum of explicit newlines or wrapped lines calculation
                        content_lines = max(1, newline_count + 1, wrapped_lines)

                        lines_to_clear += content_lines

                    # Erase the input prompt box plus user input
                    clear_previous_lines(lines_to_clear)
                    input_prompt_shown = False

                if src != current_agent:
                    previous_agent, current_agent = current_agent, src
                    if previous_agent:
                        print("\n" + transition_line(previous_agent, current_agent))
                    print(header_box(src))

                colour = agent_color(src)
                content = str(getattr(msg, "content", ""))

                # prints the web surfer output message
                if src.lower() == "web_surfer" and format_web_surfer_actions(
                    content, colour
                ):
                    pass
                if pretty_print_plan(content, colour):
                    pass
                elif pretty_print_json(content, colour):
                    pass
                elif try_format_step(content, colour):
                    pass
                else:
                    width = terminal_width()
                    left = f"{colour}┃{RESET} "
                    body_w = width - len(left)

                    # Process all lines, preserving paragraph structure but ensuring consistent spacing
                    lines = content.splitlines()
                    i = 0
                    while i < len(lines):
                        # Skip multiple consecutive empty lines, but preserve paragraph breaks
                        if not lines[i].strip():
                            if (
                                i > 0 and i < len(lines) - 1
                            ):  # Only print paragraph breaks (not leading/trailing empty lines)
                                print(f"{left}")
                            i += 1
                            # Skip additional empty lines
                            while i < len(lines) and not lines[i].strip():
                                i += 1
                            continue

                        # Process non-empty line
                        line = lines[i]
                        if len(line) <= body_w:
                            print(f"{left}{line}")
                        else:
                            # Wrap long lines
                            wrapped_chunks = textwrap.wrap(line, body_w)
                            for chunk in wrapped_chunks:
                                print(f"{left}{chunk}")
                        i += 1

            # Event message (non‑chat)
            elif isinstance(msg, BaseAgentEvent):
                if debug:
                    print(
                        f"{BOLD}{YELLOW}[EVENT]{RESET} "
                        f"{msg.__class__.__name__} from {getattr(msg, 'source', 'unknown')}"
                    )

                # Special handling for user input requests - always show this regardless of debug mode
                if msg.__class__.__name__ == "UserInputRequestedEvent":
                    box = (
                        "\n"
                        f"{BOLD}{GREEN}╭───────────────────────────────────────╮{RESET}\n"
                        f"{BOLD}{GREEN}│  Input requested - please type below  │{RESET}\n"
                        f"{BOLD}{GREEN}╰───────────────────────────────────────╯{RESET}\n"
                        f"{BOLD}{GREEN}> {RESET}"
                    )
                    print(box, end="", flush=True)

                    # Track that we've shown an input prompt
                    input_prompt_shown = True

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
