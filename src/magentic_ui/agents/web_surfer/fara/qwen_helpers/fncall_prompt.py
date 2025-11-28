# Source: https://github.com/QwenLM/Qwen-Agent/blob/main/qwen_agent/llm/fncall_prompts/nous_fncall_prompt.py

import copy
import json
import os

from typing import List, Literal, Union

from .schema import ASSISTANT, FUNCTION, SYSTEM, USER, ContentItem, Message


class NousFnCallPrompt:
    def __init__(self, template_name: str = "default"):
        """Initialize NousFnCallPrompt with a specific template.

        Args:
            template_name: Name of the template to use. Options:
                          "default", "qwen", "with_ci"
        """
        self.template_name = template_name
        self.template_map = {
            "default": FN_CALL_TEMPLATE,
            "qwen": FN_CALL_TEMPLATE_QWEN,
            "with_ci": FN_CALL_TEMPLATE_WITH_CI,
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
                    if (not SPECIAL_CODE_MODE) or (
                        CODE_TOOL_PATTERN not in fn_call.name
                    ):
                        fc = {
                            "name": fn_call.name,
                            "arguments": json.loads(fn_call.arguments),
                        }
                        fc = json.dumps(fc, ensure_ascii=False)
                        fc = f"<tool_call>\n{fc}\n</tool_call>"
                    else:
                        para = json.loads(fn_call.arguments)
                        code = para["code"]
                        para["code"] = ""
                        fc = {"name": fn_call.name, "arguments": para}
                        fc = json.dumps(fc, ensure_ascii=False)
                        fc = f"<tool_call>\n{fc}\n<code>\n{code}\n</code>\n</tool_call>"

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
        tool_names = [
            function.get("name_for_model", function.get("name", ""))
            for function in functions
        ]
        tool_descs = "\n".join([json.dumps(f, ensure_ascii=False) for f in tool_descs])

        # Select template based on configuration
        if SPECIAL_CODE_MODE and any([CODE_TOOL_PATTERN in x for x in tool_names]):
            selected_template = FN_CALL_TEMPLATE_WITH_CI
        else:
            selected_template = self.template_map[self.template_name]

        tool_system = selected_template.format(tool_descs=tool_descs)
        if messages[0].role == SYSTEM:
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


SPECIAL_CODE_MODE = os.getenv("SPECIAL_CODE_MODE", "false").lower() == "true"
CODE_TOOL_PATTERN = "code_interpreter"
FN_CALL_TEMPLATE_WITH_CI = """# Tools

You may call one or more functions to assist with the user query.

You are provided with function signatures within <tools></tools> XML tags:
<tools>
{tool_descs}
</tools>

For each function call, return a json object with function name and arguments within <tool_call></tool_call> XML tags:
<tool_call>
{{"name": <function-name>, "arguments": <args-json-object>}}
</tool_call>
For code parameters, use placeholders first, and then put the code within <code></code> XML tags, such as:
<tool_call>
{{"name": <function-name>, "arguments": {{"code": ""}}}}
<code>
Here is the code.
</code>
</tool_call>"""


# Mainly for removing incomplete special tokens when streaming the output
# This assumes that '<tool_call>\n{"name": "' is the special token for the NousFnCallPrompt
def remove_incomplete_special_tokens(text: str) -> str:
    if text in '<tool_call>\n{"name": "':
        text = ""
    return text


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
