"""Enhanced console formatter for magentic-ui CLI with improved visual formatting."""

import asyncio
import inspect
import re
import json
import sys
import builtins
import warnings
import logging
import textwrap
from typing import Any, AsyncGenerator, Dict, Optional, Set, List, Sequence, Callable

from autogen_agentchat.base import TaskResult, Response
from autogen_agentchat.messages import BaseAgentEvent, BaseChatMessage
from autogen_core import CancellationToken

# Terminal colors and formatting
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
HEADER_SEP = "=" * 26  # 26 equals signs

# Common patterns to identify information messages
INFO_PATTERNS = [
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

# Create a compiled regex pattern for faster matching
INFO_REGEX = re.compile('|'.join(INFO_PATTERNS))


def try_parse_json(content: str) -> (bool, Any):
    """Attempt to parse a string as JSON, with more relaxed detection."""
    # Check if it looks like it might be JSON (starts/ends with braces or brackets)
    content = content.strip()
    if not ((content.startswith("{") and content.endswith("}")) or 
            (content.startswith("[") and content.endswith("]"))):
        return False, None
        
    # Try to parse as regular JSON
    try:
        obj = json.loads(content)
        return True, obj
    except json.JSONDecodeError:
        # Not valid JSON
        return False, None
        
def try_format_step_message(content: str, color=CYAN):
    """
    Attempt to format content as a step message from the orchestrator.
    These typically include title, index, details, agent_name, instruction fields.
    """
    try:
        is_json, obj = try_parse_json(content)
        if not is_json:
            return False
            
        # Check if this looks like a step message JSON
        keys = {"title", "index", "details", "agent_name"}
        has_most_keys = sum(1 for k in keys if k in obj) >= 3
        
        if not has_most_keys:
            return False
        
        # Terminal width for wrapping - subtract margin for safety
        term_width = 100  # Default to 100 if we can't detect
        try:
            import shutil
            term_size = shutil.get_terminal_size()
            term_width = term_size.columns - 10  # Leave some margin
        except:
            pass  # Fallback to default width
            
        # Left margin with the vertical bar
        left_margin = f"{color}┃{RESET} "
        content_width = term_width - len(left_margin) - 3  # Account for label indent
        
        # Print title section with enhanced formatting
        print()
        if "title" in obj:
            title = obj["title"]
            print(f"{color}┃{RESET} {BOLD}Title:{RESET} {title}")
            
        # Print step index if available
        if "index" in obj:
            print(f"{color}┃{RESET} {BOLD}Step:{RESET} {obj['index'] + 1}")
            
        # Print details with wrapping if available
        if "details" in obj:
            print(f"{color}┃{RESET}")
            print(f"{color}┃{RESET} {BOLD}Details:{RESET}")
            details_text = obj["details"]
            wrapped_details = textwrap.wrap(details_text, width=content_width - 3)
            for line in wrapped_details:
                print(f"{color}┃{RESET}   {line}")
                
        # Print agent name if available
        if "agent_name" in obj:
            print(f"{color}┃{RESET}")
            print(f"{color}┃{RESET} {BOLD}Agent:{RESET} {obj['agent_name'].upper()}")
            
        # Print instruction if available
        if "instruction" in obj:
            print(f"{color}┃{RESET}")
            print(f"{color}┃{RESET} {BOLD}Instruction:{RESET}")
            instruction_text = obj["instruction"]
            wrapped_instruction = textwrap.wrap(instruction_text, width=content_width - 3)
            for line in wrapped_instruction:
                print(f"{color}┃{RESET}   {line}")
                
        # Print progress summary if available
        if "progress_summary" in obj:
            print(f"{color}┃{RESET}")
            print(f"{color}┃{RESET} {BOLD}Progress:{RESET}")
            progress_text = obj["progress_summary"]
            wrapped_progress = textwrap.wrap(progress_text, width=content_width - 3)
            for line in wrapped_progress:
                print(f"{color}┃{RESET}   {line}")
        
        # Add other fields that might be important
        for key, value in obj.items():
            if key not in {"title", "index", "details", "agent_name", "instruction", "progress_summary"}:
                if isinstance(value, str) and len(value) > 0:
                    print(f"{color}┃{RESET}")
                    print(f"{color}┃{RESET} {BOLD}{key.capitalize()}:{RESET}")
                    wrapped_text = textwrap.wrap(value, width=content_width - 3)
                    for line in wrapped_text:
                        print(f"{color}┃{RESET}   {line}")
                        
        print()
        return True
    except Exception:
        return False

def pretty_print_json(content: str, color=CYAN):
    try:
        is_json, obj = try_parse_json(content)
        if not is_json:
            return False
            
        pretty = json.dumps(obj, indent=2, ensure_ascii=False)
        
        # Print first line with some spacing
        print()
        
        # Terminal width for wrapping - subtract margin for safety
        term_width = 100  # Default to 100 if we can't detect
        try:
            import shutil
            term_size = shutil.get_terminal_size()
            term_width = term_size.columns - 10  # Leave some margin
        except:
            pass  # Fallback to default width
            
        # Left margin with the vertical bar
        left_margin = f"  {color}┃{RESET} "
        content_width = term_width - len(left_margin)
        
        # Process each line of JSON with better formatting
        for line in pretty.splitlines():
            # Add extra indent for better readability
            indented_line = line
            
            # Make keys bold for better visibility
            if ":" in line and not line.strip().startswith('"'):
                parts = line.split(":", 1)
                key = parts[0]
                value = parts[1] if len(parts) > 1 else ""
                
                # Check if the key has quotes
                if '"' in key:
                    # Make only the key name bold, not the quotes or spaces
                    last_quote_pos = key.rfind('"')
                    if last_quote_pos != -1:
                        # Get everything before the last quote
                        before_quote = key[:last_quote_pos]
                        # Get the last quote
                        last_quote = key[last_quote_pos]
                        
                        # Format with the key name in bold
                        indented_line = f"{before_quote}{BOLD}{last_quote}{RESET}{color}{value}"
                else:
                    # For cases without quotes (like when it's an object property)
                    indented_line = f"{BOLD}{key}{RESET}{color}:{value}"
            
            # Handle line wrapping to maintain consistent vertical bars
            if len(indented_line) > content_width:
                # Calculate the indent level for continuation lines
                indent_level = len(line) - len(line.lstrip())
                indent_spaces = ' ' * (indent_level + 2)  # Add 2 spaces for better readability
                
                # Print the first line
                print(f"{left_margin}{indented_line[:content_width]}")
                
                # Split the rest of the line into chunks that fit within content_width
                remaining = indented_line[content_width:]
                while remaining:
                    # Print continuation line with proper alignment
                    chunk = remaining[:content_width-len(indent_spaces)]
                    print(f"{left_margin}{indent_spaces}{chunk}")
                    remaining = remaining[len(chunk):]
            else:
                # Print the line as is if it fits
                print(f"{left_margin}{indented_line}")
        
        # Add an extra line after the JSON for spacing
        print()
        return True
    except Exception:
        return False
    
    
def pretty_print_plan(content: str, color=CYAN):
    try:
        obj = json.loads(content)
        if all(k in obj for k in ("task", "plan_summary", "steps")):
            # Add spacing before the plan
            #print()
            
            # Terminal width for wrapping - subtract margin for safety
            term_width = 100  # Default to 100 if we can't detect
            try:
                import shutil
                term_size = shutil.get_terminal_size()
                term_width = term_size.columns - 10  # Leave some margin
            except:
                pass  # Fallback to default width
                
            # Left margin with the vertical bar - reduced indentation for better edge alignment
            left_margin = f"{color}┃{RESET} "
            content_width = term_width - len(left_margin) - 3  # Account for task label indent
            
            # Print task with enhanced formatting and wrapping for long task descriptions
            task_text = obj['task']
            if len(task_text) > content_width:
                # Print the label
                print(f"{color}┃{RESET} {BOLD}Task:{RESET}")
                # Wrap and print the text with consistent margin
                wrapped_task = textwrap.wrap(task_text, width=content_width)
                for line in wrapped_task:
                    print(f"{color}┃{RESET}   {line}")
            else:
                print(f"{color}┃{RESET} {BOLD}Task:{RESET} {task_text}")
            
            # Print plan summary if available
            if obj.get("plan_summary"):
                print(f"{color}┃{RESET}")
                print(f"{color}┃{RESET} {BOLD}Plan Summary:{RESET}")
                for line in obj['plan_summary'].split('\n'):
                    # Wrap long lines
                    if len(line) > content_width:
                        wrapped_lines = textwrap.wrap(line, width=content_width)
                        for i, wrapped_line in enumerate(wrapped_lines):
                            if i == 0:
                                print(f"{color}┃{RESET}   {wrapped_line}")
                            else:
                                print(f"{color}┃{RESET}   {wrapped_line}")
                    else:
                        print(f"{color}┃{RESET}   {line}")
            
            # Print steps with better separation and structure
            if obj.get("steps"):
                print(f"{color}┃{RESET}")
                print(f"{color}┃{RESET} {BOLD}Steps:{RESET}")
                for i, step in enumerate(obj['steps'], 1):
                    # Add separator between steps
                    if i > 1:
                        print(f"{color}┃{RESET}")
                    
                    # Print step number and title with enhanced visibility
                    step_title = f"{i}. {step['title']}"
                    print(f"{color}┃{RESET}   {BOLD}{color}{step_title}{RESET}")
                    
                    # Print details with better indentation and consistent wrapping
                    details_width = content_width - 6  # Account for the extra indent
                    details = step.get('details', '')
                    wrapped_details = textwrap.wrap(details, width=details_width)
                    for line in wrapped_details:
                        print(f"{color}┃{RESET}      {line}")
                    
                    # Print instruction with better wrapping if it exists
                    if step.get('instruction'):
                        print(f"{color}┃{RESET}")
                        print(f"{color}┃{RESET}      {BOLD}Instruction:{RESET}")
                        wrapped_instruction = textwrap.wrap(step['instruction'], width=details_width)
                        for line in wrapped_instruction:
                            print(f"{color}┃{RESET}      {line}")
                    
                    # Print progress summary if it exists
                    if step.get('progress_summary'):
                        print(f"{color}┃{RESET}")
                        print(f"{color}┃{RESET}      {BOLD}Progress:{RESET}")
                        wrapped_progress = textwrap.wrap(step['progress_summary'], width=details_width)
                        for line in wrapped_progress:
                            print(f"{color}┃{RESET}      {line}")
                    
                    # Print agent with emphasis
                    print(f"{color}┃{RESET}      {BOLD}Agent:{RESET} {step['agent_name'].upper()}")
            
            # Add spacing after the plan
            print()
            
            # Add user prompt for accepting the plan or requesting changes
            print(f"{BOLD}{YELLOW}Type 'accept' to proceed with this plan or describe any changes needed:{RESET}")
            return True
        return False
    except Exception as e:
        if textwrap:
            # If there's a fallback option that works without proper textwrap
            pass
        return False


async def _StylizedConsole(
    stream: AsyncGenerator[Any, None], 
    debug: bool = False, 
    no_inline_images: bool = False, 
    output_stats: bool = False
) -> Any:
    """
    An enhanced console formatter for magentic-ui CLI that provides
    better visual formatting of agent communication.

    Args:
        stream (AsyncGenerator): Stream of messages to render
        debug (bool, optional): Enable debug mode to show internal messages. Defaults to False.
        no_inline_images (bool, optional): If True, will not render inline images. Defaults to False.
        output_stats (bool, optional): If True, will output stats summary. Defaults to False.

    Returns:
        The last message processed
    """
    current_agent: Optional[str] = None
    previous_agent: Optional[str] = None
    known_agents: Set[str] = set()
    known_transitions: Dict[str, Dict[str, bool]] = {}
    last_processed = None
    
    # Agent color mapping for consistent coloring
    agent_colors = {
        "orchestrator": CYAN,
        "coder_agent": MAGENTA,
        "coder": MAGENTA,
        "reviewer": GREEN,
        "web_surfer": BLUE,
        "file_surfer": YELLOW,
        "user_proxy": GREEN,
        "azure_reasoning_agent": RED,
    }
    
    def get_agent_color(agent_name: str) -> str:
        """Get the color for an agent, with fallback to default colors."""
        lower_name = agent_name.lower()
        
        # Check if we have a predefined color for this agent
        for agent_key, color in agent_colors.items():
            if agent_key in lower_name:
                return color
        
        # Assign a color based on agent name hash (for consistency)
        colors = [BLUE, GREEN, YELLOW, CYAN, MAGENTA]
        return colors[hash(agent_name) % len(colors)]

    def format_agent_header(agent_name: str) -> str:
        """Format a header box for the agent name."""
        agent_display = agent_name.upper()
        agent_color = get_agent_color(agent_name)
        # Box width (including borders)
        box_width = 26
        # Center the display name
        display_name = agent_display[:box_width-4]  # leave space for padding and borders
        name_len = len(display_name)
        total_padding = box_width - 2 - name_len  # 2 for the borders
        left_padding = total_padding // 2
        right_padding = total_padding - left_padding
        # Build the box
        top = f"{BOLD}{agent_color}╔{'═' * (box_width-2)}╗"
        mid = f"║{' ' * left_padding}{WHITE_BG}{BLACK_TEXT}{display_name}{RESET}{agent_color}{' ' * right_padding}║"
        bot = f"╚{'═' * (box_width-2)}╝{RESET}"
        return f"\n{top}\n{mid}\n{bot}\n"

    def format_transition() -> str:
        """Format a transition arrow between agents."""
        if not previous_agent or not current_agent:
            return ""
        
        # Record this transition
        if previous_agent not in known_transitions:
            known_transitions[previous_agent] = {}
        known_transitions[previous_agent][current_agent] = True
        
        prev_color = get_agent_color(previous_agent)
        curr_color = get_agent_color(current_agent)
        
        # Enhanced transition with more visible arrow
        return f"\n  {BOLD}{prev_color}{previous_agent.upper()}{RESET}  {BOLD}{YELLOW}━━━━━━━━▶{RESET}  {BOLD}{curr_color}{current_agent.upper()}{RESET}\n"
    
    def format_info_line(content: str) -> str:
        """Format an info line with [INFO] prefix."""
        return f"{BOLD}{GREEN}[INFO]{RESET} {UNDERLINE}{content}{RESET}"

    def is_info_message(content: str) -> bool:
        """Check if a message contains information patterns that should be formatted specially."""
        # First check for common patterns
        if INFO_REGEX.search(content):
            return True
        
        # Also match any lines starting with verbs in present continuous form - common for status updates
        # Example: "Parsing data from the API..."
        if re.match(r'^\s*[A-Z][a-z]+ing\b', content):
            return True
            
        return False

    # Suppress raw log lines unless debug is enabled
    class LogFilter:
        def __init__(self, debug):
            self.debug = debug
        def write(self, msg):
            if self.debug or not msg.startswith("INFO:autogen_core.events"):
                sys.__stdout__.write(msg)
        def flush(self):
            sys.__stdout__.flush()
    sys.stdout = LogFilter(debug)

    # Suppress all non-agent output unless debug is enabled
    class OutputFilter:
        def __init__(self, debug, allow_agent_output):
            self.debug = debug
            self.allow_agent_output = allow_agent_output  # function to check if output is allowed
            self._buffer = ""
        def write(self, msg):
            if self.debug or self.allow_agent_output():
                sys.__stdout__.write(msg)
        def flush(self):
            sys.__stdout__.flush()

    # Only allow output from process_message (agent comms) or if debug is on
    _agent_output_flag = {'active': False}
    def allow_agent_output():
        return _agent_output_flag['active']
    sys.stdout = OutputFilter(debug, allow_agent_output)
    sys.stderr = OutputFilter(debug, allow_agent_output)

    # Suppress warnings and logging unless debug is on
    if not debug:
        warnings.filterwarnings('ignore')
        logging.disable(logging.CRITICAL)

    async def process_message(message: BaseChatMessage | BaseAgentEvent | TaskResult | Response) -> None:
        nonlocal current_agent, previous_agent, last_processed
        last_processed = message
        _agent_output_flag['active'] = True  # Enable agent output
        
        if debug:
            message_type = message.__class__.__name__
            source = getattr(message, "source", "unknown")
            print(f"{BOLD}{YELLOW}[DEBUG PROCESS]{RESET} Received message: {message_type} from {BOLD}{source}{RESET}")
            print(f"{BOLD}{YELLOW}[DEBUG STATE]{RESET} Current agent: {current_agent}, Previous agent: {previous_agent}")
            
        try:
            if isinstance(message, BaseChatMessage):
                metadata = getattr(message, "metadata", {})
                if metadata and metadata.get("internal") == "yes" and not debug:
                    return
                if debug and metadata:
                    print(f"{BOLD}{YELLOW}[DEBUG]{RESET} {WHITE_BG}{BLACK_TEXT} Message metadata {RESET} {metadata}")
                source = message.source
                if source != current_agent:
                    if debug:
                        print(f"{BOLD}{YELLOW}[DEBUG TRANSITION]{RESET} Agent change: {current_agent} -> {source}")
                        
                    previous_agent = current_agent
                    current_agent = source
                    known_agents.add(source)
                    
                    if debug:
                        print(f"{BOLD}{YELLOW}[DEBUG AGENTS]{RESET} Known agents: {', '.join(known_agents)}")
                        
                    if previous_agent:
                        print(format_transition())
                    print(format_agent_header(source))
                content = getattr(message, "content", "")
                if isinstance(content, str):
                    if debug:
                        content_preview = content[:100] + "..." if len(content) > 100 else content
                        print(f"{BOLD}{YELLOW}[DEBUG CONTENT]{RESET} Content type: string, length: {len(content)}")
                        print(f"{BOLD}{YELLOW}[DEBUG CONTENT]{RESET} Preview: {content_preview}")
                        
                    if is_info_message(content):
                        if debug:
                            print(f"{BOLD}{YELLOW}[DEBUG FORMAT]{RESET} Formatting as INFO message")
                        print(format_info_line(content))
                    elif pretty_print_plan(content):
                        if debug:
                            print(f"{BOLD}{YELLOW}[DEBUG FORMAT]{RESET} Formatted as PLAN")
                        pass
                    elif pretty_print_json(content):
                        if debug:
                            print(f"{BOLD}{YELLOW}[DEBUG FORMAT]{RESET} Formatted as JSON")
                        pass
                    # Check if this might be a step message JSON (commonly sent by orchestrator)
                    elif try_format_step_message(content, get_agent_color(source)):
                        if debug:
                            print(f"{BOLD}{YELLOW}[DEBUG FORMAT]{RESET} Formatted as STEP message")
                        pass
                    else:
                        if debug:
                            print(f"{BOLD}{YELLOW}[DEBUG FORMAT]{RESET} Formatting as regular message")
                        agent_color = get_agent_color(source)
                        lines = content.split('\n')
                        
                        # Terminal width for wrapping - subtract margin for safety
                        term_width = 100  # Default to 100 if we can't detect
                        try:
                            import shutil
                            term_size = shutil.get_terminal_size()
                            term_width = term_size.columns - 10  # Leave some margin
                        except:
                            pass  # Fallback to default width
                        
                        left_margin = f"{agent_color}┃{RESET} "
                        content_width = term_width - len(left_margin)
                        
                        for i, line in enumerate(lines):
                            if line.strip():
                                # Handle line wrapping to maintain consistent vertical bars
                                if len(line) > content_width:
                                    # Print the first line
                                    print(f"{left_margin}{line[:content_width]}")
                                    
                                    # Split the rest of the line into chunks that fit within content_width
                                    remaining = line[content_width:]
                                    while remaining:
                                        # Print continuation line with proper alignment
                                        chunk = remaining[:content_width]
                                        print(f"{left_margin}  {chunk}")
                                        remaining = remaining[len(chunk):]
                                else:
                                    # Print the line as is if it fits
                                    print(f"{left_margin}{line}")
                else:
                    try:
                        if debug:
                            print(f"{BOLD}{YELLOW}[DEBUG]{RESET} Multi-modal content: {type(content)}")
                        print(str(content))
                    except Exception as e:
                        print(f"[Complex content could not be displayed: {e if debug else ''}]")
            elif (isinstance(message, BaseAgentEvent)):
                if debug:
                    print(f"{BOLD}{YELLOW}[DEBUG EVENT]{RESET} {UNDERLINE}{message.__class__.__name__}{RESET} from {BOLD}{getattr(message, 'source', 'unknown')}{RESET}")
                    if hasattr(message, 'content'):
                        print(f"  {YELLOW}▶{RESET} Content: {getattr(message, 'content', '')}")
            elif isinstance(message, TaskResult) or isinstance(message, Response):
                print(f"\n{BOLD}{MAGENTA}╔═════════════════════════╗\n║     FINAL RESULT        ║\n╚═════════════════════════╝{RESET}")
                if hasattr(message, "content") and message.content:
                    if pretty_print_plan(message.content):
                        pass
                    elif pretty_print_json(message.content):
                        pass
                    else:
                        print(f"\n{message.content}\n")
            else:
                try:
                    source = getattr(message, "source", "unknown")
                    content = getattr(message, "content", str(message))
                    if hasattr(message, "__class__"):
                        message_type = message.__class__.__name__
                    else:
                        message_type = "Message"
                    print(f"{BOLD}{YELLOW}[{message_type}]{RESET} from {source}: {content}")
                except Exception as e:
                    if debug:
                        print(f"{BOLD}{RED}[ERROR]{RESET} Failed to process message: {str(e)}")
                        print(f"Message type: {type(message)}")
        finally:
            _agent_output_flag['active'] = False  # Disable agent output after message
    
    # Log start of processing if debug is enabled
    if debug:
        print(f"\n{BOLD}{YELLOW}[DEBUG START]{RESET} Beginning message stream processing")
        print(f"{BOLD}{YELLOW}[DEBUG CONFIG]{RESET} Debug: {debug}, No inline images: {no_inline_images}, Output stats: {output_stats}\n")
        
    # Process the stream
    async for message in stream:
        try:
            if debug:
                print(f"\n{BOLD}{YELLOW}[DEBUG MESSAGE]{RESET} Processing new message")
                
            await process_message(message)
            
            if debug:
                print(f"{BOLD}{YELLOW}[DEBUG MESSAGE]{RESET} Finished processing message\n")
                
        except Exception as e:
            print(f"{RED}Error processing message: {str(e) if debug else 'see logs for details'}{RESET}")
            if debug:
                import traceback
                print(f"{YELLOW}{traceback.format_exc()}{RESET}")
    
    print(f"\n{BOLD}{CYAN}╔═════════════════════════╗\n║     SESSION COMPLETE    ║\n╚═════════════════════════╝{RESET}\n")
    
    # Return the last processed message (following original Console behavior)
    return last_processed


# Replace the default StylizedConsole with our enhanced version
StylizedConsole = _StylizedConsole