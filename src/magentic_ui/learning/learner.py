import json
from typing import Union, List, Optional
from autogen_agentchat.messages import TextMessage, MultiModalMessage
from autogen_core.models import ChatCompletionClient
from autogen_core.models import LLMMessage, UserMessage
from autogen_core.model_context import TokenLimitedChatCompletionContext
from ..types import Plan


def chat_msg_to_llm_message(
    message: Union[TextMessage, MultiModalMessage],
) -> LLMMessage:
    if isinstance(message, TextMessage):
        if isinstance(message.content, str):
            return UserMessage(
                content=[message.content],
                source="user" if isinstance(message, TextMessage) else "magentic-ui",
            )
        else:
            raise ValueError(f"Unsupported content type: {type(message.content)}")
    elif isinstance(message, MultiModalMessage):
        return UserMessage(content=message.content, source="magentic-ui")
    else:
        raise ValueError(f"Unsupported message type: {type(message)}")


async def learn_plan_from_messages(
    client: ChatCompletionClient,
    messages: List[Union[TextMessage, MultiModalMessage]],
) -> Plan:
    """
    Given a sequence of chat messages, use structured outputs to create a draft of parameterized plan.

    Args:
        client (ChatCompletionClient): The chat completion client to use for generating the plan.
        messages (List[TextMessage | MultiModalMessage]): A list of chat messages to learn the plan from.

    Returns:
        Plan: The learned plan.
    """
    llm_messages: List[LLMMessage] = []
    for message in messages:
        llm_message = chat_msg_to_llm_message(message)
        llm_messages.append(llm_message)

    instruction_message = UserMessage(
        content=[
            """
The above messages are a conversation between a user and an AI assistant.
The AI assistant helped the user with their task and arrived potentially at a "Final Answer" to accomplish their task.

We want to be able to learn a plan from the conversation that can be used to accomplish the task as efficiently as possible.
This plan should help us accomplish this task and tasks similar to it more efficiently in the future as we learned from the mistakes and successes of the AI assistant and the details of the conversation.

Guidelines:
- We want the most efficient and direct plan to accomplish the task. The less number of steps, the better. Some agents can perform multiple steps in one go.
- We don't need to repeat the exact sequence of the conversation, but rather we need to focus on how to get to the final answer most efficiently without directly giving the final answer.
- Include details about the actions performed, buttons clicked, urls visited if they are useful.
For instance, if the plan was trying to find the github stars of autogen and arrived at the link https://github.com/microsoft/autogen then mention that link.
Or if the web surfer clicked a specific button to create an issue, mention that button.

Here is an example of a plan that the AI assistant might follow:

Example:

User request: "On which social media platform does Autogen have the most followers?"

Step 1:
- title: "Find all social media platforms that Autogen is on"
- details: "1) do a search for autogen social media platforms using Bing, 2) find the official link for autogen where the social media platforms might be listed, 3) report back all the social media platforms that Autogen is on"
- agent_name: "web_surfer"

Step 2:
- title: "Find the number of followers on Twitter"
- details: "Go to the official link for autogen on the web and find the number of followers on Twitter"
- agent_name: "web_surfer"

Step 3:
- title: "Find the number of followers on LinkedIn"
- details: "Go to the official link for autogen on the web and find the number of followers on LinkedIn"
- agent_name: "web_surfer"

Please provide the plan from the conversation above. Again, DO NOT memorize the final answer in the plan.
            """
        ],
        source="user",
    )

    # Create token limited context
    model_context = TokenLimitedChatCompletionContext(client, token_limit=110000)
    await model_context.clear()
    await model_context.add_message(instruction_message)
    for msg in llm_messages:
        await model_context.add_message(msg)
    token_limited_messages = await model_context.get_messages()

    response = await client.create(
        messages=token_limited_messages,
        extra_create_args={"response_format": Plan},
    )

    response_content: Optional[str] = (
        response.content if isinstance(response.content, str) else None
    )

    if response_content is None:
        raise ValueError("Response content is not a valid JSON string")

    plan = Plan.model_validate(json.loads(response_content))

    return plan


async def adapt_plan(client: ChatCompletionClient, plan: Plan, task: str) -> Plan:
    """
    Given a plan and new task, adapt the plan to the new task.

    Args:
        client (ChatCompletionClient): The chat completion client to use for adapting the plan.
        plan (Plan): The plan to adapt.
        task (str): The new task to adapt the plan to.

    Returns:
        Plan: The adapted plan.
    """

    instruction_message = UserMessage(
        content=["Adapt the following plan to the new task."],
        source="user",
    )
    plan_message = UserMessage(
        content=[json.dumps(plan.model_dump())],
        source="user",
    )
    task_message = UserMessage(
        content=[task],
        source="user",
    )

    response = await client.create(
        messages=[instruction_message, plan_message, task_message],
        extra_create_args={"response_format": Plan},
    )

    response_content: Optional[str] = (
        response.content if isinstance(response.content, str) else None
    )

    if response_content is None:
        raise ValueError("Response content is not a valid JSON string")

    adapted_plan = Plan.model_validate(json.loads(response_content))

    return adapted_plan
