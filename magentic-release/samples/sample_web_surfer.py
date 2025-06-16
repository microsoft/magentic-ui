import argparse
import asyncio
from pathlib import Path
from autogen_agentchat.ui import Console
from autogen_ext.models.openai import OpenAIChatCompletionClient
from autogen_agentchat.conditions import TextMentionTermination
from autogen_agentchat.teams import RoundRobinGroupChat
from magentic_ui.agents import WebSurfer
from autogen_agentchat.agents import UserProxyAgent
import logging


from magentic_ui.tools.playwright import (
    HeadlessDockerPlaywrightBrowser,
    VncDockerPlaywrightBrowser,
    LocalPlaywrightBrowser,
)


# Configure logging
logging.basicConfig(level=logging.WARN)
logger = logging.getLogger("magentic_ui.tools.docker_browser").setLevel(logging.INFO)


async def main() -> None:
    """
    Main function to run the WebSurfer agent with a browser.

    Parses command line arguments, starts the browser, initializes agents,
    and runs the conversation.
    """
    parser = argparse.ArgumentParser(
        description="""
        Run WebSurfer with a Docker-based or local browser, supporting both headless and VNC (noVNC) modes.
        
        - By default, runs with a local Playwright browser.
        - Use --port to specify a port for a Dockerized Playwright browser (headless or with VNC).
        - Use --novnc-port to enable a noVNC web interface for browser interaction via your web browser.
        
        To view the browser via noVNC, open your web browser and navigate to:
            http://localhost:<novnc-port>/?autoconnect=1
        Replace <novnc-port> with the value you provide to --novnc-port (e.g., 6080).
        """
    )
    parser.add_argument(
        "--port",
        type=int,
        default=-1,
        help="Port to run the docker browser on (default: -1 means no browser)",
    )
    parser.add_argument(
        "--novnc-port",
        type=int,
        default=-1,
        help="""
        Port to run the noVNC server on (default: 6080). 
        If set, you can view and interact with the browser remotely by visiting 
        http://localhost:<novnc-port>/?autoconnect=1 in your web browser.
        """,
    )
    args = parser.parse_args()

    # Start the browser before initializing WebSurfer
    if args.port != -1 and args.novnc_port != -1:
        browser = VncDockerPlaywrightBrowser(
            bind_dir=Path("/tmp"),
            playwright_port=args.port,
            novnc_port=args.novnc_port,
            inside_docker=False,
        )
        print(f"Browser remote view: {browser.vnc_address}?autoconnect=1")
    elif args.port != -1:
        browser = HeadlessDockerPlaywrightBrowser(playwright_port=args.port)
    else:
        browser = LocalPlaywrightBrowser(headless=False)

    model_client = OpenAIChatCompletionClient(model="gpt-4o")

    termination = TextMentionTermination("Terminate")

    user_proxy = UserProxyAgent(name="user_proxy")

    web_surfer = WebSurfer(
        name="web_surfer",
        model_client=model_client,
        animate_actions=True,
        max_actions_per_step=10,
        single_tab_mode=False,
        downloads_folder="debug",
        debug_dir="debug",
        to_save_screenshots=False,
        browser=browser,
        multiple_tools_per_call=False,
        json_model_output=False,
        use_action_guard=False,
    )
    await web_surfer.lazy_init()

    team = RoundRobinGroupChat(
        participants=[web_surfer, user_proxy],
        max_turns=10,
        termination_condition=termination,
    )

    user_message = await asyncio.get_event_loop().run_in_executor(None, input, ">: ")

    try:
        stream = team.run_stream(task=user_message)
        await Console(stream)
    finally:
        # Make sure to close the WebSurfer before stopping the browser
        await web_surfer.close()


if __name__ == "__main__":
    asyncio.run(main())
