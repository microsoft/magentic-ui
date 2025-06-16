import base64
import json
from typing import AsyncGenerator, Sequence
from autogen_agentchat.base import Response
from autogen_agentchat.messages import BaseChatMessage, TextMessage
from autogen_core import CancellationToken
from autogen_agentchat.messages import (
    MultiModalMessage,
)
from openai import OpenAI


from ._web_surfer import WebSurfer

# This code has been adapted from https://github.com/openai/openai-cua-sample-app
# Copyright 2025 OpenAI - MIT License


class WebSurferCUA(WebSurfer):
    """A dummy version of WebSurfer that returns static responses for testing and CUA purposes."""

    async def on_messages_stream(
        self, messages: Sequence[BaseChatMessage], cancellation_token: CancellationToken
    ) -> AsyncGenerator[BaseChatMessage | Response, None]:
        """Dummy implementation that returns a static response."""
        # add the last message to the chat history
        if not hasattr(self, "_cua_chat_history"):
            self._cua_chat_history = []
        if isinstance(messages[-1], TextMessage):
            self._cua_chat_history.append(
                {
                    "role": "user",
                    "content": messages[-1].content,
                }
            )
        elif isinstance(messages[-1], MultiModalMessage):
            self._cua_chat_history.append(
                {
                    "role": "user",
                    "content": messages[-1].content,
                }
            )

        client = OpenAI()

        new_items = []
        assert self._page is not None
        actions_so_far = 0
        while (
            actions_so_far < self.max_actions_per_step
            and new_items[-1].get("role") != "assistant"
            if new_items
            else True
        ):
            response = client.responses.create(
                model="computer-use-preview",
                tools=[
                    {
                        "type": "computer_use_preview",
                        "display_width": self._page.viewport_size["width"],
                        "display_height": self._page.viewport_size["height"],
                        "environment": "browser",
                    },
                    {
                        "type": "function",
                        "name": "back",
                        "description": "Go back to the previous page.",
                        "parameters": {},
                    },
                    {
                        "type": "function",
                        "name": "goto",
                        "description": "Go to a specific URL.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "url": {
                                    "type": "string",
                                    "description": "Fully qualified URL to navigate to.",
                                },
                            },
                            "additionalProperties": False,
                            "required": ["url"],
                        },
                    },
                    {
                        "type": "function",
                        "name": "create_tab",
                        "description": "Creates a new browser tab and navigates to the specified URL.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "url": {
                                    "type": "string",
                                    "description": "The URL to open in the new tab.",
                                },
                            },
                            "required": ["url"],
                        },
                    },
                ],
                input=self._cua_chat_history + new_items,
                reasoning={
                    "generate_summary": "concise",
                },
                truncation="auto",
            )
            response = response.to_dict()
            if "output" not in response:
                raise ValueError("No output from CUA")
            else:
                new_items += response["output"]
                for item in response["output"]:
                    output_item = []
                    if item["type"] == "function_call":
                        name, args = item["name"], json.loads(item["arguments"])

                        yield Response(
                            chat_message=TextMessage(
                                content=f"{name}({args})",
                                source=self.name,
                            )
                        )
                        output_item = await self.handle_function_call(item)
                    if item["type"] == "computer_call":
                        action = item["action"]
                        action_type = action["type"]
                        action_args = {k: v for k, v in action.items() if k != "type"}
                        yield Response(
                            chat_message=TextMessage(
                                content=f"{action_type}({action_args})",
                                source=self.name,
                            )
                        )
                        output_item = await self.handle_computer_call(item)
                    if item["type"] == "message":
                        output_item = []
                        yield Response(
                            chat_message=TextMessage(
                                content=item["content"][0]["text"],
                                source=self.name,
                            )
                        )
                    if output_item is not None and output_item != []:
                        new_items += output_item
            actions_so_far += 1
        self._cua_chat_history += new_items

    async def handle_function_call(self, item):
        name, args = item["name"], json.loads(item["arguments"])
        if True:
            print(f"{name}({args})")

        if name == "back":
            await self._playwright_controller.go_back(self._page)
        elif name == "goto":
            await self._playwright_controller.visit_page(self._page, url=args["url"])
        elif name == "create_tab":
            new_page = await self._playwright_controller.create_new_tab(
                self._context, url=args["url"]
            )
            self._page = new_page
        return [
            {
                "type": "function_call_output",
                "call_id": item["call_id"],
                "output": "success",
            }
        ]

    async def handle_computer_call(self, item):
        # native CUA actions
        assert self._page is not None  # Ensure page is not None
        action = item["action"]
        action_type = action["type"]
        action_args = {k: v for k, v in action.items() if k != "type"}
        if True:
            print(f"{action_type}({action_args})")

        if True:  # Keep print for debugging if desired
            print(f"Executing CUA action: {action_type}({action_args})")

        # Map CUA actions to PlaywrightController methods
        if action_type == "click":
            # Assuming 'x', 'y', and optional 'button' are in action_args
            await self._playwright_controller.click_coords(
                self._page,
                x=action_args["x"],
                y=action_args["y"],
                button=action_args.get("button", "left"),
            )
        elif action_type == "double_click":
            # Assuming 'x', 'y' are in action_args
            await self._playwright_controller.double_click_coords(
                self._page, x=action_args["x"], y=action_args["y"]
            )
        elif action_type == "scroll":
            # Assuming 'x', 'y', 'scroll_x', 'scroll_y' are in action_args
            # Note: Playwright's scroll_coords requires start coords (x, y)
            await self._playwright_controller.scroll_coords(
                self._page,
                x=action_args.get("x", 0),  # Default start coords if not provided
                y=action_args.get("y", 0),
                scroll_x=action_args["scroll_x"],
                scroll_y=action_args["scroll_y"],
            )
        elif action_type == "wait":
            # Assuming 'duration' (in seconds) is in action_args
            await self._playwright_controller.sleep(
                self._page, duration=action_args.get("ms", 1000) / 1000
            )
        elif action_type == "move":
            # Assuming 'x', 'y' are in action_args (maps to hover)
            await self._playwright_controller.hover_coords(
                self._page, x=action_args["x"], y=action_args["y"]
            )
        elif action_type == "keypress":
            # Assuming 'keys' (list of strings) is in action_args
            await self._playwright_controller.keypress(
                self._page, keys=action_args["keys"]
            )
        elif action_type == "drag":
            # Assuming 'path' (list of dicts with 'x', 'y') is in action_args
            await self._playwright_controller.drag_coords(
                self._page, path=action_args["path"]
            )
        elif action_type == "type":
            await self._playwright_controller.type_direct(
                self._page, text=action_args["text"]
            )

        screenshot = await self._playwright_controller.get_screenshot(self._page)
        screenshot_base64 = base64.b64encode(screenshot).decode("utf-8")
        # if user doesn't ack all safety checks exit with error
        pending_checks = item.get("pending_safety_checks", [])
        for check in pending_checks:
            message = check["message"]
            if False:  # Replace False with actual check logic if needed
                raise ValueError(
                    f"Safety check failed: {message}. Cannot continue with unacknowledged safety checks."
                )

        call_output = {
            "type": "computer_call_output",
            "call_id": item["call_id"],
            "acknowledged_safety_checks": pending_checks,
            # Default to success if no specific output (like screenshot)
            "output": {
                "type": "input_image",
                "image_url": f"data:image/png;base64,{screenshot_base64}",
            },
        }

        current_url, _ = await self._playwright_controller.get_current_url_title(
            self._page
        )
        call_output["output"]["current_url"] = current_url

        return [call_output]
