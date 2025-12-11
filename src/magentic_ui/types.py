import json
from typing import Optional, List, Dict, Sequence, Union, Any
from autogen_agentchat.messages import BaseAgentEvent
from pydantic import BaseModel
from dataclasses import dataclass
from pathlib import Path


@dataclass
class RunPaths:
    """
    A dataclass that contains the paths to the run directories.

    Attributes:
        internal_root_dir (Path): The base path for all potential runs.
        external_root_dir (Path): The base path for all potential runs.
        run_suffix (str): The suffix for the run directories.
        internal_run_dir (Path): The directory for the internal run.
        external_run_dir (Path): The directory for the external run.
    """

    internal_root_dir: Path
    external_root_dir: Path
    run_suffix: str
    internal_run_dir: Path
    external_run_dir: Path


class PlanStep(BaseModel):
    """
    A class representing a single step in a plan.

    Attributes:
        title (str): The title of the step.
        details (str): The description of the step.
        agent_name (str): The name of the agent responsible for this step.
    """

    title: str
    details: str
    agent_name: str


class SentinelPlanStep(PlanStep):
    """
    A class representing a long-running monitoring or periodic task.

    Attributes:
        title (str): The title of the step.
        details (str): The description of the step.
        agent_name (str): The name of the agent responsible for this step.
        sleep_duration (int): Seconds to wait between checks.
        condition (Union[int, str]): Either:
            - An integer indicating number of iterations to perform
            - A string describing the condition to check for completion
    """

    sleep_duration: int
    condition: Union[int, str]


class Plan(BaseModel):
    """
    A class representing a plan consisting of multiple steps.

    Attributes:
        task (str, optional): The name of the task. Default: empty string
        steps (List[PlanStep]): A list of steps to complete the task.

    Example:
        plan = Plan(
            task="Open Website",
            steps=[PlanStep(title="Open Google", details="Go to the website google.com")]
        )
    """

    task: Optional[str]
    steps: Sequence[PlanStep]

    def __getitem__(self, index: int) -> PlanStep:
        return self.steps[index]

    def __len__(self) -> int:
        return len(self.steps)

    def __str__(self) -> str:
        """Return the string representation of the plan."""
        plan_str = ""
        if self.task is not None:
            plan_str += f"Task: {self.task}\n"
        for i, step in enumerate(self.steps):
            plan_str += f"{i}. {step.agent_name}: {step.title}\n   {step.details}\n"
            if isinstance(step, SentinelPlanStep):
                condition_str = str(step.condition)
                plan_str += f"   [Sentinel: every {step.sleep_duration}s, condition: {condition_str}]\n"
        return plan_str

    @classmethod
    def from_list_of_dicts_or_str(
        cls, plan_dict: Union[List[Dict[str, str]], str, List[Any], Dict[str, Any]]
    ) -> Optional["Plan"]:
        """Load Plan from a list of dictionaries or a JSON string."""
        if isinstance(plan_dict, str):
            plan_dict = json.loads(plan_dict)
        if len(plan_dict) == 0:
            return None
        assert isinstance(plan_dict, (list, dict))

        task = None
        if isinstance(plan_dict, dict):
            task = plan_dict.get("task", None)
            plan_dict = plan_dict.get("steps", [])

        steps: List[PlanStep] = []
        for raw_step in plan_dict:
            if isinstance(raw_step, dict):
                step: dict[str, Any] = raw_step  # type: ignore

                # Check if this is a sentinel step based on whether it has
                # the condition and sleep_duration fields
                if "condition" in step and "sleep_duration" in step:
                    steps.append(
                        SentinelPlanStep(
                            title=step.get("title", "Untitled Step"),
                            details=step.get("details", "No details provided."),
                            agent_name=step.get("agent_name", "agent"),
                            sleep_duration=step.get("sleep_duration", 0),
                            condition=step.get("condition", "indefinite"),
                        )
                    )
                else:
                    steps.append(
                        PlanStep(
                            title=step.get("title", "Untitled Step"),
                            details=step.get("details", "No details provided."),
                            agent_name=step.get("agent_name", "agent"),
                        )
                    )
        return cls(task=task, steps=steps) if steps else None


class HumanInputFormat(BaseModel):
    """
    A class to represent and validate human input format.

    Attributes:
        content (str): The content of the input.
        accepted (bool, optional): Whether the input is accepted or not. Default: False
        plan (Plan, optional): A plan object.
    """

    content: str
    accepted: bool = False
    plan: Optional[Plan] = None

    @classmethod
    def from_str(cls, input_str: str) -> "HumanInputFormat":
        """Load HumanInputFormat from a string after validation."""
        try:
            data = json.loads(input_str)
            if not isinstance(data, dict):
                raise ValueError("Input string must be a JSON object")
        except (json.JSONDecodeError, ValueError):
            data = {"content": input_str}
        assert isinstance(data, dict)

        return cls(
            content=str(data.get("content", "")),  # type: ignore
            accepted=bool(data.get("accepted", False)),  # type: ignore
            plan=Plan.from_list_of_dicts_or_str(data.get("plan", [])),  # type: ignore
        )

    @classmethod
    def from_dict(cls, input_dict: Dict[str, Any]) -> "HumanInputFormat":
        """Load HumanInputFormat from a dictionary after validation."""
        return cls(
            content=str(input_dict.get("content", "")),
            accepted=bool(input_dict.get("accepted", False)),
            plan=input_dict.get("plan", None),  # type: ignore
        )

    def to_dict(self) -> Dict[str, Any]:
        """Return the dictionary representation of the input."""
        return self.model_dump()

    def to_str(self) -> str:
        """Return the string representation of the input."""
        return json.dumps(self.model_dump())


