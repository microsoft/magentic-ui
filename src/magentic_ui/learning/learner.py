import json
from typing import Union, List, Optional
from autogen_agentchat.messages import TextMessage, MultiModalMessage
from autogen_core.models import ChatCompletionClient
from autogen_core.models import LLMMessage, UserMessage
from autogen_core.model_context import TokenLimitedChatCompletionContext
from ..types import Plan, PlaywrightScript


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


async def learn_script_from_messages(
    client: ChatCompletionClient,
    messages: List[Union[TextMessage, MultiModalMessage]],
) -> PlaywrightScript:
    """
    Given a sequence of chat messages from a web browsing session,
    extract the operations performed and generate a Playwright script.

    Args:
        client (ChatCompletionClient): The chat completion client to use.
        messages (List[TextMessage | MultiModalMessage]): Chat messages from the session.

    Returns:
        PlaywrightScript: A structured representation of the Playwright script.
    """
    llm_messages: List[LLMMessage] = []
    for message in messages:
        llm_message = chat_msg_to_llm_message(message)
        llm_messages.append(llm_message)

    instruction_message = UserMessage(
        content=[
            """
You are an expert at extracting web automation steps from conversation logs.

The above messages are a conversation between a user and an AI assistant (web_surfer) that performed web browsing actions.
Your task is to extract the sequence of actions performed and convert them into a Playwright script.

IMPORTANT GUIDELINES:

1. **Identify the Start URL**: Find the first URL visited or the URL where the task began.

2. **Extract Actions**: For each action performed, identify:
   - action_type: One of 'goto', 'click', 'fill', 'type', 'press', 'select', 'hover', 'scroll', 'wait'
   - selector: Generate a STABLE CSS selector or Playwright locator that will work reliably:
     * Prefer: data-testid, id, name attributes (e.g., "[data-testid='submit-btn']", "#login-form", "input[name='email']")
     * Use role-based selectors: "button:has-text('Submit')", "a:has-text('Login')"
     * Use text content: "text=Submit", "text=Click here"
     * Avoid: Dynamic classes, nth-child with high numbers, complex XPath
   - value: For fill/type actions, the text entered; for goto, the URL
   - description: Brief description of what this step does

3. **Generate Robust Selectors**: Based on the conversation context:
   - If the assistant mentions clicking a "Submit" button, use: "button:has-text('Submit')" or "[type='submit']"
   - If filling an email field, use: "input[type='email']" or "input[name='email']" or "#email"
   - If clicking a link with specific text, use: "a:has-text('Link Text')"

4. **Order Actions Logically**: Actions should be in the exact order they were performed.

5. **Include Wait Actions**: Add appropriate waits between actions that trigger page loads or async operations.

Example output structure:
{
  "task": "Login to the website and navigate to dashboard",
  "start_url": "https://example.com",
  "actions": [
    {"action_type": "fill", "selector": "input[name='email']", "value": "user@example.com", "description": "Enter email address", "wait_after": 0},
    {"action_type": "fill", "selector": "input[name='password']", "value": "password123", "description": "Enter password", "wait_after": 0},
    {"action_type": "click", "selector": "button[type='submit']", "value": null, "description": "Click login button", "wait_after": 2000},
    {"action_type": "click", "selector": "a:has-text('Dashboard')", "value": null, "description": "Navigate to dashboard", "wait_after": 1000}
  ],
  "viewport_width": 1280,
  "viewport_height": 720
}

Please analyze the conversation and extract the Playwright script.
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
        extra_create_args={"response_format": PlaywrightScript},
    )

    response_content: Optional[str] = (
        response.content if isinstance(response.content, str) else None
    )

    if response_content is None:
        raise ValueError("Response content is not a valid JSON string")

    script = PlaywrightScript.model_validate(json.loads(response_content))

    return script
