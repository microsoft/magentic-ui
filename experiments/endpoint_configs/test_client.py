import yaml
import asyncio
from autogen_core.models import ChatCompletionClient, UserMessage


async def test_chat_completion_client() -> None:
    # Load the config file
    print("Loading config...")
    with open("config.yaml", "r") as f:
        config = yaml.safe_load(f)

    # Get the orchestrator client config
    client_config = config.get("orchestrator_client")
    print(f"Loaded client config: {client_config}")

    # Initialize the client
    print("Initializing client...")
    client = ChatCompletionClient.load_component(client_config)

    # Test a simple completion
    print("Testing completion...")
    response = await client.create(
        messages=[UserMessage(content="Say hello", source="user")]
    )
    print(f"Response content: {response.content}")

    await client.close()


if __name__ == "__main__":
    asyncio.run(test_chat_completion_client())
