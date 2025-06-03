import asyncio
import logging
import pandas as pd
from typing import Dict, Any, Optional, Union
import argparse
import os
from datetime import datetime

from autogen_core.models import (
    ChatCompletionClient,
    UserMessage,
    SystemMessage,
)

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configure model client
default_client_config = {
    "provider": "OpenAIChatCompletionClient",
    "config": {
        "model": "gpt-4o-2024-08-06",
    },
    "max_retries": 5,
}


def get_model_client(
    endpoint_config: Optional[Union[Dict[str, Any], None]],
) -> ChatCompletionClient:
    if endpoint_config is None:
        return ChatCompletionClient.load_component(default_client_config)
    return ChatCompletionClient.load_component(endpoint_config)


async def check_ground_truth_in_messages(
    question: str, ground_truth: str, user_messages_str: str
) -> int:
    """
    Ask the model if ground_truth is included in user_messages
    Returns 1 if ground truth is included, 0 otherwise
    """
    prompt = f"""

    I have a question: "{question}"


    I have a list of messages a user sent to an AI assistant: {user_messages_str}
    

    The question has a ground truth answer: "{ground_truth}"


    Check if any of the user messages reveal directly the ground truth answer to the AI assistant. 
    In cases where the ground truth is found in the user messages but the message looks like a validation of the answer, then you should output 0.
    Answer with ONLY 1 if the ground truth is included exactly, or ONLY 0 if it is not.
    IMPORTANT: Only output 1 or 0, no other text.
    """

    model_client = get_model_client(None)
    messages = [
        SystemMessage(
            content="You analyze if specific information is contained in messages."
        ),
        UserMessage(content=prompt, source="user"),
    ]

    try:
        response = await model_client.create(messages=messages)
        answer = response.content.strip()

        # Ensure we only get 0 or 1
        if answer == "1":
            result = 1
        else:
            result = 0

        await model_client.close()
        return result
    except Exception as e:
        logger.error(f"Error calling model: {e}")
        await model_client.close()
        return -1


