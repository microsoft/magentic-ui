import asyncio
from autogen_agentchat.ui import Console
from autogen_ext.models.openai import OpenAIChatCompletionClient
from magentic_ui.teams.orchestrator.orchestrator_config import OrchestratorConfig
from magentic_ui import get_task_team
from magentic_ui.types import Plan
from autogen_ext.experimental.task_centric_memory import MemoryController
from autogen_ext.experimental.task_centric_memory.utils import PageLogger
from magentic_ui.learning import learn_plan_from_messages


"""
Steps to run this test:
1. Delete the memory bank folder "./memory_bank/magentic_ui" from a previous run.
2. Run this script.
    - View the results in progress by opening the "./pagelogs/magentic_ui/0  Call Tree.html" file in a browser.
    - No plans should be retrieved, unless two of the tasks are similar.
4. Run the script again.
    - Refresh the browser to see the new results.
    - All plans should be retrieved. If not, raise relevance_conversion_threshold below.
"""

list_of_tasks = [
    "Where does gagan bansal work based on his msr homepage",  # No plan to retrieve on the 1st run.
    "Where does ricky loynd work based on his homepage",  # No plan to retrieve on the 1st run.
    "Who is the employer of gagan bansal?",  # Should retrieve gagan's plan even on the 1st run.
]


async def try_task(
    task: str,
    memory_controller: MemoryController,
    client: OpenAIChatCompletionClient,
    logger: PageLogger,
) -> None:
    logger.enter_function()
    logger.info("Task: {}".format(task))

    # Try to retrieve memories/insights/plans relevant to this task.
    memos = await memory_controller.retrieve_relevant_memos(task=task)

    # Was a plan found?
    if len(memos) > 0:
        # Yes, a relevant plan was found. Log it and return.
        most_relevant_plan = memos[0].insight
        logger.info(
            "Relevant plan retrieved from memory:\n{}".format(most_relevant_plan)
        )
    else:
        # No relevant plan was found. We need to create one.
        logger.info("No relevant plan found. Let's create one.")

        # Create a magentic_ui team.
        orchestrator_config = OrchestratorConfig(
            cooperative_planning=False,
            autonomous_execution=True,
            allow_follow_up_input=False,
            max_stalls=3,
            plan_dict=Plan.model_validate_json(memos[0].insight)
            if len(memos) > 0
            else None,
        )
        team = await get_task_team(orchestrator_config)
        stream = team.run_stream(task=task)
        result = await Console(stream)

        # Create a plan from the result.
        plan = await learn_plan_from_messages(client, messages=result.messages)
        logger.info("New plan: {}".format(plan.model_dump_json()))

        # Add the plan to memory.
        await memory_controller.add_memo(
            task=task, insight=plan.model_dump_json(), index_on_both=False
        )

        # Close the agents.
        for agent in team._participants:
            if hasattr(agent, "close"):
                await agent.close()

    logger.leave_function()


async def main() -> None:
    logger = PageLogger(
        config={"level": "DEBUG", "path": "./pagelogs/magentic_ui"}
    )  # Optional, but very useful.
    logger.enter_function()
    client = OpenAIChatCompletionClient(model="gpt-4o")

    # Create the memory controller and memory bank.
    memory_bank_config = {
        "path": "./memory_bank/magentic_ui",
        "relevance_conversion_threshold": 1.7,  # Raise this value for more results, lower it for fewer.
    }
    memory_controller = MemoryController(
        reset=False,
        client=client,
        logger=logger,
        config={"MemoryBank": memory_bank_config},
    )

    # Try the tasks.
    logger.info("Loop through a few tasks.")
    for task in list_of_tasks:
        await try_task(
            task, memory_controller=memory_controller, client=client, logger=logger
        )

    logger.leave_function()
    logger.flush(finished=True)


if __name__ == "__main__":
    asyncio.run(main())
