#!/usr/bin/env python3
"""
This script analyzes SentinelBench evaluation run directories to identify missing
runs, timeout failures, and completion statistics across different task dimensions.

USAGE:
    # Check directories 0 and 1 for runs/MagenticUI/SentinelBench/test/ 
    python missing_runs_checker.py

    # Check directories 0 and 1 for a custom base path
    python missing_runs_checker.py --base-path runs/MagenticUI_web_surfer_only/SentinelBench/test

    # Check custom directories and jsonl file
    python missing_runs_checker.py \
        --base-path runs/MagenticUI_web_surfer_only/SentinelBench/test \
        --jsonl-path data/SentinelBench/test.jsonl \
        --directories=0 --directories=1 --directories=2

ARGUMENTS:
    --base-path: Base path where run directories are located (default: runs/MagenticUI_web_surfer_only/SentinelBench/test)
    --jsonl-path: Path to the test.jsonl file with task definitions (default: data/SentinelBench/test.jsonl)
    --directories: The directories that house the different task runs (default: 0 and 1)

The script validates runs by checking for required files (times.json, answer files,
model_tokens_usage.json) and analyzes completion status and timeout occurrences.
"""

import json
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import logging
import sys
import typer

# Import task variants from centralized configuration
sys.path.append(str(Path(__file__).parent.parent))
try:
    from task_variants import SENTINELBENCH_TASK_VARIANTS  # type: ignore
except ImportError:
    # Fallback if import fails
    SENTINELBENCH_TASK_VARIANTS = {}  # type: ignore

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Use the centralized task variants as expected dimensions
EXPECTED_DIMENSIONS: Dict[str, List[int]] = SENTINELBENCH_TASK_VARIANTS  # type: ignore[assignment]


def load_expected_tasks(
    jsonl_path_str: str = "data/SentinelBench/test.jsonl",
) -> Tuple[List[str], Dict[str, str]]:
    """Load expected task IDs and passwords from test.jsonl file."""
    jsonl_path = Path(jsonl_path_str)

    if not jsonl_path.exists():
        logger.error(f"test.jsonl not found at {jsonl_path}")
        return [], {}

    tasks: List[str] = []
    task_passwords: Dict[str, str] = {}

    with open(jsonl_path, "r") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    task_data = json.loads(line)
                    task_id = task_data["id"]
                    password = task_data.get("password", "")

                    tasks.append(task_id)
                    task_passwords[task_id] = password

                except json.JSONDecodeError:
                    logger.warning(f"Skipping invalid JSON line: {line}")
                    continue

    logger.info(f"Loaded {len(tasks)} tasks with passwords from test.jsonl")
    return tasks, task_passwords


def check_run_validity(
    run_dir: Path, task_name: str, dimension: int, expected_password: str
) -> Tuple[bool, bool, str]:
    """
    Check if a run exists and is valid (contains correct password).

    Returns:
        (exists, has_timeout, status_message)
    """
    task_dir = run_dir / task_name / str(dimension)

    if not task_dir.exists():
        return False, False, "Directory missing"

    # Check for required files (based on analyze_dimensions.py logic)
    times_file = task_dir / "times.json"
    answer_files = list(task_dir.glob(f"{task_name}_{dimension}_answer.json"))
    tokens_file = task_dir / "model_tokens_usage.json"

    if not times_file.exists():
        return False, False, "times.json missing"

    if not answer_files:
        return False, False, "answer file missing"

    if not tokens_file.exists():
        return False, False, "model_tokens_usage.json missing"

    # Check for timeouts and completion status
    try:
        with open(times_file) as f:
            times_data = json.load(f)
            completed = times_data.get("completed", False)
            interrupted = times_data.get("interrupted", False)

        with open(answer_files[0]) as f:
            answer_data = json.load(f)
            answer = answer_data.get("answer", "")

            # Check for timeout first
            has_timeout = "TIMEOUT" in answer.upper()

            # Check if the answer contains the expected password (success)
            has_correct_password = False
            if expected_password and expected_password.upper() in answer.upper():
                has_correct_password = True
            elif not expected_password:
                # For tasks without expected passwords, we can't validate correctness
                # This is a missing runs checker, not a scorer - be conservative
                # Let the actual evaluation scoring handle correctness validation
                has_correct_password = False

        if interrupted:
            return True, has_timeout, "interrupted"
        elif not completed:
            return True, has_timeout, "not completed"
        elif has_timeout:
            return True, True, "completed with timeout"
        elif has_correct_password:
            return True, False, "completed successfully"
        else:
            return True, False, "completed with failure"

    except (json.JSONDecodeError, FileNotFoundError, KeyError) as e:
        return False, False, f"Error reading files: {e}"


