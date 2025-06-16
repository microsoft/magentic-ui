from typing import List
import asyncio
from urllib.parse import urlparse, parse_qsl, unquote, urlunparse
import json
from typing import Dict, Any, Optional
from autogen_core.models import UserMessage, ChatCompletionClient
from autogen_core import Image as AGImage
from pathlib import Path


def normalize_url(url: str) -> str:
    """
    Normalize a URL by unquoting the path, removing any trailing slash, and sorting query parameters.

    Args:
        url (str): The URL to normalize.

    Returns:
        str: The normalized URL.
    """
    parsed = urlparse(url)
    # Normalize the path by unquoting and removing any trailing slash
    path = unquote(parsed.path).rstrip("/")
    # Sort query parameters
    query = sorted(parse_qsl(parsed.query))
    # Reconstruct the URL with normalized path and sorted query
    normalized = parsed._replace(path=path, query=query)
    return urlunparse(normalized)


def are_urls_equal(url1: str, url2: str) -> bool:
    """
    Check if two URLs are equal after normalization.

    Args:
        url1 (str): The first URL.
        url2 (str): The second URL.

    Returns:
        bool: True if the URLs are equal after normalization, False otherwise.
    """
    return normalize_url(url1) == normalize_url(url2)


def exact_match_evaluator(ground_truth: str, candidate: str) -> float:
    """
    Evaluate the exact match between the ground truth and candidate strings.

    Args:
        ground_truth (str): The ground truth string.
        candidate (str): The candidate string.

    Returns:
        float: 1.0 if the strings match exactly, 0.0 otherwise.
    """
    return 1.0 if ground_truth.strip() == candidate.strip() else 0.0


def f1_evaluator(ground_truth: str, candidate: str) -> float:
    """
    Evaluate the F1 score between the ground truth and candidate strings based on token overlap.

    Args:
        ground_truth (str): The ground truth string.
        candidate (str): The candidate string.

    Returns:
        float: The F1 score.
    """
    gold_tokens = ground_truth.lower().split()
    pred_tokens = candidate.lower().split()
    gold_set = set(gold_tokens)
    pred_set = set(pred_tokens)
    common = gold_set.intersection(pred_set)
    if not common:
        return 0.0
    precision = len(common) / len(pred_set)
    recall = len(common) / len(gold_set)
    if precision + recall == 0:
        return 0.0
    return 2 * (precision * recall) / (precision + recall)


LLM_EVALUATOR_NO_ANSWER_PROMPT = """
As an evaluator, you will be presented with the following primary components to assist you in your role:

- Web Task Instruction: This is a clear and specific directive provided in natural language, detailing the online activity to be carried out. These requirements may include conducting searches, verifying information, comparing prices, checking availability, or any other action relevant to the specified web service (such as Amazon, Apple, ArXiv, BBC News, Booking etc).

- Result Screenshots: This is a visual representation of the screen showing the result or intermediate state of performing a web task. It serves as visual proof of the actions taken in response to the instruction.

- Result Response: This is a textual response obtained after the execution of the web task. It serves as textual result in response to the instruction.

- Result Response steps: This is a list of steps taken to achieve the result and general reasoning to 

-- You DO NOT NEED to interact with web pages or perform actions such as booking flights or conducting searches on websites.
-- You SHOULD NOT make assumptions based on information not presented in the screenshot when comparing it to the instructions.
-- Your primary responsibility is to conduct a thorough assessment of the web task instruction against the outcome depicted in the screenshot and in the response, evaluating whether the actions taken align with the given instructions.
-- NOTE that the instruction may involve more than one task, for example, locating the garage and summarizing the review. Failing to complete either task, such as not providing a summary, should be considered unsuccessful.
-- NOTE that the screenshot is authentic, but the response provided by LLM is generated at the end of web browsing, and there may be discrepancies between the text and the screenshots.
-- Note the difference: 1) Result response may contradict the screenshot, then the content of the screenshot prevails, 2) The content in the Result response is not mentioned on the screenshot, choose to believe the content.
-- Furthemore, consider how consistent the result response steps are with the final response.

Your response should be JSON object with the following three components:

1. score: integer from 1 to 10
2. success: boolean
3. reasoning: short explanation for the score.
{{
    "score": int,       # from 1 to 10
    "success": bool,    # True/False
    "reasoning": str    # short explanation
}}

Here is the task instruction: {task}

Here is the result response: {candidate_answer}

Here is the result response steps: {candidate_reasoning}

Attached as images are the screenshots if available.

Your score:
"""

