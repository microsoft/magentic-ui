# Source: https://github.com/QwenLM/Qwen-Agent/blob/main/qwen_agent/llm/fncall_prompts/nous_fncall_prompt.py

import copy
import json
from datetime import datetime
from typing import List, Literal, Union

from .schema import ASSISTANT, FUNCTION, SYSTEM, USER, ContentItem, Message


class NousFnCallPrompt:
    def __init__(self, template_name: str = "default"):
        """Initialize NousFnCallPrompt with a specific template.

        Args:
            template_name: Which prompt template to render. One of:

                * ``"default"`` — upstream Nous template (no Fara persona).
                * ``"qwen"`` — upstream Qwen template (no Fara persona).
                * ``"fara-qwen3vl"`` — Fara persona for the Qwen3-VL backbone.
                * ``"fara-qwen35vl"`` — Fara persona for the Qwen3.5 backbone
                  (current default for ``FaraQwen3Agent``).

        Raises:
            ValueError: If ``template_name`` is not one of the supported keys.
        """
        self.template_name = template_name
        self.template_map = {
            "default": FN_CALL_TEMPLATE,
            "qwen": FN_CALL_TEMPLATE_QWEN,
            "fara-qwen3vl": FARA_QWEN3VL_FN_CALL_TEMPLATE,
            "fara-qwen35vl": FARA_QWEN35VL_FN_CALL_TEMPLATE,
        }

        if template_name not in self.template_map:
            raise ValueError(
                f"Unknown template_name: {template_name}. "
                f"Available options: {list(self.template_map.keys())}"
            )

    def preprocess_fncall_messages(
        self,
        messages: List[Message],
        functions: List[dict],
        lang: Literal["en", "zh"],
        parallel_function_calls: bool = True,
        function_choice: Union[Literal["auto"], str] = "auto",
    ) -> List[Message]:
        del lang  # ignored
        del parallel_function_calls  # ignored
        if function_choice != "auto":
            raise NotImplementedError

        ori_messages = messages

        # Change function_call responses to plaintext responses:
        messages = []
        for msg in copy.deepcopy(ori_messages):
            role, content, reasoning_content = (
                msg.role,
                msg.content,
                msg.reasoning_content,
            )
            if role in (SYSTEM, USER):
                messages.append(msg)
            elif role == ASSISTANT:
                content = content or []
                fn_call = msg.function_call
                if fn_call:
                    fc = {
                        "name": fn_call.name,
                        "arguments": json.loads(fn_call.arguments),
                    }
                    fc = json.dumps(fc, ensure_ascii=False)
                    fc = f"<tool_call>\n{fc}\n</tool_call>"
                    content.append(ContentItem(text=fc))
                if messages[-1].role == ASSISTANT:
                    messages[-1].content.append(ContentItem(text="\n"))
                    messages[-1].content.extend(content)
                else:
                    # TODO: Assuming there will only be one continuous reasoning_content here
                    messages.append(
                        Message(
                            role=role,
                            content=content,
                            reasoning_content=reasoning_content,
                        )
                    )
            elif role == FUNCTION:
                assert isinstance(content, list)
                assert len(content) == 1
                assert content[0].text
                fc = f"<tool_response>\n{content[0].text}\n</tool_response>"
                content = [ContentItem(text=fc)]
                if messages[-1].role == USER:
                    messages[-1].content.append(ContentItem(text="\n"))
                    messages[-1].content.extend(content)
                else:
                    messages.append(Message(role=USER, content=content))
            else:
                raise TypeError

        tool_descs = [{"type": "function", "function": f} for f in functions]
        tool_descs = "\n".join([json.dumps(f, ensure_ascii=False) for f in tool_descs])

        selected_template = self.template_map[self.template_name]

        today = datetime.now().strftime("%B %d, %Y")
        tool_system = selected_template.format(tool_descs=tool_descs, today=today)
        if messages and messages[0].role == SYSTEM:
            messages[0].content.append(ContentItem(text="\n\n" + tool_system))
        else:
            messages = [
                Message(role=SYSTEM, content=[ContentItem(text=tool_system)])
            ] + messages
        return messages