class CheckpointEvent(BaseAgentEvent):
    state: str
    content: str = "Checkpoint"
    metadata: Dict[str, str] = {"internal": "yes"}

    def to_text(self) -> str:
        return "Checkpoint"


# ============================================================================
# Playwright Script Generation Types
# ============================================================================


class PlaywrightAction(BaseModel):
    """
    A class representing a single Playwright action.

    Attributes:
        action_type (str): The type of action (e.g., 'goto', 'click', 'fill', 'press', 'wait', 'scroll').
        selector (str, optional): CSS selector, XPath, or Playwright locator for the target element.
        value (str, optional): Value for fill/type actions, or URL for goto.
        description (str): Human-readable description of what this action does.
        wait_after (int, optional): Milliseconds to wait after this action. Default: 0
    """

    action_type: str
    selector: Optional[str] = None
    value: Optional[str] = None
    description: str
    wait_after: int = 0


class PlaywrightScript(BaseModel):
    """
    A class representing a complete Playwright script.

    Attributes:
        task (str): Description of what this script accomplishes.
        start_url (str): The initial URL to navigate to.
        actions (List[PlaywrightAction]): Sequence of actions to perform.
        viewport_width (int): Browser viewport width. Default: 1280
        viewport_height (int): Browser viewport height. Default: 720
    """

    task: str
    start_url: str
    actions: List[PlaywrightAction]
    viewport_width: int = 1280
    viewport_height: int = 720

    def to_python_script(self) -> str:
        """Generate a standalone Python Playwright script."""
        lines = [
            '"""',
            f"Playwright Script: {self.task}",
            "",
            "Auto-generated from Magentic-UI session.",
            "Run with: python script.py",
            '"""',
            "",
            "import asyncio",
            "from playwright.async_api import async_playwright",
            "",
            "",
            "async def main():",
            "    async with async_playwright() as p:",
            f"        browser = await p.chromium.launch(headless=False)",
            "        context = await browser.new_context(",
            f"            viewport={{'width': {self.viewport_width}, 'height': {self.viewport_height}}}",
            "        )",
            "        page = await context.new_page()",
            "",
            f'        # Navigate to start URL',
            f'        await page.goto("{self._escape_string(self.start_url)}")',
            "        await page.wait_for_load_state('networkidle')",
            "",
        ]

        for i, action in enumerate(self.actions):
            lines.append(f"        # Step {i + 1}: {action.description}")
            lines.extend(self._action_to_code(action))
            if action.wait_after > 0:
                lines.append(f"        await asyncio.sleep({action.wait_after / 1000})")
            lines.append("")

        lines.extend([
            '        print("Script completed successfully!")',
            "        await browser.close()",
            "",
            "",
            'if __name__ == "__main__":',
            "    asyncio.run(main())",
            "",
        ])

        return "\n".join(lines)

    def _escape_string(self, s: str) -> str:
        """Escape special characters for Python string literals."""
        return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")

    def _action_to_code(self, action: PlaywrightAction) -> List[str]:
        """Convert a single action to Python code lines."""
        code = []
        at = action.action_type.lower()
        selector = self._escape_string(action.selector) if action.selector else ""
        value = self._escape_string(action.value) if action.value else ""

        if at == "goto":
            code.append(f'        await page.goto("{value}")')
            code.append("        await page.wait_for_load_state('networkidle')")
        elif at == "click":
            code.append(f'        await page.locator("{selector}").click()')
        elif at == "fill":
            code.append(f'        await page.locator("{selector}").fill("{value}")')
        elif at == "type":
            code.append(f'        await page.locator("{selector}").type("{value}")')
        elif at == "press":
            code.append(f'        await page.keyboard.press("{value}")')
        elif at == "select":
            code.append(f'        await page.locator("{selector}").select_option("{value}")')
        elif at == "hover":
            code.append(f'        await page.locator("{selector}").hover()')
        elif at == "scroll":
            if value:
                code.append(f'        await page.evaluate("window.scrollBy(0, {value})")')
            else:
                code.append(f'        await page.locator("{selector}").scroll_into_view_if_needed()')
        elif at == "wait":
            if selector:
                code.append(f'        await page.locator("{selector}").wait_for()')
            else:
                # Safely parse wait time, defaulting to 1000ms if invalid
                try:
                    wait_time = int(float(value)) if value else 1000
                except (ValueError, TypeError):
                    wait_time = 1000
                code.append(f"        await asyncio.sleep({wait_time / 1000})")
        elif at == "screenshot":
            filename = value if value else "screenshot.png"
            code.append(f'        await page.screenshot(path="{filename}")')
        else:
            code.append(f"        # Unknown action type: {at}")

        return code
