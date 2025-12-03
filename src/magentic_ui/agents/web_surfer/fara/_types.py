"""Local types for FaraWebSurfer.

Contains:
- ImageObj / LLMMessage: Internal LLM conversation message types
- StreamUpdate: Yielded from run_stream()
- BrowserEnvironment: ABC for coordinate-based browser automation
"""

from __future__ import annotations

import base64
import io
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Literal, Tuple

from PIL import Image


# ---------------------------------------------------------------------------
# LLM message types
# ---------------------------------------------------------------------------


@dataclass
class ImageObj:
    """Image wrapper for handling screenshots and images.

    Holds a PIL Image and encodes lazily on demand.
    """

    image: Image.Image

    @classmethod
    def from_pil(cls, image: Image.Image) -> ImageObj:
        return cls(image=image)

    def to_base64(self) -> str:
        """Convert PIL image to base64 string."""
        buf = io.BytesIO()
        self.image.save(buf, format="PNG")
        return base64.b64encode(buf.getvalue()).decode("utf-8")

    def resize(self, size: Tuple[int, int]) -> Image.Image:
        """Resize the image."""
        return self.image.resize(size)


@dataclass
class LLMMessage:
    """A message in the internal LLM conversation history.

    Uses ``role`` directly to match the OpenAI API.
    """

    role: Literal["system", "user", "assistant"]
    content: str | list[str | ImageObj]
    metadata: dict[str, Any] | None = None

    def to_openai_dict(self) -> dict[str, Any]:
        """Convert to OpenAI Chat Completions API message format."""
        if isinstance(self.content, str):
            return {"role": self.role, "content": self.content}
        parts: list[dict[str, Any]] = []
        for item in self.content:
            if isinstance(item, str):
                parts.append({"type": "text", "text": item})
            elif isinstance(item, ImageObj):
                b64 = item.to_base64()
                parts.append(
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{b64}"},
                    }
                )
        return {"role": self.role, "content": parts}


# ---------------------------------------------------------------------------
# Streaming update
# ---------------------------------------------------------------------------


@dataclass
class StreamUpdate:
    """Yielded from ``run_stream()``."""

    text: str = ""
    additional_properties: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# BrowserEnvironment ABC
# ---------------------------------------------------------------------------


class BrowserEnvironment(ABC):
    """Abstract coordinate-based browser environment.

    Decouples the fara agent from Playwright specifics.  The agent calls
    these methods; ``PlaywrightBrowserEnvironment`` (in ``_browser_env.py``)
    provides the concrete implementation.

    For non-coordinate agents (DOM-based, API-based), implement
    ``SubAgentProtocol`` directly instead of this ABC.
    """

    # --- Core GUI actions (FaraAgent base) ---

    @abstractmethod
    async def left_click(self, x: float, y: float) -> None: ...

    @abstractmethod
    async def type_text(
        self,
        x: float,
        y: float,
        text: str,
        press_enter: bool = True,
        clear_first: bool = False,
    ) -> None: ...

    @abstractmethod
    async def key(self, keys: list[str]) -> None: ...

    @abstractmethod
    async def hover(self, x: float, y: float) -> None: ...

    @abstractmethod
    async def scroll_up(self, amount: int = 400) -> None: ...

    @abstractmethod
    async def scroll_down(self, amount: int = 400) -> None: ...

    @abstractmethod
    async def wait(self, duration: float) -> None: ...

    @abstractmethod
    async def get_screenshot(self) -> bytes: ...

    # --- Browser navigation ---

    @abstractmethod
    async def goto(self, url: str) -> None: ...

    @abstractmethod
    async def back(self) -> None: ...

    @abstractmethod
    async def get_url(self) -> str: ...

    # --- Extended actions (FaraQwen3NextAgent) ---

    @abstractmethod
    async def double_click(self, x: float, y: float) -> None: ...

    @abstractmethod
    async def right_click(self, x: float, y: float) -> None: ...

    @abstractmethod
    async def triple_click(self, x: float, y: float) -> None: ...

    @abstractmethod
    async def left_click_drag(self, end_x: float, end_y: float) -> None:
        """Drag from current cursor position to (end_x, end_y)."""
        ...

    @abstractmethod
    async def hscroll(self, pixels: int) -> None: ...

    @abstractmethod
    async def scroll_to(self, x: int, y: int) -> None:
        """Scroll the page to absolute (x, y) window coordinates."""
        ...

    @abstractmethod
    async def get_scroll(self) -> tuple[int, int]:
        """Return current (scrollX, scrollY) in window pixels."""
        ...

    @abstractmethod
    async def type_direct(self, text: str) -> None:
        """Type text without coordinates — types into the currently focused element."""
        ...

    # --- Page content ---

    @abstractmethod
    async def get_page_markdown(self) -> str: ...

    # --- Shell execution (optional — sandbox only) ---

    async def execute(self, command: str) -> str:
        """Execute a shell command. Override in sandbox environments."""
        raise NotImplementedError("Shell execution not available in this environment")

    # --- Lifecycle ---

    @abstractmethod
    async def wait_for_load(
        self,
        state: Literal["load", "domcontentloaded", "networkidle", "commit"] = "load",
        timeout: int | None = None,
    ) -> None: ...