def check_missing_runs(
    base_path: str = "runs/MagenticUI_web_surfer_only/SentinelBench/test",
    jsonl_path: str = "data/SentinelBench/test.jsonl",
    directories: Optional[List[str]] = None,
):
    """Check for missing runs and generate report."""
    base_path_obj = Path(base_path)

    if directories is None:
        directories = ["0", "1"]

    # Load expected tasks and passwords
    expected_tasks, task_passwords = load_expected_tasks(jsonl_path)

    if not expected_tasks:
        logger.error("No tasks loaded. Exiting.")
        return

    total_expected = 0
    total_found = 0
    total_missing = 0
    total_timeouts = 0
    all_missing_runs: List[str] = []
    timeout_stats: Dict[str, Dict[str, int]] = {}

    print("\n" + "=" * 80)
    print("SENTINELBENCH RUN STATUS REPORT")
    print("=" * 80)

    for directory in directories:
        run_dir = base_path_obj / directory

        print(f"\n📁 Directory: {directory}")
        print("-" * 50)

        dir_expected = 0
        dir_found = 0
        dir_missing = 0
        dir_timeouts = 0
        dir_missing_runs: List[str] = []

        for task_name in expected_tasks:
            if task_name not in EXPECTED_DIMENSIONS:
                logger.warning(
                    f"Task '{task_name}' not in expected dimensions. Skipping."
                )
                continue

            expected_dims = EXPECTED_DIMENSIONS[task_name]
            expected_password = task_passwords.get(task_name, "")

            for dimension in expected_dims:
                dir_expected += 1
                total_expected += 1

                exists, has_timeout, status = check_run_validity(
                    run_dir, task_name, dimension, expected_password
                )

                if exists:
                    dir_found += 1
                    total_found += 1

                    if has_timeout:
                        dir_timeouts += 1
                        total_timeouts += 1

                        # Track timeout stats by task
                        if task_name not in timeout_stats:
                            timeout_stats[task_name] = {}
                        if directory not in timeout_stats[task_name]:
                            timeout_stats[task_name][directory] = 0
                        timeout_stats[task_name][directory] += 1
                else:
                    dir_missing += 1
                    total_missing += 1
                    missing_run = f"{directory}/{task_name}/{dimension}"
                    dir_missing_runs.append(missing_run)
                    all_missing_runs.append(missing_run)

        # Print directory summary
        completion_rate = (dir_found / dir_expected * 100) if dir_expected > 0 else 0
        timeout_rate = (dir_timeouts / dir_found * 100) if dir_found > 0 else 0

        print(f"Expected runs: {dir_expected}")
        print(f"Found runs: {dir_found}")
        print(f"Missing runs: {dir_missing}")
        print(f"Completion rate: {completion_rate:.1f}%")
        print(f"Runs with timeouts: {dir_timeouts} ({timeout_rate:.1f}% of found runs)")

        if dir_missing_runs:
            print(f"\nMissing runs in directory {directory}:")
            for missing_run in sorted(dir_missing_runs):
                print(f"  ❌ {missing_run}")

    # Task dimension breakdown
    print("\n📋 TASK DIMENSION BREAKDOWN")
    print("-" * 80)

    for task_name in expected_tasks:
        if task_name not in EXPECTED_DIMENSIONS:
            continue

        expected_dims = set(EXPECTED_DIMENSIONS[task_name])

        for directory in directories:
            run_dir = base_path_obj / directory
            found_dims: set[int] = set()
            timeout_dims: set[int] = set()
            failure_dims: set[int] = set()

            expected_password = task_passwords.get(task_name, "")

            for dimension in expected_dims:
                exists, has_timeout, status_msg = check_run_validity(
                    run_dir, task_name, dimension, expected_password
                )
                if exists:
                    found_dims.add(dimension)
                    if has_timeout:
                        timeout_dims.add(dimension)
                    elif "failure" in status_msg:
                        failure_dims.add(dimension)

            missing_dims = sorted(expected_dims - found_dims)
            timeout_dims_sorted = sorted(timeout_dims)
            failure_dims_sorted = sorted(failure_dims)
            successful_dims = sorted(found_dims - timeout_dims - failure_dims)

            # found_count = len(found_dims)
            total_count = len(expected_dims)
            failed_count = len(timeout_dims) + len(failure_dims)

            # Build status string
            info_parts: List[str] = []

            if len(successful_dims) == total_count:
                status = "✅ Complete"
            elif len(successful_dims) == 0:
                if missing_dims and not (timeout_dims_sorted or failure_dims_sorted):
                    status = f"❌ Missing {len(missing_dims)}/{total_count}"
                else:
                    status = f"💥 All failed {failed_count}/{total_count}"
            else:
                status = f"⚠️  Partial {len(successful_dims)}/{total_count} success"

            if missing_dims:
                info_parts.append(f"Missing: {missing_dims}")
            if timeout_dims_sorted:
                info_parts.append(f"Timeouts: {timeout_dims_sorted}")
            if failure_dims_sorted:
                info_parts.append(f"Failures: {failure_dims_sorted}")

            info_str = " - " + ", ".join(info_parts) if info_parts else ""
            print(f"  {task_name} (Dir {directory}): {status}{info_str}")

    # Overall summary
    print("\n" + "=" * 80)
    print("OVERALL SUMMARY")
    print("=" * 80)

    overall_completion = (
        (total_found / total_expected * 100) if total_expected > 0 else 0
    )
    overall_timeout_rate = (
        (total_timeouts / total_found * 100) if total_found > 0 else 0
    )

    print(f"Total expected runs: {total_expected}")
    print(f"Total found runs: {total_found}")
    print(f"Total missing runs: {total_missing}")
    print(f"Overall completion rate: {overall_completion:.1f}%")
    print(
        f"Total runs with timeouts: {total_timeouts} ({overall_timeout_rate:.1f}% of found runs)"
    )

    # Task breakdown
    print(
        f"\nTask breakdown ({len(expected_tasks)} tasks, {len(directories)} directories):"
    )
    for task in expected_tasks:
        if task in EXPECTED_DIMENSIONS:
            expected_per_dir = len(EXPECTED_DIMENSIONS[task])
            total_expected_for_task = expected_per_dir * len(directories)
            print(
                f"  {task}: {expected_per_dir} dimensions × {len(directories)} directories = {total_expected_for_task} expected runs"
            )

    # Timeout statistics by task
    if timeout_stats:
        print("\n⏰ TIMEOUT STATISTICS BY TASK")
        print("-" * 50)
        for task_name, dirs in sorted(timeout_stats.items()):
            total_task_timeouts = sum(dirs.values())
            print(f"{task_name}: {total_task_timeouts} timeouts", end="")
            if len(dirs) > 1:
                dir_breakdown = ", ".join(
                    [f"dir {d}: {count}" for d, count in sorted(dirs.items())]
                )
                print(f" ({dir_breakdown})")
            else:
                print()

    # Missing runs summary
    if all_missing_runs:
        print(f"\n❌ ALL MISSING RUNS ({len(all_missing_runs)} total):")
        print("-" * 50)
        for missing_run in sorted(all_missing_runs):
            print(f"  {missing_run}")
    else:
        print("\n✅ No missing runs found!")

    print("\n" + "=" * 80)


app = typer.Typer(add_completion=False)


@app.command()
def main(
    base_path: str = typer.Option(
        "runs/MagenticUI_web_surfer_only/SentinelBench/test",
        "--base-path",
        help="Base path where run directories are located",
    ),
    jsonl_path: str = typer.Option(
        "data/SentinelBench/test.jsonl",
        "--jsonl-path",
        help="Path to the test.jsonl file with task definitions",
    ),
    directories: List[str] = typer.Option(
        ["0", "1"],
        "--directories",
        help="Directory names to check within the base path",
    ),
):
    """Check for missing SentinelBench runs and report timeout statistics."""
    check_missing_runs(
        base_path=base_path,
        jsonl_path=jsonl_path,
        directories=directories,
    )


if __name__ == "__main__":
    app()
