import asyncio
import argparse
from autogen_agentchat.ui import Console
from autogen_ext.models.openai import OpenAIChatCompletionClient
from autogen_agentchat.conditions import TextMentionTermination
from magentic_ui.agents import CoderAgent
from magentic_ui.teams import RoundRobinGroupChat
from autogen_agentchat.agents import UserProxyAgent


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--work_dir",
        type=str,
        default="debug",
        help="Directory where coder will save files",
    )
    args = parser.parse_args()
    model_client = OpenAIChatCompletionClient(model="gpt-4o")

    termination = TextMentionTermination("EXITT")

    user_proxy = UserProxyAgent(name="user_proxy")

    coder = CoderAgent(
        name="coder_agent",
        model_client=model_client,
        work_dir=args.work_dir,
        bind_dir=args.work_dir,
    )

    team = RoundRobinGroupChat(
        participants=[coder, user_proxy],
        max_turns=30,
        termination_condition=termination,
    )
    await team.lazy_init()
    user_message = await asyncio.get_event_loop().run_in_executor(None, input, ">: ")

    stream = team.run_stream(task=user_message)
    await Console(stream)


if __name__ == "__main__":
    asyncio.run(main())
