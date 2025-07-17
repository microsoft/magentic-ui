from typing import Tuple
from playwright.async_api import Page
import asyncio


class AnimationUtilsPlaywright:
    """
    A utility class for handling cursor animations and visual effects in Playwright.
    """

    def __init__(self) -> None:
        self.last_cursor_position: Tuple[float, float] = (0.0, 0.0)

    async def add_cursor_box(self, page: Page, identifier: str) -> None:
        """
        Highlight the element with the given identifier and insert a custom cursor on the page.

        Args:
            page (Page): The Playwright page object.
            identifier (str): The element identifier.
        """
        try:
            # 1. Highlight the element (if it exists)
            await page.evaluate(
                """
                (identifier) => {
                    const elm = document.querySelector(`[__elementId='${identifier}']`);
                    if (elm) {
                        elm.style.transition = 'border 0.1s ease-in-out';
                        elm.style.border = '2px solid red';
                    }
                }
                """,
                identifier,
            )

            # Give time for the border transition
            await asyncio.sleep(0.1)

            # 2. Create a custom cursor (only if it doesn't already exist)
            await page.evaluate(
                """
                () => {
                    let cursor = document.getElementById('red-cursor');
                    if (!cursor) {
                        cursor = document.createElement('div');
                        cursor.id = 'red-cursor';
                        cursor.style.width = '12px';
                        cursor.style.height = '12px';
                        cursor.style.position = 'absolute';
                        cursor.style.borderRadius = '50%';
                        cursor.style.zIndex = '999999';        // Large z-index to appear on top
                        cursor.style.pointerEvents = 'none';    // Don't block clicks
                        // A nicer cursor: red ring with a white highlight and a soft shadow
                        cursor.style.background = 'radial-gradient(circle at center, #fff 20%, #f00 100%)';
                        cursor.style.boxShadow = '0 0 6px 2px rgba(255,0,0,0.5)';
                        cursor.style.transition = 'left 0.05s linear, top 0.05s linear';
                        document.body.appendChild(cursor);
                    }
                }
                """
            )
        except Exception:
            pass

    async def gradual_cursor_animation(
        self,
        page: Page,
        start_x: float,
        start_y: float,
        end_x: float,
        end_y: float,
        steps: int = 10,
        step_delay: float = 0.02,
    ) -> None:
        """
        Animate the cursor movement gradually from start to end coordinates.

        Args:
            page (Page): The Playwright page object.
            start_x (float): The starting x-coordinate.
            start_y (float): The starting y-coordinate.
            end_x (float): The ending x-coordinate.
            end_y (float): The ending y-coordinate.
            steps (int, optional): Number of small steps for the movement. Default: 10
            step_delay (float, optional): Delay (in seconds) between steps. Default: 0.02
        """
        # Ensure the cursor is on the page
        try:
            for step in range(steps):
                # Linear interpolation
                x = start_x + (end_x - start_x) * (step / steps)
                y = start_y + (end_y - start_y) * (step / steps)

                # Move the cursor via JS
                await page.evaluate(
                    """
                    ([x, y]) => {
                        const cursor = document.getElementById('red-cursor');
                        if (cursor) {
                            cursor.style.left = x + 'px';
                            cursor.style.top = y + 'px';
                        }
                    }
                    """,
                    [x, y],
                )

                await asyncio.sleep(step_delay)

            # Final position
            await page.evaluate(
                """
                ([x, y]) => {
                    const cursor = document.getElementById('red-cursor');
                    if (cursor) {
                        cursor.style.left = x + 'px';
                        cursor.style.top = y + 'px';
                    }
                }
                """,
                [end_x, end_y],
            )
        except Exception:
            pass
            # Store last cursor position if needed
        self.last_cursor_position = (end_x, end_y)

    async def remove_cursor_box(self, page: Page, identifier: str) -> None:
        """
        Remove the highlight from the element and the custom cursor from the page.

        Args:
            page (Page): The Playwright page object.
            identifier (str): The element identifier.
        """
        try:
            await page.evaluate(
                """
                (identifier) => {
                    // Remove highlight
                    const elm = document.querySelector(`[__elementId='${identifier}']`);
                    if (elm) {
                        elm.style.border = '';
                    }
                    // Remove cursor
                    const cursor = document.getElementById('red-cursor');
                    if (cursor) {
                        cursor.remove();
                    }
                }
                """,
                identifier,
            )
        except Exception:
            pass

    async def cleanup_animations(self, page: Page) -> None:
        """
        Clean up any cursor animations or highlights that were added by animate_actions.
        This includes removing the red cursor element and any element highlights.

        Args:
            page (Page): The Playwright page object.
        """
        try:
            # Remove cursor and highlights using the same approach as in remove_cursor_box
            await page.evaluate(
                """
                () => {
                    // Remove cursor
                    const cursor = document.getElementById('red-cursor');
                    if (cursor) {
                        cursor.remove();
                    }
                    // Remove highlights from all elements
                    const elements = document.querySelectorAll('[__elementId]');
                    elements.forEach(el => {
                        if (el.style.border && el.style.transition) {
                            el.style.border = '';
                            el.style.transition = '';
                        }
                    });
                }
                """
            )
            # Reset the last cursor position
            self.last_cursor_position = (0.0, 0.0)
        except Exception:
            pass