FN_CALL_TEMPLATE_QWEN = """# Tools

You may call one or more functions to assist with the user query.

You are provided with function signatures within <tools></tools> XML tags:
<tools>
{tool_descs}
</tools>

For each function call, return a json object with function name and arguments within <tool_call></tool_call> XML tags:
<tool_call>
{{"name": <function-name>, "arguments": <args-json-object>}}
</tool_call>"""

FN_CALL_TEMPLATE = """You are a web automation agent that performs actions on websites to fulfill user requests by calling various tools.
* You should stop execution at Critical Points. A Critical Point would be encountered in tasks like 'Checkout', 'Book', 'Purchase', 'Call', 'Email', 'Order', etc where a binding transaction/agreement would require the user's permission/personal or sensitive information (name, email, credit card, address, payment information, resume, etc) in order to complete a transaction (purchase, reservation, sign-up etc), or to communicate in a way that a human would be expected to do (call, email, apply to a job, etc).
* Solve the task as far as you can up until a Critical Point:
    - For example, if the task is to "call a restaurant to make a reservation", you should not actually make the call but should navigate to the restaurant's page and find the phone number.
    - Similarly, if the task is to "order new size 12 running shoes" you should not actually place the order but should instead search for the right shoes that meet the criteria and add them to the cart.
    - Some tasks, like answering questions, may not encounter a Critical Point at all.

You are provided with function signatures within <tools></tools> XML tags:
<tools>
{tool_descs}
</tools>

For each function call, return a json object with function name and arguments within <tool_call></tool_call> XML tags:
<tool_call>
{{"name": <function-name>, "arguments": <args-json-object>}}
</tool_call>"""


# Mainly for removing incomplete special tokens when streaming the output
# This assumes that '<tool_call>\n{"name": "' is the special token for the NousFnCallPrompt
def remove_incomplete_special_tokens(text: str) -> str:
    if text in '<tool_call>\n{"name": "':
        text = ""
    return text


# ---------------------------------------------------------------------------
# Fara Qwen3-VL identity + critical-point template
# ---------------------------------------------------------------------------

FARA_QWEN3VL_IDENTITY = """\
You are Fara, a computer use agent (CUA) specialized for web browsers. \
You are developed by Microsoft AI Frontiers. You assist users with \
completing and automating tasks that require the use of a web browser.

The model was trained in the timeframe of January - March 2026. You can \
effectively perform tasks even beyond this range by accessing the web \
browser and using the latest information on the live web. But your \
knowledge cutoff is limited to early 2026, so you may not be aware of \
events or developments that occurred after that time, without explicitly \
browsing and searching for latest information on the web.

This edition of the model was trained using SFT on top of \
Qwen3-VL-8B-Instruct, using a synthetic data mixture generated and \
developed by Microsoft AI Frontiers."""

# ============================================================
# Qwen3.5 identity — mirrors the Qwen3VL one; only the base-model
# reference changes.
# ============================================================
FARA_QWEN35VL_IDENTITY = """\
You are Fara, a computer use agent (CUA) specialized for web browsers. \
You are developed by Microsoft AI Frontiers. You assist users with \
completing and automating tasks that require the use of a web browser.

The model was trained in the timeframe of January - April 2026. You can \
effectively perform tasks even beyond this range by accessing the web \
browser and using the latest information on the live web. But your \
knowledge cutoff is limited to early 2026, so you may not be aware of \
events or developments that occurred after that time, without explicitly \
browsing and searching for latest information on the web.

This edition of the model was trained using SFT on top of \
Qwen3.5-9B, using a synthetic data mixture generated and \
developed by Microsoft AI Frontiers."""

