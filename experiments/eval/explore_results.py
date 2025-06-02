import os
import json
import pandas as pd
import argparse
from typing import Dict, Any
from magentic_ui.eval.benchmarks.gaia.gaia import GaiaBenchmark


def get_run_results_df(
    run_dir: str, data_dir: str, dataset_name: str = "Gaia"
) -> pd.DataFrame:
    """
    Process a run directory and create a DataFrame containing all task results and ground truth.

    Args:
        run_dir (str): Path to the run directory containing task subdirectories

    Returns:
        pd.DataFrame: DataFrame containing task results and ground truth
    """
    # Initialize benchmark
    if dataset_name == "Gaia":
        benchmark = GaiaBenchmark(data_dir=data_dir)
    else:
        raise ValueError(f"Invalid dataset name: {dataset_name}")
    # Download the dataset (only needed once)
    benchmark.download_dataset()
    # Load it into memory
    benchmark.load_dataset()

    # Initialize lists to store data
    data = []

    # Process each task directory
    for task_dir in os.listdir(run_dir):
        task_path = os.path.join(run_dir, task_dir)

        # Skip if not a directory or if it's a log file
        if not os.path.isdir(task_path) or task_dir.startswith("."):
            continue

        task_data: Dict[str, Any] = {"task_id": task_dir}

        # Get ground truth from benchmark
        if task_dir in benchmark.tasks:
            task_data["ground_truth"] = benchmark.tasks[task_dir].ground_truth
            task_data["question"] = benchmark.tasks[task_dir].question
            task_data["difficulty"] = benchmark.tasks[task_dir].difficulty
            task_data["metadata"] = benchmark.tasks[task_dir].metadata

        # Read answer file
        answer_file = os.path.join(task_path, f"{task_dir}_answer.json")
        if os.path.exists(answer_file):
            with open(answer_file, "r") as f:
                task_data["answer"] = json.load(f)["answer"]

        # Read messages file
        messages_file = os.path.join(task_path, f"{task_dir}_messages.json")
        if os.path.exists(messages_file):
            with open(messages_file, "r") as f:
                task_data["messages"] = json.load(f)
            user_messages = [
                message
                for message in task_data["messages"]
                if message["source"] == "user_proxy"
            ]
            task_data["user_messages"] = user_messages

        # Read score file
        score_file = os.path.join(task_path, "score.json")
        if os.path.exists(score_file):
            with open(score_file, "r") as f:
                score = json.load(f)
                task_data["score"] = score["score"]

        # Read times file
        times_file = os.path.join(task_path, "times.json")
        if os.path.exists(times_file):
            with open(times_file, "r") as f:
                task_data["duration"] = json.load(f)["duration"]

        data.append(task_data)
    df = pd.DataFrame(data)
    # Filter out rows where score is NaN
    df = df.dropna(subset=["score"])

    # Save DataFrame to CSV
    output_csv = os.path.join(run_dir, "results.csv")
    df.to_csv(output_csv, index=False)
    print(f"Results DataFrame saved to {output_csv}")

    return df


def get_output_prefix(run_dir: str) -> str:
    """Generate output prefix from last 4 parts of run_dir path."""
    # Split path and get last 4 parts
    parts = os.path.normpath(run_dir).split(os.sep)
    relevant_parts = parts[-4:] if len(parts) >= 4 else parts
    return "_".join(relevant_parts)


def main():
    parser = argparse.ArgumentParser(
        description="Process run results and analyze tasks."
    )
    parser.add_argument(
        "--run-dir",
        type=str,
        required=True,
        help="Path to the run directory containing task subdirectories",
    )
    parser.add_argument(
        "--data-dir", type=str, required=True, help="Path to the data directory"
    )
    args, unknown = (
        parser.parse_known_args()
    )  # First parse run_dir to generate default filenames

    # Generate default filenames based on run_dir
    prefix = get_output_prefix(args.run_dir)
    parser.add_argument(
        "--failed_output",
        type=str,
        default=f"{args.run_dir}/failed_tasks_{prefix}.json",
        help="Output file path for failed tasks",
    )
    parser.add_argument(
        "--all_output",
        type=str,
        default=f"{args.run_dir}/all_tasks_{prefix}.json",
        help="Output file path for all tasks",
    )

    args = parser.parse_args()  # Parse all arguments

    df = get_run_results_df(args.run_dir, args.data_dir)

    # Add a column to flag 'unable to determine' answers
    unable_str = "Unable to determine"
    df["unable_to_determine"] = (
        df["answer"].astype(str).str.strip().str.contains(unable_str)
    )
    unable_count = df["unable_to_determine"].sum()

    # Accuracy excluding 'unable to determine'
    df_excl = df[~df["unable_to_determine"]]
    if len(df_excl) > 0:
        acc_excl = (df_excl["score"] > 0).mean()
    else:
        acc_excl = float("nan")

    # Accuracy counting 'unable to determine' as correct
    acc_unable_correct = ((df["score"] > 0) | df["unable_to_determine"]).mean()

    # Create a list to store all tasks and failed tasks
    all_tasks = []
    failed_tasks = []

    for index, row in df.iterrows():
        task_info = {
            "task_id": row["task_id"],
            "question": row["question"],
            "answer": row["answer"],
            "ground_truth": row["ground_truth"],
            "score": row["score"],
            "difficulty": row["difficulty"],
            "duration": row.get("duration", None),
            "messages": row["messages"],
        }
        all_tasks.append(task_info)

        if row["score"] == 0:
            failed_tasks.append(task_info)

    # Write all tasks to a log file
    with open(args.all_output, "w") as log_file:
        json.dump(all_tasks, log_file, indent=4, ensure_ascii=False)
    print(f"All tasks written to {args.all_output}")

    # Write failed tasks to a log file
    with open(args.failed_output, "w") as log_file:
        json.dump(failed_tasks, log_file, indent=4, ensure_ascii=False)
    print(f"Failed tasks written to {args.failed_output}")

    # Print summary statistics
    print("\nSummary:")
    print(f"Total tasks: {len(all_tasks)}")
    print(f"Failed tasks: {len(failed_tasks)}")
    print(f"Unable to determine: {unable_count}")
    print(f"Rate of unable to determine: {unable_count / len(df) * 100:.2f}%")
    print(
        f"Success rate: {((len(all_tasks) - len(failed_tasks)) / len(all_tasks) * 100):.2f}%"
    )
    print(f"Accuracy (excluding 'unable to determine'): {acc_excl*100:.2f}%")
    print(
        f"Accuracy (counting 'unable to determine' as correct): {acc_unable_correct*100:.2f}%"
    )


if __name__ == "__main__":
    main()