LLM_EVALUATOR_GOLD_ANSWER_PROMPT = """
As an evaluator, you will be presented with the following primary components to assist you in your role:

- Web Task Instruction: This is a clear and specific directive provided in natural language, detailing the online activity to be carried out. These requirements may include conducting searches, verifying information, comparing prices, checking availability, or any other action relevant to the specified web service (such as Amazon, Apple, ArXiv, BBC News, Booking etc).

- Gold Truth Answer: This is the correct answer to the web task instruction. It serves as a benchmark for evaluating the candidate's response.

- Candidate Screenshots: This is a visual representation of the screen showing the result or intermediate state of performing a web task. It serves as visual proof of the actions taken in response to the instruction.

- Candidate Final answer: This is a textual response obtained after the execution of the web task. It serves as textual result in response to the instruction to be compared to the gold truth answer.

- Candidate Response steps: This is a list of steps taken to achieve the result and general reasoning to 

-- You DO NOT NEED to interact with web pages or perform actions such as booking flights or conducting searches on websites.
-- You SHOULD NOT make assumptions based on information not presented in the screenshot when comparing it to the instructions.
-- Your primary responsibility is to check if the candidate's answer matches the gold truth answer for the task.
-- NOTE that the instruction may involve more than one task, for example, locating the garage and summarizing the review. Failing to complete either task, such as not providing a summary, should be considered unsuccessful.
-- NOTE that the screenshot is authentic, but the response provided by Candidate is generated at the end of web browsing, and there may be discrepancies between the text and the screenshots.
-- Note the difference: 1) Candidate response may contradict the screenshot, then the content of the screenshot prevails, 2) The content in the Candidate response is not mentioned on the screenshot, choose to believe the content.
-- Furthemore, consider how consistent the Candidate response steps are with the Candidate final response.

Your response should be JSON object with the following three components:

1. score: integer from 1 to 10
2. success: boolean
3. reasoning: short explanation for the score.
{{
    "score": int,       # from 1 to 10
    "success": bool,    # True/False
    "reasoning": str    # short explanation
}}

Here is the task instruction: {task}

This is the gold truth answer: {gold_truth_answer}

Here is the Candidate final answer: {candidate_answer}

Here is the Candidate response steps: {candidate_reasoning}

Attached as images are the screenshots if available.

Your score:
"""


async def llm_evaluate_candidate_answer_async(
    task_question: str,
    candidate_answer: str,
    model_client: ChatCompletionClient,
    gold_truth_answer: Optional[str] = None,
    candidate_reasoning: Optional[str] = "not available",
    candidate_screenshots: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Uses an LLM to evaluate the candidate answer versus either the gold
    truth answer (if provided) or the task itself, returning a JSON object with:
    {
        "score": int,       # from 1 to 10
        "success": bool,    # True/False
        "reasoning": str    # short explanation
    }

    Args:
        task_question (str): Original task to be satisfied
        candidate_answer (str): The candidate's answer string
        model_client (ChatCompletionClient): A chat-completion-compatible client
        gold_truth_answer (str, optional): If provided, the gold standard we compare to
        candidate_reasoning (str, optional): Optional chain-of-thought or reasoning. Default: "not available"
        candidate_screenshots (List[str], optional): Optional list of screenshot references, filepaths
    Returns:
        dict: A dictionary with 'score', 'success', 'reasoning'
    """
    # 1) Build the prompt
    if gold_truth_answer:
        prompt = LLM_EVALUATOR_GOLD_ANSWER_PROMPT.format(
            task=task_question,
            candidate_answer=candidate_answer,
            gold_truth_answer=gold_truth_answer,
            candidate_reasoning=candidate_reasoning,
            candidate_screenshots=candidate_screenshots,
        ).strip()
    else:
        prompt = LLM_EVALUATOR_NO_ANSWER_PROMPT.format(
            task=task_question,
            candidate_answer=candidate_answer,
            candidate_reasoning=candidate_reasoning,
            candidate_screenshots=candidate_screenshots,
        ).strip()

    images: list[AGImage] = []
    if candidate_screenshots:
        for path in candidate_screenshots:
            # from_file
            try:
                image = AGImage.from_file(Path(path))
                images.append(image)
            except Exception as e:
                print(f"Error: {e}")
                continue

    user_message: str | list[str | AGImage] = ""
    if images and len(images) > 0:
        user_message = [
            prompt,
        ]
        user_message.extend(images)
    else:
        user_message = prompt

    messages = [
        UserMessage(
            source="user",
            content=user_message,
        )
    ]

    # Now call the GPT model
    max_iters = 5
    while max_iters > 0:
        try:
            response = await model_client.create(messages, json_output=True)
            assert isinstance(response.content, str)
            result = json.loads(response.content)
            assert isinstance(result, dict)
            assert "score" in result
            assert "success" in result
            assert "reasoning" in result
            break
        except Exception:
            max_iters -= 1
            continue

    # 5) Validate and fill any missing fields with defaults
    final_result: Dict[str, Any] = {
        "score": result.get("score", 0) / 10,  # type: ignore
        "success": result.get("success", False),  # type: ignore
        "reasoning": result.get("reasoning", "No reasoning provided."),  # type: ignore
    }

    return final_result


def llm_evaluate_candidate_answer(
    task_question: str,
    candidate_answer: str,
    model_client: ChatCompletionClient,
    gold_truth_answer: Optional[str] = None,
    candidate_reasoning: Optional[str] = "not available",
    candidate_screenshots: Optional[List[str]] = None,
) -> Dict[str, Any]:
    return asyncio.run(
        llm_evaluate_candidate_answer_async(
            task_question=task_question,
            candidate_answer=candidate_answer,
            model_client=model_client,
            gold_truth_answer=gold_truth_answer,
            candidate_reasoning=candidate_reasoning,
            candidate_screenshots=candidate_screenshots,
        )
    )
