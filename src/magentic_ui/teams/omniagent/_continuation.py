"""Max-rounds continuation flow for OmniAgent."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable

from loguru import logger

from ...agents.message_schemas import final_answer_props
from ...agents.web_surfer.fara._types import StreamUpdate
from ...types import ContinuationRequest


def is_subagent_user_stop(event: object) -> bool:
    """Whether ``event`` is a sub-agent's max-rounds stop final answer."""
    if not isinstance(event, StreamUpdate):
        return False
    props = event.additional_properties
    return props.get("type") == "final_answer" and bool(props.get("max_rounds_reached"))


async def handle_max_rounds_continuation(
    *,
    source_name: str,
    total_rounds: int,
    generate_final_answer: Callable[[], Awaitable[str]],
) -> AsyncIterator[StreamUpdate | ContinuationRequest | bool]:
    """Yield a Continue/Stop card and react to the user's choice.

    Yields exactly one terminal ``bool``: ``True`` to keep looping,
    ``False`` to stop. On stop, also yields a final-answer event built
    from ``generate_final_answer()`` before the terminal ``bool``.
    """
    prompt = (
        f"Orchestrator has taken {total_rounds} rounds without "
        "finishing the task. Continue?"
    )
    future: asyncio.Future[str] = asyncio.get_running_loop().create_future()
    yield ContinuationRequest(prompt=prompt, respond=future.set_result)
    resp = await future

    if resp.strip().lower().rstrip(".!,") == "yes":
        logger.info("Orchestrator continuation granted at %d rounds", total_rounds)
        yield True
        return

    logger.warning(
        "Orchestrator stopping at user request after %d rounds", total_rounds
    )
    final_answer = await generate_final_answer()
    yield StreamUpdate(
        text=final_answer,
        additional_properties=dict(
            final_answer_props(source=source_name, max_rounds_reached=True)
        ),
    )
    yield False