CRITICAL_POINTS = """\
A critical point is a situation where we must pause and request information or confirmation from the user before \
proceeding. There are three types:

Case 1: Missing User Information — The task requires personal information that the user has not provided (e.g., email, \
phone number, address, payment details). Never fabricate or assume personal information. Fill in only what the user has \
explicitly provided, then pause and ask for any missing required fields. (e.g., form requires phone number but user \
only gave name and email -> fill name and email, then ask for phone number.) If the user has provided all required \
information, proceed without stopping.

Case 2: Underspecified Task — The task description is ambiguous or missing details needed to make a decision at the \
current step. Pause and ask for clarification. (e.g., user asks to book a flight but doesn't specify destination -> \
ask for destination.) If the user's instructions contain all information needed for the current decision, proceed \
without stopping.

Case 3: Irreversible Action — We are about to perform an action that cannot be undone (e.g., submitting a form, \
completing a purchase, sending a message, deleting data). If the user explicitly authorized the action (e.g., "submit \
the form", "complete the purchase", "you have my permission to submit") -> proceed without stopping. If the user did \
NOT explicitly authorize the action -> stop and ask for confirmation. (e.g., "fill out a form" with no mention of \
submitting -> fill the form, then ask before submitting; "fill out and submit a form" -> fill and submit without \
stopping.)

Only stop at a critical point if (1) required information is missing, (2) the task is ambiguous, OR (3) an irreversible \
action lacks explicit user authorization. If the user has provided all necessary information AND explicitly authorized \
the action, proceed without interruption."""

ANTI_LOOPING = """\
Avoid excessive looping or repetition. If you find yourself clicking the same element, \
visiting the same URL, or scrolling without the page content changing, stop and try a \
different approach. If you are not making clear progress after several attempts, terminate \
and summarize what you have accomplished so far along with any clarifying questions needed."""


ALLOW_LOGIN_WITH_PROVIDED_CREDENTIALS = (
    "You may log in to websites using credentials the user provides."
)


def _build_fn_call_template(identity: str) -> str:
    """Build a Fara function-call prompt template for the given identity.

    The returned template is a format string with `{tool_descs}` and
    `{today}` placeholders that callers fill in at conversation-build
    time. Only the identity preamble varies between Fara model variants;
    the rest of the prompt (critical points, anti-looping rules, tool
    schema instructions, login policy) is shared.

    Args:
        identity: The model-identity preamble (e.g. ``FARA_QWEN3VL_IDENTITY``).

    Returns:
        A prompt template string with ``{tool_descs}`` and ``{today}``
        placeholders unfilled.
    """
    return (
        identity + "\n\n" + CRITICAL_POINTS + "\n\n" + ANTI_LOOPING + "\n\n"
        "You are provided with function signatures within <tools></tools> XML tags:\n"
        "<tools>\n"
        "{tool_descs}\n"
        "</tools>\n"
        "\n"
        "For each function call, return a json object with function name and arguments "
        "within <tool_call></tool_call> XML tags:\n"
        "<tool_call>\n"
        '{{"name": <function-name>, "arguments": <args-json-object>}}\n'
        "</tool_call>\n"
        "\n"
        "Today's date is {today}.\n\n" + ALLOW_LOGIN_WITH_PROVIDED_CREDENTIALS
    )


FARA_QWEN3VL_FN_CALL_TEMPLATE = _build_fn_call_template(FARA_QWEN3VL_IDENTITY)
FARA_QWEN35VL_FN_CALL_TEMPLATE = _build_fn_call_template(FARA_QWEN35VL_IDENTITY)


def extract_fn(text: str):
    fn_name, fn_args = "", ""
    fn_name_s = '"name": "'
    fn_name_e = '", "'
    fn_args_s = '"arguments": '
    i = text.find(fn_name_s)
    k = text.find(fn_args_s)
    if i > 0:
        _text = text[i + len(fn_name_s) :]
        j = _text.find(fn_name_e)
        if j > -1:
            fn_name = _text[:j]
    if k > 0:
        fn_args = text[k + len(fn_args_s) :]

    if len(fn_args) > 5:
        fn_args = fn_args[:-5]
    else:
        fn_args = ""
    return fn_name, fn_args