async def process_csv(csv_path: str, output_path: str) -> None:
    """Process the CSV file and analyze if ground truth is in user messages"""
    try:
        df = pd.read_csv(csv_path)
        logger.info(f"Loaded dataframe with {len(df)} rows")

        # Create columns for the results
        df["ground_truth_in_messages"] = None
        df["trivial_ground_truth_in_messages"] = (
            None  # New column for trivial string match
        )
        df["llm_execution_count"] = 0  # New column for counting llm executions
        df["llm_plan_count"] = 0  # New column for counting llm planning

        for index, row in df.iterrows():
            if pd.isna(row.get("ground_truth")) or pd.isna(row.get("user_messages")):
                logger.warning(f"Missing data for row {index}")
                continue

            user_messages_str = str(row["user_messages"])
            # Count llm executions in user messages
            try:
                messages = eval(user_messages_str)
                llm_count = sum(
                    1
                    for msg in messages
                    if isinstance(msg, dict)
                    and isinstance(msg.get("metadata"), dict)
                    and "user_execution_reply" in msg.get("metadata", {})
                    and msg["metadata"]["user_execution_reply"] == "llm"
                )
                plan_count = sum(
                    1
                    for msg in messages
                    if isinstance(msg, dict)
                    and isinstance(msg.get("metadata"), dict)
                    and "user_plan_reply" in msg.get("metadata", {})
                    and msg["metadata"]["user_plan_reply"] == "llm"
                )
                df.at[index, "llm_execution_count"] = llm_count
                df.at[index, "llm_plan_count"] = plan_count
            except Exception as e:
                logger.warning(
                    f"Could not parse messages for task {row.get('task_id', index)}: {e}"
                )
                df.at[index, "llm_execution_count"] = 0
                df.at[index, "llm_plan_count"] = 0

            answer = str(row.get("answer", "")).strip().lower()
            # if answer == "unable to determine":
            #    df.at[index, "llm_execution_count"] = max(1, df.at[index, "llm_execution_count"])

            logger.info(f"Processing task {row.get('task_id', index)}")
            question = str(row["question"])
            ground_truth = str(row["ground_truth"])
            actual_user_messages = eval(user_messages_str)
            actual_user_messages_str = ""
            for msg in actual_user_messages:
                actual_user_messages_str += f"{msg['content']}\n"
            trivial_result = int(ground_truth in actual_user_messages_str)
            df.at[index, "trivial_ground_truth_in_messages"] = trivial_result
            result = await check_ground_truth_in_messages(
                question, ground_truth, actual_user_messages_str
            )
            df.at[index, "ground_truth_in_messages"] = result
            logger.info(
                f"Task {row.get('task_id', index)}: result = {result}, llm executions = {df.at[index, 'llm_execution_count']}, llm planning = {df.at[index, 'llm_plan_count']}"
            )

        # Save results to new CSV
        df.to_csv(output_path, index=False)
        logger.info(f"Results saved to {output_path}")

        # Calculate summary statistics (ALL TASKS)
        counts = df["ground_truth_in_messages"].value_counts()
        trivial_counts = df["trivial_ground_truth_in_messages"].value_counts()
        total_valid = counts.sum()
        trivial_total_valid = trivial_counts.sum()
        percentage_included = (
            (counts.get(1, 0) / total_valid * 100) if total_valid > 0 else 0
        )
        trivial_percentage_included = (
            (trivial_counts.get(1, 0) / trivial_total_valid * 100)
            if trivial_total_valid > 0
            else 0
        )

        logger.info(
            f"Summary (ALL TASKS): Ground truth included in {counts.get(1, 0)}/{total_valid} cases ({percentage_included:.2f}%)"
        )
        logger.info(
            f"Trivial string match (ALL TASKS): Ground truth included in {trivial_counts.get(1, 0)}/{trivial_total_valid} cases ({trivial_percentage_included:.2f}%)"
        )

        mask_not_unable = (
            df["answer"].astype(str).str.strip().str.lower() != "unable to determine"
        )
        df_not_unable = df[mask_not_unable]
        # Ensure these are pandas Series for value_counts
        gt_series = pd.Series(df_not_unable["ground_truth_in_messages"])
        trivial_series = pd.Series(df_not_unable["trivial_ground_truth_in_messages"])
        counts_not_unable = gt_series.value_counts()
        trivial_counts_not_unable = trivial_series.value_counts()
        total_valid_not_unable = counts_not_unable.sum()
        trivial_total_valid_not_unable = trivial_counts_not_unable.sum()
        percentage_included_not_unable = (
            (counts_not_unable.get(1, 0) / total_valid_not_unable * 100)
            if total_valid_not_unable > 0
            else 0
        )
        trivial_percentage_included_not_unable = (
            (trivial_counts_not_unable.get(1, 0) / trivial_total_valid_not_unable * 100)
            if trivial_total_valid_not_unable > 0
            else 0
        )
        logger.info(
            f"Summary (EXCLUDING 'unable to determine'): Ground truth included in {counts_not_unable.get(1, 0)}/{total_valid_not_unable} cases ({percentage_included_not_unable:.2f}%)"
        )
        logger.info(
            f"Trivial string match (EXCLUDING 'unable to determine'): Ground truth included in {trivial_counts_not_unable.get(1, 0)}/{trivial_total_valid_not_unable} cases ({trivial_percentage_included_not_unable:.2f}%)"
        )

        # Add summary statistics for llm executions
        llm_stats = df["llm_execution_count"].describe()
        tasks_with_execution = (df["llm_execution_count"] > 0).sum()
        total_tasks = len(df)

        # Get statistics for tasks with at least 1 execution
        tasks_with_execution_df = df[df["llm_execution_count"] > 0]
        tasks_with_planning = (df["llm_plan_count"] > 0).sum()
        median_when_used = tasks_with_execution_df["llm_execution_count"].median()
        mean_when_used = tasks_with_execution_df["llm_execution_count"].mean()

        logger.info("\nLLM Execution Statistics:")
        logger.info(
            f"Tasks with at least 1 execution: {tasks_with_execution}/{total_tasks} ({(tasks_with_execution/total_tasks)*100:.2f}%)"
        )
        logger.info(
            f"Tasks with at least 1 planning: {tasks_with_planning}/{total_tasks} ({(tasks_with_planning/total_tasks)*100:.2f}%)"
        )
        logger.info("\nWhen LLM is used at least once:")
        logger.info(f"  - Median executions: {median_when_used:.2f}")
        logger.info(f"  - Mean executions: {mean_when_used:.2f}")
        logger.info("\nOverall statistics:")
        logger.info(f"Mean executions per task: {llm_stats['mean']:.2f}")
        logger.info(f"Median executions per task: {llm_stats['50%']:.2f}")
        logger.info(f"Max executions in a task: {llm_stats['max']:.0f}")
        logger.info(f"Min executions in a task: {llm_stats['min']:.0f}")

    except Exception as e:
        logger.error(f"Error processing CSV: {e}")


def main():
    parser = argparse.ArgumentParser(description="Analyze simulated user data CSV.")
    parser.add_argument(
        "--run-dir", type=str, required=True, help="Path to the run directory."
    )
    args = parser.parse_args()

    run_dir = args.run_dir
    input_csv = os.path.join(run_dir, "results.csv")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_csv = os.path.join(run_dir, f"sim_user_{timestamp}.csv")

    # Run the analysis
    asyncio.run(process_csv(input_csv, output_csv))


if __name__ == "__main__":
    main()
