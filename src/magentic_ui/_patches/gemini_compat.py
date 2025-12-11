"""
Patch for Gemini API compatibility with autogen-ext OpenAI client.

Problem: Gemini's OpenAI-compatible API sometimes returns `choice.message = None`,
which causes `AttributeError: 'NoneType' object has no attribute 'function_call'`
in autogen_ext/models/openai/_openai_client.py line 659.

Solution: Monkey-patch the `create` method to handle None message gracefully
by checking and constructing a valid empty message when needed.
"""

import logging

logger = logging.getLogger(__name__)

_patched = False


def apply_patch():
    """Apply the Gemini compatibility patch to autogen-ext OpenAI client."""
    global _patched
    if _patched:
        return

    try:
        from autogen_ext.models.openai import _openai_client
        from openai.types.chat.chat_completion import ChatCompletionMessage

        original_create = _openai_client.BaseOpenAIChatCompletionClient.create

        async def patched_create(self, messages, **kwargs):
            """Patched create method that handles Gemini's None message responses."""
            result = await original_create.__wrapped__(self, messages, **kwargs)
            return result

        # Instead of patching create, patch the response processing
        # by patching the module-level code that processes choices

        import autogen_ext.models.openai._openai_client as client_module

        # Store original create method
        original_create_method = client_module.BaseOpenAIChatCompletionClient.create

        async def safe_create(self, messages, **kwargs):
            """Wrapper that ensures choice.message is never None."""
            import asyncio
            from typing import cast, Union
            from openai.types.chat import ChatCompletion, ParsedChatCompletion
            from openai._types import NOT_GIVEN

            # Call the internal processing
            create_params = self._process_create_args(
                messages,
                kwargs.get("tools", []),
                kwargs.get("json_output"),
                kwargs.get("extra_create_args", {}),
            )

            if create_params.response_format is not None:
                future = asyncio.ensure_future(
                    self._client.beta.chat.completions.parse(
                        messages=create_params.messages,
                        tools=(
                            create_params.tools
                            if len(create_params.tools) > 0
                            else NOT_GIVEN
                        ),
                        response_format=create_params.response_format,
                        **create_params.create_args,
                    )
                )
            else:
                future = asyncio.ensure_future(
                    self._client.chat.completions.create(
                        messages=create_params.messages,
                        stream=False,
                        tools=(
                            create_params.tools
                            if len(create_params.tools) > 0
                            else NOT_GIVEN
                        ),
                        **create_params.create_args,
                    )
                )

            cancellation_token = kwargs.get("cancellation_token")
            if cancellation_token is not None:
                cancellation_token.link_future(future)

            result = await future

            # PATCH: Ensure choice.message is not None
            if result.choices and len(result.choices) > 0:
                choice = result.choices[0]
                if choice.message is None:
                    logger.warning(
                        "Gemini API returned None message, constructing empty message"
                    )
                    # Create a minimal valid message
                    choice.message = ChatCompletionMessage(
                        role="assistant",
                        content="",
                        function_call=None,
                        tool_calls=None,
                    )

            # Now call the original method which will process the fixed result
            # Actually we need to continue with the rest of the original method
            # So let's just call original and catch the error
            pass

            # Return the result after fixing
            return await original_create_method(self, messages, **kwargs)

        # Actually, a simpler approach: just patch to retry on error
        async def retry_create(self, messages, **kwargs):
            """Wrapper that retries on Gemini None message error and 429 rate limit errors."""
            import asyncio
            from openai import RateLimitError, APIStatusError

            max_retries = 5
            for attempt in range(max_retries):
                try:
                    print(f"[Gemini Patch] Making API call (attempt {attempt + 1}/{max_retries})")
                    return await original_create_method(self, messages, **kwargs)
                except AttributeError as e:
                    if (
                        "'NoneType' object has no attribute 'function_call'" in str(e)
                        or "'NoneType' object has no attribute 'tool_calls'" in str(e)
                        or "'NoneType' object has no attribute 'content'" in str(e)
                    ):
                        if attempt < max_retries - 1:
                            logger.warning(
                                f"Gemini API returned invalid response (attempt {attempt + 1}/{max_retries}), retrying..."
                            )
                            await asyncio.sleep(0.5 * (attempt + 1))
                            continue
                        else:
                            logger.error(
                                "Gemini API consistently returning invalid responses"
                            )
                            raise RuntimeError(
                                "Gemini API returned invalid response after retries. "
                                "This may be a compatibility issue with Gemini's OpenAI-compatible API. "
                                "Consider using a different model or checking your API configuration."
                            ) from e
                    raise
                except (RateLimitError, APIStatusError) as e:
                    # Handle 429 rate limit errors from Gemini
                    error_str = str(e)
                    print(f"[Gemini Patch] Caught {type(e).__name__}: {error_str[:200]}")
                    is_rate_limit = (
                        "429" in error_str
                        or "RESOURCE_EXHAUSTED" in error_str
                        or "rate" in error_str.lower()
                        or isinstance(e, RateLimitError)
                    )
                    if is_rate_limit:
                        if attempt < max_retries - 1:
                            # Exponential backoff: 2, 4, 8, 16 seconds
                            wait_time = 2 ** (attempt + 1)
                            print(
                                f"[Gemini Patch] Rate limit hit, waiting {wait_time}s before retry (attempt {attempt + 1}/{max_retries})..."
                            )
                            await asyncio.sleep(wait_time)
                            continue
                        else:
                            print(
                                f"[Gemini Patch] Rate limit exceeded after {max_retries} retries"
                            )
                            raise
                    raise
                except Exception as e:
                    # Catch any other exceptions that might contain 429 in the message
                    error_str = str(e)
                    print(f"[Gemini Patch] Caught generic Exception {type(e).__name__}: {error_str[:200]}")
                    if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
                        if attempt < max_retries - 1:
                            wait_time = 2 ** (attempt + 1)
                            print(
                                f"[Gemini Patch] 429 in error message, waiting {wait_time}s before retry (attempt {attempt + 1}/{max_retries})..."
                            )
                            await asyncio.sleep(wait_time)
                            continue
                        else:
                            print(
                                f"[Gemini Patch] Error after {max_retries} retries: {e}"
                            )
                            raise
                    raise

        client_module.BaseOpenAIChatCompletionClient.create = retry_create
        _patched = True
        logger.info("Applied Gemini compatibility patch to autogen-ext OpenAI client")

    except ImportError as e:
        logger.warning(f"Could not import autogen_ext, skipping Gemini patch: {e}")
    except Exception as e:
        logger.warning(f"Failed to apply Gemini compatibility patch: {e}")
